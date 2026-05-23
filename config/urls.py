"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from auth_kit.views import AuthKitUIView
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from api.auth_views import (
    AndroidAssetLinksView,
    AppleAppSiteAssociationView,
    AppResetPasswordFallbackView,
    AppVerifyEmailFallbackView,
    CustomPasswordResetCompleteView,
    CustomPasswordResetConfirmView,
    CustomPasswordResetView,
)
from api.carts.admin import cart_attrib_admin_site
from api.shops.admin import shop_admin_site
from api.social.admin import social_admin_site

# Password reset views shared across all custom admin sites (social-admin,
# shop-admin, cart-admin).  Django's built-in views handle token generation,
# validation and expiry; we only need to supply templates.
urlpatterns = [
    # Universal Links — served at the domain root, must not redirect.
    path(
        ".well-known/apple-app-site-association",
        AppleAppSiteAssociationView.as_view(),
        name="apple-app-site-association",
    ),
    path(
        ".well-known/assetlinks.json",
        AndroidAssetLinksView.as_view(),
        name="android-asset-links",
    ),
    # Fallback web pages for deep links opened outside the mobile app.
    path(
        "app/reset-password/",
        AppResetPasswordFallbackView.as_view(),
        name="app-reset-password",
    ),
    path(
        "app/verify-email/",
        AppVerifyEmailFallbackView.as_view(),
        name="app-verify-email",
    ),
    path("admin/", admin.site.urls),
    path("shop-admin/", shop_admin_site.urls),
    path("social-admin/", social_admin_site.urls),
    path("cart-admin/", cart_attrib_admin_site.urls),
    path("api/auth/", include("auth_kit.urls")),
    path("api/", include("api.urls")),
    # Shared password-reset flow (used by the "Mot de passe oublié?" link on
    # every custom admin login page).
    path(
        "auth/password_reset/",
        CustomPasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.txt",
            html_email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
            success_url="/auth/password_reset/done/",
        ),
        name="password_reset",
    ),
    path(
        "auth/password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "auth/reset/<uidb64>/<token>/",
        CustomPasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url="/auth/reset/done/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "auth/reset/done/",
        CustomPasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]

# Include UI testing view only in DEBUG mode
if settings.DEBUG:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
        path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
        path("api/auth/ui/", AuthKitUIView.as_view(), name="auth_kit_ui"),
    ]
