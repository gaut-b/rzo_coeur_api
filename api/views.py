from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cart
from .permissions import IsCashier
from .serializers import (
    ArticleSerializer,
    BulkArticleCreateSerializer,
    CartCollectSerializer,
    CartSerializer,
)


class ArticleCreateView(APIView):
    """
    API endpoint for bulk article creation.
    Only accessible by authenticated users with CASHIER role.

    POST /api/articles/
    Only POST requests are supported; all other HTTP methods will return 405 Method Not Allowed.
    Request body:
    {
        "client_id": 1,
        "articles": [
            {"barcode": 3017620422003},
            {"barcode": 3564700013151}
        ]
    }

    Note: The shop_id is automatically retrieved from the authenticated cashier's shop.
    """

    permission_classes = [IsCashier]

    @extend_schema(
        summary="Create multiple articles in bulk",
        description="""
        Allows authenticated cashiers to create multiple articles at once by scanning
        a client's barcode followed by article barcodes.

        **Workflow:**
        1. Cashier scans the client's barcode (client_id)
        2. Cashier scans multiple article barcodes (up to 50 per request)
        3. All articles are created with cart=null and associated with the cashier's shop

        **Permissions:**
        - User must be authenticated (JWT Cookie)
        - User must have CASHIER role
        - Articles are automatically associated with the cashier's shop

        **Validation:**
        - client_id must exist and correspond to a CLIENT user
        - articles list cannot be empty
        - Maximum 50 articles per request
        - Cashier must have an associated shop
        """,
        request=BulkArticleCreateSerializer,
        responses={
            201: {
                "description": "Articles successfully created",
                "content": {
                    "application/json": {
                        "example": {
                            "message": "Successfully created 2 articles.",
                            "articles": [
                                {
                                    "id": 1,
                                    "name": "",
                                    "barcode": 3017620422003,
                                    "client": 1,
                                    "shop": 1,
                                    "cart": None,
                                },
                                {
                                    "id": 2,
                                    "name": "",
                                    "barcode": 3564700013151,
                                    "client": 1,
                                    "shop": 1,
                                    "cart": None,
                                },
                            ],
                        }
                    }
                },
            },
            400: {
                "description": "Bad Request - Validation errors",
                "content": {
                    "application/json": {
                        "examples": {
                            "invalid_client": {
                                "summary": "Invalid client ID",
                                "value": {"client_id": ["Client with id 999 does not exist."]},
                            },
                            "not_a_client": {
                                "summary": "User is not a client",
                                "value": {"client_id": ["User with id 2 is not a Client."]},
                            },
                            "empty_articles": {
                                "summary": "Empty articles list",
                                "value": {"articles": ["Articles list cannot be empty."]},
                            },
                            "too_many_articles": {
                                "summary": "Too many articles",
                                "value": {
                                    "articles": [
                                        "Cannot create more than 50 articles at once. "
                                        "Received 75 articles. Please reduce the batch size."
                                    ]
                                },
                            },
                            "no_shop": {
                                "summary": "Cashier has no associated shop",
                                "value": {
                                    "non_field_errors": [
                                        "Authenticated user does not have an associated shop."
                                    ]
                                },
                            },
                        }
                    }
                },
            },
            401: {
                "description": "Unauthorized - Authentication required",
                "content": {
                    "application/json": {
                        "example": {"detail": "Authentication credentials were not provided."}
                    }
                },
            },
            403: {
                "description": "Forbidden - User is not a cashier",
                "content": {
                    "application/json": {
                        "example": {"detail": "You do not have permission to perform this action."}
                    }
                },
            },
        },
        examples=[
            OpenApiExample(
                "Valid request with 2 articles",
                value={
                    "client_id": 1,
                    "articles": [{"barcode": 3017620422003}, {"barcode": 3564700013151}],
                },
                request_only=True,
            ),
            OpenApiExample(
                "Valid request with 5 articles",
                value={
                    "client_id": 1,
                    "articles": [
                        {"barcode": 3017620422003},
                        {"barcode": 3564700013151},
                        {"barcode": 8712566405619},
                        {"barcode": 5410188031508},
                        {"barcode": 3228857000852},
                    ],
                },
                request_only=True,
            ),
        ],
        tags=["Articles"],
    )
    def post(self, request):
        """
        Create multiple articles in bulk.
        Validates input data and creates articles associated with a client and shop.
        """
        serializer = BulkArticleCreateSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            # Create articles using the serializer
            created_articles = serializer.save()

            # Serialize the created articles for response
            response_serializer = ArticleSerializer(created_articles, many=True)

            return Response(
                {
                    "message": f"Successfully created {len(created_articles)} articles.",
                    "articles": response_serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CartCollectView(APIView):
    """API endpoint for marking a cart as collected by a cashier."""

    permission_classes = [IsCashier]

    @extend_schema(
        summary="Mark cart as collected",
        description="""
        Mark a cart as collected when the recipient picks it up.

        **Authentication**: Required (JWT Cookie)

        **Permission**: CASHIER role only

        **Validations**:
        - Cart must exist
        - Cart status must be "ASSIGNED"
        - Cashier can only collect carts from their shop
        - Recipient ID must match the cart's recipient

        **Actions**:
        - Updates cart status to "COLLECTED"
        - Sets collected_at timestamp
        """,
        request=CartCollectSerializer,
        responses={
            200: CartSerializer,
            400: {
                "description": "Bad Request",
                "examples": {
                    "invalid_status": {
                        "value": {
                            "status": (
                                "Cart must be in ASSIGNED status to be collected. "
                                "Current status: PENDING"
                            )
                        }
                    },
                    "recipient_mismatch": {
                        "value": {
                            "recipient_id": "The recipient ID does not match the cart's recipient."
                        }
                    },
                },
            },
            403: {
                "description": "Forbidden - Wrong shop or not a cashier",
                "examples": {
                    "wrong_shop": {"value": {"shop": "You can only collect carts from your shop."}}
                },
            },
            404: {
                "description": "Cart not found",
                "examples": {"not_found": {"value": {"error": "Cart not found."}}},
            },
        },
        tags=["Carts"],
    )
    def patch(self, request, cart_id):
        """Handle PATCH request to mark cart as collected."""
        # Get the cart or return 404
        try:
            cart = Cart.objects.select_related("shop").get(pk=cart_id)
        except Cart.DoesNotExist:
            return Response(
                {"error": "Cart not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate and update
        serializer = CartCollectSerializer(
            data=request.data,
            context={"request": request, "cart": cart},
        )

        if serializer.is_valid():
            updated_cart = serializer.update(cart, serializer.validated_data)
            response_serializer = CartSerializer(updated_cart)
            return Response(
                {
                    "message": "Cart successfully marked as collected.",
                    "cart": response_serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
