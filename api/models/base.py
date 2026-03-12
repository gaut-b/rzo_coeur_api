from django.contrib.gis.db import models as gis_models
from django.db import models


class AddressLocationMixin(models.Model):
    """
    Mixin for models with structured address fields and geographic location.
    Provides common fields and properties for address handling.
    """

    # Structured address fields (filled by geocoding from user input)
    postal_code = models.CharField(max_length=10, blank=True, help_text="Postal code")
    street_number = models.CharField(max_length=20, blank=True, help_text="Street number")
    street_name = models.CharField(max_length=200, blank=True, help_text="Street name")
    city = models.CharField(max_length=100, blank=True, help_text="City")

    # Geographic location (PostGIS)
    location = gis_models.PointField(
        geography=True,
        null=True,
        blank=True,
        help_text="Geographic coordinates (longitude, latitude)",
        srid=4326,  # WGS84 coordinate system
    )

    class Meta:
        abstract = True

    @property
    def latitude(self):
        """Get latitude from location point."""
        return self.location.y if self.location else None

    @property
    def longitude(self):
        """Get longitude from location point."""
        return self.location.x if self.location else None
