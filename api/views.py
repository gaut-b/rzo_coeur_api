from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .enums import CartStatus
from .models import Article, Cart, Recipient
from .permissions import IsCashier, IsClient, IsRecipient
from .serializers import (
    ArticleDetailSerializer,
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
        responses={201: ArticleSerializer(many=True)},
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
            OpenApiExample(
                "Successful creation response",
                value={
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
                },
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Invalid client ID",
                value={"client_id": ["Client with id 999 does not exist."]},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "User is not a client",
                value={"client_id": ["User with id 2 is not a Client."]},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Empty articles list",
                value={"articles": ["Articles list cannot be empty."]},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Too many articles",
                value={
                    "articles": [
                        "Cannot create more than 50 articles at once. "
                        "Received 75 articles. Please reduce the batch size."
                    ]
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Cashier has no associated shop",
                value={
                    "non_field_errors": ["Authenticated user does not have an associated shop."]
                },
                response_only=True,
                status_codes=["400"],
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


class ArticleGetListView(APIView):
    """
    API endpoint to retrieve articles paid by a user.
    Only accessible by authenticated users with CLIENT role.

    """

    permission_classes = [IsClient]

    @extend_schema(
        summary="Retrieve articles paid by user",
        description="""
        Allows authenticated users to retrieve all the articles they have paid and their statuses.

        **Permissions:**
        - User must be authenticated (JWT Cookie)
        - User must have CLIENT role
        """,
        responses={200: ArticleDetailSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Successful response with mixed statuses",
                value={
                    "count": 3,
                    "articles": [
                        {
                            "id": 1,
                            "barcode": 3017620422003,
                            "name": "Product Name",
                            "shop": {"id": 1, "name": "Carrefour City Centre"},
                            "status": "AVAILABLE",
                            "cart": None,
                        },
                        {
                            "id": 2,
                            "barcode": 3564700013151,
                            "name": "Another Product",
                            "shop": {"id": 1, "name": "Carrefour City Centre"},
                            "status": "ASSIGNED",
                            "cart": {"id": 5, "status": "ASSIGNED"},
                        },
                        {
                            "id": 3,
                            "barcode": 3270190207092,
                            "name": "Third Product",
                            "shop": {"id": 2, "name": "Monoprix Gare"},
                            "status": "COLLECTED",
                            "cart": {"id": 5, "status": "COLLECTED"},
                        },
                    ],
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
        tags=["Articles"],
    )
    def get(self, request):
        """
        Retrieve all articles purchased by the authenticated client.
        Returns articles with their status (AVAILABLE, ASSIGNED, COLLECTED).
        """
        articles = (
            Article.objects.filter(client__user=request.user)
            .select_related("shop", "cart")
            .order_by("-id")
        )

        serializer = ArticleDetailSerializer(articles, many=True)

        return Response(
            {"count": len(articles), "articles": serializer.data}, status=status.HTTP_200_OK
        )


class RecipientCartListView(APIView):
    """API endpoint for recipients to retrieve their carts."""

    permission_classes = [IsRecipient]

    @extend_schema(
        summary="Retrieve carts for authenticated recipient",
        description="""
        Allows authenticated recipients to retrieve all their assigned carts with articles.

        **Authentication**: Required (JWT Cookie)

        **Permission**: RECIPIENT role only

        **Features**:
        - Paginated results (20 carts per page by default)
        - Optional filtering by cart status (PENDING, ASSIGNED, COLLECTED)
        - Sorted from most recent to oldest (by cart ID)
        - Includes all articles for each cart with shop information

        **Query Parameters**:
        - `status` (optional): Filter by cart status (PENDING, ASSIGNED, or COLLECTED)
        - `page` (optional): Page number for pagination
        """,
        parameters=[
            {
                "name": "status",
                "in": "query",
                "description": "Filter carts by status",
                "required": False,
                "schema": {
                    "type": "string",
                    "enum": ["PENDING", "ASSIGNED", "COLLECTED"],
                },
            },
            {
                "name": "page",
                "in": "query",
                "description": "Page number",
                "required": False,
                "schema": {"type": "integer"},
            },
        ],
        responses={200: CartSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Successful paginated response with carts and articles",
                value={
                    "count": 42,
                    "next": "http://api.example.com/api/recipients/me/carts/?page=2",
                    "previous": None,
                    "results": [
                        {
                            "id": 5,
                            "shop": 1,
                            "shop_name": "Carrefour City Centre",
                            "recipient": 3,
                            "recipient_email": "recipient@example.com",
                            "recipient_name": "John Doe",
                            "status": "ASSIGNED",
                            "collected_at": None,
                            "articles": [
                                {
                                    "id": 1,
                                    "barcode": 3017620422003,
                                    "name": "Product Name",
                                    "shop": {"id": 1, "name": "Carrefour City Centre"},
                                    "status": "ASSIGNED",
                                    "cart": {"id": 5, "status": "ASSIGNED"},
                                },
                                {
                                    "id": 2,
                                    "barcode": 3564700013151,
                                    "name": "Another Product",
                                    "shop": {"id": 1, "name": "Carrefour City Centre"},
                                    "status": "ASSIGNED",
                                    "cart": {"id": 5, "status": "ASSIGNED"},
                                },
                            ],
                        }
                    ],
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Invalid status parameter",
                value={"status": ["Invalid status. Must be one of: PENDING, ASSIGNED, COLLECTED"]},
                response_only=True,
                status_codes=["400"],
            ),
        ],
        tags=["Carts"],
    )
    def get(self, request):
        """
        Retrieve all carts for the authenticated recipient.
        Supports optional filtering by status and includes pagination.
        """
        # Base queryset filtered by authenticated recipient
        carts = (
            Cart.objects.filter(recipient__user=request.user)
            .select_related("shop", "recipient__user")
            .prefetch_related("articles__shop")
            .order_by("-id")
        )

        # Optional status filtering
        status_param = request.query_params.get("status")
        if status_param:
            # Validate status parameter
            valid_statuses = [status.value for status in CartStatus]
            if status_param not in valid_statuses:
                return Response(
                    {"status": [f"Invalid status. Must be one of: {', '.join(valid_statuses)}"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Map status to underlying field conditions
            # Status is computed from recipient and collected_at fields:
            # - PENDING: recipient is None (won't match since we filter by recipient__user)
            # - ASSIGNED: recipient is not None AND collected_at is None
            # - COLLECTED: recipient is not None AND collected_at is not None
            if status_param == CartStatus.PENDING.value:
                # PENDING carts have no recipient, so they won't be in recipient's list
                carts = carts.filter(recipient__isnull=True)
            elif status_param == CartStatus.ASSIGNED.value:
                # ASSIGNED carts have recipient but no collected_at
                carts = carts.filter(collected_at__isnull=True)
            elif status_param == CartStatus.COLLECTED.value:
                # COLLECTED carts have both recipient and collected_at
                carts = carts.filter(collected_at__isnull=False)

        # Paginate results
        paginator = PageNumberPagination()
        paginated_carts = paginator.paginate_queryset(carts, request)

        # Serialize and return paginated response
        serializer = CartSerializer(paginated_carts, many=True)
        return paginator.get_paginated_response(serializer.data)


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
        - Recipient must exist
        - Cart must exist
        - Cart status must be "ASSIGNED"
        - Cashier can only collect carts from their shop
        - Cart must belong to the specified recipient

        **Actions**:
        - Updates cart status to "COLLECTED"
        - Sets collected_at timestamp
        """,
        request=None,
        responses={204: None},
        examples=[
            OpenApiExample(
                "Cart successfully collected",
                description="No content returned on success",
                value=None,
                response_only=True,
                status_codes=["204"],
            ),
            OpenApiExample(
                "Invalid cart status",
                value={
                    "status": (
                        "Cart must be in ASSIGNED status to be collected. Current status: PENDING"
                    )
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Cart does not belong to recipient",
                value={"recipient": "The cart does not belong to this recipient."},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Wrong shop",
                value={"shop": "You can only collect carts from your shop."},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Recipient not found",
                value={"error": "Recipient not found."},
                response_only=True,
                status_codes=["404"],
            ),
            OpenApiExample(
                "Cart not found",
                value={"error": "Cart not found."},
                response_only=True,
                status_codes=["404"],
            ),
        ],
        tags=["Carts"],
    )
    def patch(self, request, recipient_id, cart_id):
        """Handle PATCH request to mark cart as collected."""
        # Get the recipient or return 404
        try:
            recipient = Recipient.objects.select_related("user").get(user__pk=recipient_id)
        except Recipient.DoesNotExist:
            return Response(
                {"error": "Recipient not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get the cart or return 404
        try:
            cart = Cart.objects.select_related("shop", "recipient", "recipient__user").get(
                pk=cart_id
            )
        except Cart.DoesNotExist:
            return Response(
                {"error": "Cart not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate and update
        serializer = CartCollectSerializer(
            data={},
            context={"request": request, "cart": cart, "recipient": recipient},
        )

        if serializer.is_valid():
            serializer.update(cart, serializer.validated_data)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
