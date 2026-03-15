from django import forms
from django.contrib import admin
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.gis.geos import Point
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache

from .models import CustomUser


class AddressLocationAdminForm(forms.ModelForm):
    """Base form for models with address and location fields."""

    address = forms.CharField(
        required=False,
        max_length=200,
        help_text="Start typing to search for an address",
        widget=forms.TextInput(attrs={"placeholder": "Search address..."}),
    )

    # Virtual fields for latitude/longitude
    latitude = forms.DecimalField(
        required=False,
        max_digits=9,
        decimal_places=6,
        widget=forms.NumberInput(attrs={"step": "0.000001"}),
    )
    longitude = forms.DecimalField(
        required=False,
        max_digits=9,
        decimal_places=6,
        widget=forms.NumberInput(attrs={"step": "0.000001"}),
    )

    class Meta:
        fields = [
            "address",
            "postal_code",
            "street_number",
            "street_name",
            "city",
            "latitude",
            "longitude",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.pk:
            return
        # Pre-fill the address field with current structured address
        address_parts = filter(None, [self.instance.street_number, self.instance.street_name])
        address_line = " ".join(address_parts)

        if self.instance.postal_code and self.instance.city:
            if address_line:
                self.initial["address"] = f"{address_line}, {self.instance.postal_code} {self.instance.city}"
            else:
                self.initial["address"] = f"{self.instance.postal_code} {self.instance.city}"
        elif address_line:
            self.initial["address"] = address_line

        # Pre-fill latitude/longitude from location Point
        if self.instance.location:
            self.initial["latitude"] = self.instance.location.y
            self.initial["longitude"] = self.instance.location.x

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Create Point from latitude/longitude if both are provided
        latitude = self.cleaned_data.get("latitude")
        longitude = self.cleaned_data.get("longitude")

        if latitude is not None and longitude is not None:
            instance.location = Point(float(longitude), float(latitude), srid=4326)

        if commit:
            instance.save()
        return instance


class AddressLocationAdminMixin:
    """Mixin for admin classes with address and location display methods."""

    def full_address(self, obj):
        """Display the full address constructed from structured fields."""
        parts = []
        if obj.street_number:
            parts.append(obj.street_number)
        if obj.street_name:
            parts.append(obj.street_name)
        address_line = " ".join(parts) if parts else ""

        if obj.postal_code and obj.city:
            if address_line:
                return f"{address_line}, {obj.postal_code} {obj.city}"
            return f"{obj.postal_code} {obj.city}"
        elif address_line:
            return address_line
        return "-"

    full_address.short_description = "Address"

    def has_coordinates(self, obj, *args, **kwargs):
        """Display whether the object has GPS coordinates."""
        if obj.latitude and obj.longitude:
            return format_html('<span style="color: green;">✓</span>', *args, **kwargs)
        return format_html('<span style="color: red;">✗</span>', *args, **kwargs)

    has_coordinates.short_description = "GPS"

    def display_coordinates(self, obj, *args, **kwargs):
        """Display GPS coordinates in a readable format."""
        if obj.latitude and obj.longitude:
            return format_html(
                "<strong>Latitude:</strong> {}<br><strong>Longitude:</strong> {}",
                obj.latitude,
                obj.longitude,
            )
        return "No GPS coordinates"

    display_coordinates.short_description = "GPS Coordinates"


class CustomAdminSite(admin.AdminSite):
    """
    Base custom admin site with reusable login logic that doesn't require is_staff.
    Subclasses must implement check_user_permission() to define role-specific access.
    """

    login_template = "admin/custom_admin_login.html"

    def check_user_permission(self, user):
        """
        Check if user has permission to access this admin site.
        Must be implemented by subclasses.

        Returns:
            bool: True if user has permission, False otherwise
        """
        raise NotImplementedError("Subclasses must implement check_user_permission()")

    def get_permission_denied_message(self):
        """
        Get the error message to display when user doesn't have permission.
        Can be overridden by subclasses for custom messages.
        """
        return "You do not have permission to access this area."

    @method_decorator(never_cache)
    def login(self, request, extra_context=None):
        """
        Custom login that doesn't require is_staff.
        Displays the login form and handles the login action.
        """
        if request.method == "POST":
            username = request.POST.get("username")
            password = request.POST.get("password")

            # Authenticate user
            user = authenticate(request, username=username, password=password)

            if user is not None and user.is_active:
                # Re-fetch with role profiles to avoid N+1 in
                # check_user_permission
                user = CustomUser.objects.select_related(
                    "client", "socialworker", "recipient", "cashier"
                ).get(pk=user.pk)
                # Check if user has the required role
                if self.check_user_permission(user):
                    auth_login(request, user)
                    # Validate and redirect to the page they were trying to
                    # access or the index
                    next_url = request.GET.get("next", request.POST.get("next", ""))
                    if next_url and url_has_allowed_host_and_scheme(
                        url=next_url,
                        allowed_hosts={request.get_host()},
                        require_https=request.is_secure(),
                    ):
                        return redirect(next_url)
                    else:
                        return redirect(reverse("admin:index", current_app=self.name))
                else:
                    # User doesn't have the required role
                    context = {
                        "title": f"{self.site_title} Login",
                        "site_title": self.site_title,
                        "site_header": self.site_header,
                        "error_message": self.get_permission_denied_message(),
                        "username": username,
                    }
                    return render(request, self.login_template, context)
            else:
                # Invalid credentials
                context = {
                    "title": f"{self.site_title} Login",
                    "site_title": self.site_title,
                    "site_header": self.site_header,
                    "error_message": ("Please enter a correct email and password."),
                    "username": username,
                }
                return render(request, self.login_template, context)

        # GET request - show login form
        context = {
            "title": f"{self.site_title} Login",
            "site_title": self.site_title,
            "site_header": self.site_header,
            "site": self,
            "next": request.GET.get("next", ""),
        }
        if extra_context:
            context.update(extra_context)

        return render(request, self.login_template, context)

    def has_permission(self, request):
        """
        Allow access to users who pass the role-specific check.
        Does NOT require is_staff=True.

        The resolved role is cached in the Django session so that only the
        first request within a login session hits the database.  Subsequent
        requests inject ``_cached_role`` onto ``request.user`` directly so
        that the ``role`` property returns immediately without any extra
        query.
        """
        if not (request.user.is_active and request.user.is_authenticated):
            return False

        # Session key is scoped to this admin site so that users who
        # access multiple admin sites each get their own cache entry.
        session_key = f"_role_cache_{self.name}"

        if session_key in request.session:
            # Restore the cached role onto the user object so that
            # check_user_permission → user.role never touches the DB.
            request.user._cached_role = request.session[session_key] or None
            return self.check_user_permission(request.user)

        # First access in this session: fetch with select_related and cache.
        user = CustomUser.objects.select_related(
            "client", "socialworker", "recipient", "cashier"
        ).get(pk=request.user.pk)
        # Store as empty string instead of None so the key is falsy but
        # present.
        request.session[session_key] = user.role or ""
        return self.check_user_permission(user)
