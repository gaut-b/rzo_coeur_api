from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
)
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Shop

from .serializers import ShopSerializer


class ShopDetailView(APIView):
    """API endpoint to retrieve a shop by ID."""

    @extend_schema(
        summary="Retrieve shop by ID",
        description="""
       Retrieve detailed information about a specific shop including its
       address and coordinates.

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
       Retrieve a paginated list of shops. Can optionally sort by distance
       from a given GPS location.

       **Authentication**: Not required

       **Features**:
       - Paginated results (default page size from settings)
       - Optional proximity-based sorting using GPS coordinates
       - Returns shop details with address and coordinates
       - If no coordinates provided, shops are sorted by ID

       **Query Parameters**:
       - `latitude` (optional): Latitude for proximity sorting
         (decimal degrees, WGS84)
       - `longitude` (optional): Longitude for proximity sorting
         (decimal degrees, WGS84)
       - `page` (optional): Page number for pagination

       **Note**: Both latitude and longitude must be provided together for
       proximity sorting.
       """,
        parameters=[
            OpenApiParameter(
                name="latitude",
                location=OpenApiParameter.QUERY,
                description=("Latitude in decimal degrees (e.g., 48.8566 for Paris)"),
                required=False,
                type=float,
            ),
            OpenApiParameter(
                name="longitude",
                location=OpenApiParameter.QUERY,
                description=("Longitude in decimal degrees (e.g., 2.3522 for Paris)"),
                required=False,
                type=float,
            ),
            OpenApiParameter(
                name="page",
                location=OpenApiParameter.QUERY,
                description="Page number",
                required=False,
                type=int,
            ),
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
                            "full_address": ("123 Rue de la République, 75001 Paris"),
                            "street_number": "123",
                            "street_name": "Rue de la République",
                            "postal_code": "75001",
                            "city": "Paris",
                            "latitude": 48.8566,
                            "longitude": 2.3522,
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
        ],
        tags=["Shops"],
    )
    def get(self, request):
        """
        List all shops with optional proximity-based sorting.
        If latitude and longitude are provided, shops are sorted by distance.
        """
        latitude = request.query_params.get("latitude")
        longitude = request.query_params.get("longitude")

        # Only one coordinate provided is an error
        if (latitude is None) != (longitude is None):
            return Response(
                {"coordinates": ("Both latitude and longitude must be provided for proximity sorting.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shops = Shop.objects.all()

        if latitude and longitude:
            try:
                lat = float(latitude)
                lon = float(longitude)

                if not (-90 <= lat <= 90):
                    return Response(
                        {"latitude": ("Latitude must be between -90 and 90 degrees.")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not (-180 <= lon <= 180):
                    return Response(
                        {"longitude": ("Longitude must be between -180 and 180 degrees.")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # PostGIS expects (longitude, latitude) order
                user_location = Point(lon, lat, srid=4326)
                shops = shops.annotate(distance=Distance("location", user_location)).order_by("distance")

            except ValueError:
                return Response(
                    {"coordinates": "Invalid coordinate values. Must be valid numbers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            shops = shops.order_by("id")

        paginator = PageNumberPagination()
        paginated_shops = paginator.paginate_queryset(shops, request)
        serializer = ShopSerializer(paginated_shops, many=True)
        return paginator.get_paginated_response(serializer.data)
