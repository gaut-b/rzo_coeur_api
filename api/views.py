from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView, View
from django.http import HttpResponse
from .enums import CartStatus
from .models import Article, Cart, Recipient, Shop, SocialWorker
from .permissions import IsCashier, IsClient, IsRecipient
from django.contrib import messages
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from .serializers import (
    ArticleDetailSerializer,
    ArticleSerializer,
    BulkArticleCreateSerializer,
    CartCollectSerializer,
    CartSerializer,
    ShopSerializer,
)

from .enums import UserRole
from django.template import loader
from .forms import CreateCartForm
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin


class CreateCartView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Cart
    fields = ["shop"]
    form = CreateCartForm
    template = "api/add_cart.html"
    # specify where to redirect after a successful POST
    success_url = "/attri"
    login_url = "/attri/login"
    redirect_field_name = "attri"

    def has_permission(self):
        return self.request.user.is_authenticated and self.request.user.role == UserRole.SOCIAL_WORKER.value


    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "The cart was created successfully.")
        return super(CreateCartView, self).form_valid(form)


class AttributionsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    login_url = "/attri/login"
    redirect_field_name = "attri"

    def get_social_center(self, user):
        request_social_center="1"
        for s in SocialWorker.objects.all():
            if user == s.user:  # we're not going through this...FIXME
                request_social_center = s.social_center
        return request_social_center

    def get_shops(self, social_center):
        request_shops=[]
        for s in Shop.objects.all():
            if social_center == s.social_center:  # we're not going through this...FIXME
                request_shops.append(s)
        return request_shops
 
 
    def has_permission(self):
        return self.request.user.is_authenticated and self.request.user.role == UserRole.SOCIAL_WORKER.value

    def get(self, request):
        articles = Article.objects.all()
        paniers = Cart.objects.all()
        recipients = Recipient.objects.all()
        user = request.user
        filter_social_center = self.get_social_center(user)
        filter_shops=self.get_shops(filter_social_center)
        print(filter_social_center)
        print(filter_shops)
        context = {"articles": articles, "paniers": paniers, "recipients": recipients, "filter_social_center": filter_social_center, "filter_shops": filter_shops}
        """get a list of all scanned products"""
        template = loader.get_template("api/index.html")

        return HttpResponse(template.render(context, request))


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
                "Valid request with optional fields",
                value={
                    "client_id": 1,
                    "articles": [
                        {
                            "barcode": 3017620422003,
                            "name": "Coca-Cola 33cl",
                            "img_url": "https://example.com/product1.jpg",
                            "thumb_url": "https://example.com/thumb1.jpg",
                            "brand_label": "Coca-Cola",
                        },
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
                            "name": "Coca-Cola 33cl",
                            "barcode": 3017620422003,
                            "client": 1,
                            "shop": 1,
                            "cart": None,
                            "img_url": "https://example.com/product1.jpg",
                            "thumb_url": "https://example.com/thumb1.jpg",
                            "brand_label": "Coca-Cola",
                            "created_at": "2026-01-10T10:30:00Z",
                            "updated_at": "2026-01-10T10:30:00Z",
                        },
                        {
                            "id": 2,
                            "name": "KitKat",
                            "barcode": 3564700013151,
                            "client": 1,
                            "shop": 1,
                            "cart": None,
                            "img_url": "",
                            "thumb_url": "",
                            "brand_label": "Nestle",
                            "created_at": "2026-01-10T10:30:01Z",
                            "updated_at": "2026-01-10T10:30:01Z",
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
                value={"non_field_errors": ["Authenticated user does not have an associated shop."]},
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
                            "img_url": "https://example.com/product1.jpg",
                            "thumb_url": "https://example.com/thumb1.jpg",
                            "brand_label": "Coca-Cola",
                            "shop": {"id": 1, "name": "Carrefour City Centre"},
                            "status": "AVAILABLE",
                            "cart": None,
                            "created_at": "2026-01-10T10:30:00Z",
                            "updated_at": "2026-01-10T10:30:00Z",
                        },
                        {
                            "id": 2,
                            "barcode": 3564700013151,
                            "name": "Another Product",
                            "img_url": "",
                            "thumb_url": "",
                            "brand_label": "Nestle",
                            "shop": {"id": 1, "name": "Carrefour City Centre"},
                            "status": "ASSIGNED",
                            "cart": {"id": 5, "status": "ASSIGNED"},
                            "created_at": "2026-01-09T14:20:00Z",
                            "updated_at": "2026-01-09T14:20:00Z",
                        },
                        {
                            "id": 3,
                            "barcode": 3270190207092,
                            "name": "Third Product",
                            "img_url": "",
                            "thumb_url": "",
                            "brand_label": "",
                            "shop": {"id": 2, "name": "Monoprix Gare"},
                            "status": "COLLECTED",
                            "cart": {"id": 5, "status": "COLLECTED"},
                            "created_at": "2026-01-08T09:15:00Z",
                            "updated_at": "2026-01-08T09:15:00Z",
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
        articles = Article.objects.filter(client__user=request.user).select_related("shop", "cart").order_by("-id")

        serializer = ArticleDetailSerializer(articles, many=True)

        return Response({"count": len(articles), "articles": serializer.data}, status=status.HTTP_200_OK)


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
                                    "name": "Coca-Cola 33cl",
                                    "img_url": "https://example.com/product1.jpg",
                                    "thumb_url": "https://example.com/thumb1.jpg",
                                    "brand_label": "Coca-Cola",
                                },
                                {
                                    "id": 2,
                                    "barcode": 3564700013151,
                                    "name": "KitKat",
                                    "img_url": "",
                                    "thumb_url": "",
                                    "brand_label": "Nestle",
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
                value={"status": ("Cart must be in ASSIGNED status to be collected. Current status: PENDING")},
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

        **Returns**:
        - Cart details including all articles
        - Recipient information if assigned
        - Computed status (PENDING, ASSIGNED, or COLLECTED)
        """,
        responses={
            200: CartSerializer,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Cart successfully retrieved",
                value={
                    "id": 1,
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
                            "name": "Coca-Cola 33cl",
                            "img_url": "https://example.com/product1.jpg",
                            "thumb_url": "https://example.com/thumb1.jpg",
                            "brand_label": "Coca-Cola",
                        },
                        {
                            "id": 2,
                            "barcode": 3564700013151,
                            "name": "KitKat",
                            "img_url": "",
                            "thumb_url": "",
                            "brand_label": "Nestle",
                        },
                    ],
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Cart from different shop",
                value={"error": "You can only access carts from your shop."},
                response_only=True,
                status_codes=["403"],
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


class ShopDetailView(APIView):
    """API endpoint to retrieve a shop by ID."""

    @extend_schema(
        summary="Retrieve shop by ID",
        description="""
       Retrieve detailed information about a specific shop including its address and coordinates.

       **Authentication**: Not required

       **Features**:
       - Returns shop details with structured address
       - Includes geographic coordinates (latitude/longitude)
       - Returns full address as formatted string
       """,
        responses={200: ShopSerializer},
        examples=[
            OpenApiExample(
                "Shop details",
                value={
                    "id": 1,
                    "name": "Carrefour City Centre",
                    "full_address": "123 Rue de la République, 75001 Paris",
                    "street_number": "123",
                    "street_name": "Rue de la République",
                    "postal_code": "75001",
                    "city": "Paris",
                    "latitude": 48.8566,
                    "longitude": 2.3522,
                    "social_center": 1,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Shop not found",
                value={"error": "Shop not found."},
                response_only=True,
                status_codes=["404"],
            ),
        ],
        tags=["Shops"],
    )
    def get(self, request, shop_id):
        """Retrieve shop by ID."""
        try:
            shop = Shop.objects.get(pk=shop_id)
        except Shop.DoesNotExist:
            return Response(
                {"error": "Shop not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ShopSerializer(shop)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ShopListView(APIView):
    """API endpoint to list shops with optional proximity sorting."""

    @extend_schema(
        summary="List shops with optional proximity sorting",
        description="""
       Retrieve a paginated list of shops. Can optionally sort by distance from a given GPS
       location.

       **Authentication**: Not required

       **Features**:
       - Paginated results (default page size from settings)
       - Optional proximity-based sorting using GPS coordinates
       - Returns shop details with address and coordinates
       - If no coordinates provided, shops are sorted by ID

       **Query Parameters**:
       - `latitude` (optional): Latitude for proximity sorting (decimal degrees, WGS84)
       - `longitude` (optional): Longitude for proximity sorting (decimal degrees, WGS84)
       - `page` (optional): Page number for pagination

       **Note**: Both latitude and longitude must be provided together for proximity sorting.
       """,
        parameters=[
            {
                "name": "latitude",
                "in": "query",
                "description": "Latitude in decimal degrees (e.g., 48.8566 for Paris)",
                "required": False,
                "schema": {"type": "number", "format": "float"},
            },
            {
                "name": "longitude",
                "in": "query",
                "description": "Longitude in decimal degrees (e.g., 2.3522 for Paris)",
                "required": False,
                "schema": {"type": "number", "format": "float"},
            },
            {
                "name": "page",
                "in": "query",
                "description": "Page number",
                "required": False,
                "schema": {"type": "integer"},
            },
        ],
        responses={200: ShopSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Paginated shops list",
                value={
                    "count": 15,
                    "next": "http://api.example.com/api/shops/?page=2",
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "name": "Carrefour City Centre",
                            "full_address": "123 Rue de la République, 75001 Paris",
                            "street_number": "123",
                            "street_name": "Rue de la République",
                            "postal_code": "75001",
                            "city": "Paris",
                            "latitude": 48.8566,
                            "longitude": 2.3522,
                            "social_center": 1,
                        },
                        {
                            "id": 2,
                            "name": "Monoprix Gare",
                            "full_address": "45 Avenue de la Gare, 75002 Paris",
                            "street_number": "45",
                            "street_name": "Avenue de la Gare",
                            "postal_code": "75002",
                            "city": "Paris",
                            "latitude": 48.8606,
                            "longitude": 2.3376,
                            "social_center": 1,
                        },
                    ],
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Invalid coordinates",
                value={"coordinates": ("Both latitude and longitude must be provided for proximity sorting.")},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Invalid coordinate values",
                value={"latitude": "Invalid latitude value."},
                response_only=True,
                status_codes=["400"],
            ),
        ],
        tags=["Shops"],
    )
    def get(self, request):
        """
        List all shops with optional proximity-based sorting.
        If latitude and longitude are provided, shops are sorted by distance.
        """
        # Get query parameters
        latitude = request.query_params.get("latitude")
        longitude = request.query_params.get("longitude")

        # Validate coordinate parameters - only one provided is an error
        if (latitude is None) != (longitude is None):
            return Response(
                {"coordinates": ("Both latitude and longitude must be provided for proximity sorting.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Base queryset
        shops = Shop.objects.all()

        # Apply proximity sorting if coordinates provided
        if latitude and longitude:
            try:
                lat = float(latitude)
                lon = float(longitude)

                # Validate coordinate ranges
                if not (-90 <= lat <= 90):
                    return Response(
                        {"latitude": "Latitude must be between -90 and 90 degrees."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not (-180 <= lon <= 180):
                    return Response(
                        {"longitude": "Longitude must be between -180 and 180 degrees."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Create point for the given coordinates (longitude first in PostGIS)
                user_location = Point(lon, lat, srid=4326)

                # Annotate with distance and order by it
                shops = shops.annotate(distance=Distance("location", user_location)).order_by("distance")

            except (ValueError, TypeError):
                return Response(
                    {"coordinates": "Invalid coordinate values. Must be valid numbers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # Default ordering by ID if no coordinates provided
            shops = shops.order_by("id")

        # Paginate results
        paginator = PageNumberPagination()
        paginated_shops = paginator.paginate_queryset(shops, request)

        # Serialize and return paginated response
        serializer = ShopSerializer(paginated_shops, many=True)
        return paginator.get_paginated_response(serializer.data)
