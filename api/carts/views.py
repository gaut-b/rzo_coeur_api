from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from api.enums import CartStatus
from api.models import Cart, Recipient
from api.shops.permissions import IsCashier

from .permissions import IsRecipient
from .serializers import CartCollectSerializer, CartSerializer


class RecipientCartListView(APIView):
    """API endpoint for recipients to retrieve their carts."""

    permission_classes = [IsRecipient]

    @extend_schema(
        summary="Retrieve carts for authenticated recipient",
        description="""
        Allows authenticated recipients to retrieve all their assigned carts
        with articles.

        **Authentication**: Required (JWT Cookie)

        **Permission**: RECIPIENT role only

        **Features**:
        - Paginated results (20 carts per page by default)
        - Optional filtering by cart status (PENDING, ASSIGNED, COLLECTED)
        - Sorted from most recent to oldest (by cart ID)
        - Includes all articles for each cart with shop information

        **Query Parameters**:
        - `status` (optional): Filter by cart status
        - `page` (optional): Page number for pagination
        """,
        parameters=[
            OpenApiParameter(
                name="status",
                location=OpenApiParameter.QUERY,
                description="Filter carts by status",
                required=False,
                type=str,
                enum=["PENDING", "ASSIGNED", "COLLECTED"],
            ),
            OpenApiParameter(
                name="page",
                location=OpenApiParameter.QUERY,
                description="Page number",
                required=False,
                type=int,
            ),
        ],
        responses={200: CartSerializer(many=True)},
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
            valid_statuses = [s.value for s in CartStatus]
            if status_param not in valid_statuses:
                return Response(
                    {"status": [f"Invalid status. Must be one of: " f"{', '.join(valid_statuses)}"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Map status to underlying field conditions:
            # - PENDING: recipient is None (won't match since we filter by
            #   recipient__user)
            # - ASSIGNED: recipient is not None AND collected_at is None
            # - COLLECTED: recipient is not None AND collected_at is not None
            if status_param == CartStatus.PENDING.value:
                carts = carts.filter(recipient__isnull=True)
            elif status_param == CartStatus.ASSIGNED.value:
                carts = carts.filter(collected_at__isnull=True)
            elif status_param == CartStatus.COLLECTED.value:
                carts = carts.filter(collected_at__isnull=False)

        # Paginate results
        paginator = PageNumberPagination()
        paginated_carts = paginator.paginate_queryset(carts, request)

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
        """,
        request=None,
        responses={204: None},
        tags=["Carts"],
    )
    def post(self, request, recipient_id, cart_id):
        """Handle POST request to mark cart as collected."""
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
            cart = Cart.objects.select_related("shop", "recipient", "recipient__user").get(pk=cart_id)
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


class CartDetailView(APIView):
    """
    Retrieve a cart by its ID.
    Only accessible by cashiers for carts from their shop.
    """

    permission_classes = [IsCashier]

    @extend_schema(
        summary="Retrieve cart by ID",
        description="""
        Retrieve a cart with its complete content by cart ID.

        **Authentication**: Required (JWT Cookie)

        **Permission**: CASHIER role only

        **Validations**:
        - Cart must exist
        - Cart must belong to the cashier's shop
        """,
        responses={
            200: CartSerializer,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        tags=["Carts"],
    )
    def get(self, request, cart_id):
        """Handle GET request to retrieve a cart by ID."""
        # Get the cart or return 404
        try:
            cart = Cart.objects.select_related("shop", "recipient__user").prefetch_related("articles").get(pk=cart_id)
        except Cart.DoesNotExist:
            return Response(
                {"error": "Cart not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify the cart belongs to the cashier's shop
        if cart.shop != request.user.cashier.shop:
            return Response(
                {"error": "You can only access carts from your shop."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)
