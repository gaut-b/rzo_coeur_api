import uuid

from django.core.files.storage import default_storage
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Article
from api.shops.permissions import IsCashier
from api.users.permissions import IsClient

from .serializers import (
    ArticleDetailSerializer,
    ArticleSerializer,
    BulkArticleCreateSerializer,
    PhotoUploadSerializer,
)


class ArticleCreateView(APIView):
    """
    API endpoint for bulk article creation.
    Only accessible by authenticated users with CASHIER role.

    POST /api/articles/
    Only POST requests are supported; all other HTTP methods will return 405.
    Request body:
    {
        "client_id": 1,
        "articles": [
            {"barcode": 3017620422003},
            {"barcode": 3564700013151}
        ]
    }

    Note: The shop_id is automatically retrieved from the authenticated
    cashier's shop.
    """

    permission_classes = [IsCashier]

    @extend_schema(
        summary="Create multiple articles in bulk",
        description="""
        Allows authenticated cashiers to create multiple articles at once by
        scanning a client's barcode followed by article barcodes.

        **Workflow:**
        1. Cashier scans the client's barcode (client_id)
        2. Cashier scans multiple article barcodes (up to 50 per request)
        3. All articles are created with cart=null and associated with the
           cashier's shop

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
        tags=["Articles"],
    )
    def post(self, request):
        """
        Create multiple articles in bulk.
        Validates input data and creates articles associated with a client and
        shop.
        """
        serializer = BulkArticleCreateSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            created_articles = serializer.save()
            response_serializer = ArticleSerializer(created_articles, many=True)

            return Response(
                {
                    "message": (f"Successfully created {len(created_articles)} articles."),
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
        Allows authenticated users to retrieve all the articles they have paid
        and their statuses.

        **Permissions:**
        - User must be authenticated (JWT Cookie)
        - User must have CLIENT role
        """,
        responses={200: ArticleDetailSerializer(many=True)},
        tags=["Articles"],
    )
    def get(self, request):
        """
        Retrieve all articles purchased by the authenticated client.
        Returns articles with their status (AVAILABLE, ASSIGNED, COLLECTED).
        """
        articles = Article.objects.filter(client__user=request.user).select_related("shop", "cart").order_by("-id")

        serializer = ArticleDetailSerializer(articles, many=True)

        return Response(
            {"count": len(articles), "articles": serializer.data},
            status=status.HTTP_200_OK,
        )


class ArticleBarcodeView(APIView):
    """
    Retrieve the first article stored in our database for a given barcode.

    Only accessible by authenticated Client users. This endpoint is intended
    to be called before creating a new article: if the barcode already exists
    in our database, the stored metadata (name, img_url, brand_label …) can
    be reused instead of requiring the user to enter them manually.

    GET /api/articles/barcode/<barcode>/
    """

    permission_classes = [IsClient]

    @extend_schema(
        summary="Get article by barcode from our database",
        description=(
            "Returns the first article found in our database for the given "
            "barcode. Intended as a fallback when a third-party product database "
            "returns no result: the client can reuse metadata already stored "
            "locally.\n\n"
            "**Permissions:** Client role required."
        ),
        parameters=[
            OpenApiParameter(
                name="barcode",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="EAN/UPC barcode number of the article.",
            )
        ],
        responses={200: ArticleSerializer, 404: None},
        tags=["Articles"],
    )
    def get(self, request, barcode: int):
        """
        Return the first article matching the given barcode.

        Parameters:
            request: The incoming HTTP request.
            barcode (int): The barcode value extracted from the URL path.

        Returns:
            Response: 200 with serialized article data, or 404 if not found.
        """
        article = Article.objects.filter(barcode=barcode).first()
        if article is None:
            return Response(
                {"detail": f"No article found with barcode {barcode}."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ArticleSerializer(article)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ArticlePhotoUploadView(APIView):
    """
    Upload a photo for an article and store it in object storage (MinIO/S3).

    Returns the public URL of the uploaded image so the client can store it
    in the ``img_url`` field when creating the article.

    Only accessible by authenticated Client users.

    POST /api/articles/photos/
    Content-Type: multipart/form-data
    """

    permission_classes = [IsClient]
    parser_classes = [MultiPartParser]

    @extend_schema(
        summary="Upload an article photo",
        description=(
            "Accepts a multipart image file (JPEG, PNG, or WebP, max 5 MB), "
            "stores it in the object storage bucket, and returns the public "
            "URL.\n\n"
            "**Workflow:** call this endpoint first to obtain a URL, then pass "
            "that URL as ``img_url`` when creating the article.\n\n"
            "**Permissions:** Client role required."
        ),
        request=PhotoUploadSerializer,
        responses={
            201: {
                "type": "object",
                "properties": {"url": {"type": "string", "format": "uri"}},
            },
            400: None,
        },
        tags=["Articles"],
    )
    def post(self, request):
        """
        Validate and store an uploaded image file.

        Generates a UUID-based filename to avoid collisions and path-injection
        attacks, then delegates storage to Django's ``default_storage`` backend
        (MinIO in Docker, local filesystem in tests).

        Parameters:
            request: The incoming HTTP request containing the multipart file.

        Returns:
            Response: 201 with ``{"url": "<public URL>"}`` on success,
                      or 400 with validation errors.
        """
        serializer = PhotoUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        image_file = serializer.validated_data["image"]

        # Build a collision-safe filename: <uuid>.<original_extension>
        original_extension = image_file.name.rsplit(".", 1)[-1].lower() if "." in image_file.name else "jpg"
        filename = f"articles/{uuid.uuid4().hex}.{original_extension}"

        saved_path = default_storage.save(filename, image_file)
        url = default_storage.url(saved_path)

        return Response({"url": url}, status=status.HTTP_201_CREATED)
