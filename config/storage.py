"""
Custom Django storage backends.

MinIOPublicStorage wraps S3Boto3Storage so that files are uploaded via the
internal Docker endpoint (AWS_S3_ENDPOINT_URL = http://minio:9000) while the
URLs returned to clients use the publicly reachable address defined by the
MINIO_PUBLIC_URL environment variable.

This decouples the internal service topology from the public URL, which is
essential when MinIO is not directly exposed on the internet and all traffic
is routed through a reverse proxy (e.g. nginx) under a sub-path like
/storage/.

Example:
    Internal upload URL : http://minio:9000/articles-photos/articles/uuid.jpg
    Public client URL   : http://localhost/storage/articles-photos/articles/uuid.jpg
"""

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class MinIOPublicStorage(S3Boto3Storage):
    """
    S3Boto3Storage subclass that rewrites generated URLs.

    Uploads use the internal AWS_S3_ENDPOINT_URL (the Docker service name).
    The url() method replaces that internal base with MINIO_PUBLIC_URL so that
    the URL returned to the client is publicly reachable.
    """

    def url(self, name: str, parameters=None, expire=None, http_method=None) -> str:
        """
        Return the public URL for *name*.

        Replaces the internal endpoint + bucket prefix with the value of
        ``settings.MINIO_PUBLIC_URL``.  Falls back to the raw boto3 URL if
        ``MINIO_PUBLIC_URL`` is not configured.

        Parameters:
            name: The storage key (relative path inside the bucket).
            parameters: Extra query parameters forwarded to boto3.
            expire: Presigned-URL expiry — not used for public buckets.
            http_method: HTTP method hint forwarded to boto3.

        Returns:
            str: Publicly accessible URL for the stored object.
        """
        internal_url: str = super().url(name, parameters=parameters, expire=expire, http_method=http_method)

        public_base: str = getattr(settings, "MINIO_PUBLIC_URL", "").rstrip("/")
        if not public_base:
            # MINIO_PUBLIC_URL not set — return the boto3 URL as-is
            return internal_url

        # Internal URL pattern (path-style): http://minio:9000/<bucket>/<key>
        internal_base = f"{settings.AWS_S3_ENDPOINT_URL.rstrip('/')}/{settings.AWS_STORAGE_BUCKET_NAME}"
        return internal_url.replace(internal_base, public_base, 1)
