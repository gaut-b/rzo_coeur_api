"""
api/emails.py — Transactional email helpers for the Le réSOS du coeur API.

All emails are sent in French.  Functions in this module should be called
from admin form saves and are intentionally kept free of Django request
dependencies where possible so that they can be tested in isolation.
"""

import logging
from urllib.parse import urlencode

from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _

from .models import Cart, CustomUser

logger = logging.getLogger(__name__)


def send_account_welcome_email(
    user: CustomUser,
    callback_url: str,
    request,
) -> None:
    """
    Send a welcome email to a newly created user.

    The email (in French) contains:
    - A greeting with the user's name.
    - The URL of the admin login page specific to their role.
    - A one-time password-setup link (valid for 24 hours, as configured by
      PASSWORD_RESET_TIMEOUT in settings).

    Parameters
    ----------
    user:
        The newly created CustomUser instance.
    callback_url:
        The destination to redirect to after the password has been set.
        Forwarded verbatim as the ``callbackUrl`` query parameter on the
        one-time reset link.  May be a relative path
        (e.g. ``/social-admin/login/``) or a whitelisted deep link
        (e.g. ``rzo://activate``).
    request:
        The current Django HttpRequest, used to build the absolute reset URL.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_path = f"/auth/reset/{uid}/{token}/?{urlencode({'callbackUrl': callback_url})}"
    reset_url = request.build_absolute_uri(reset_path)
    logo_url = request.build_absolute_uri(static("logo.png"))

    context = {
        "user": user,
        "callback_url": callback_url,
        "reset_url": reset_url,
        "logo_url": logo_url,
    }

    subject = _("Bienvenue sur Le réSOS du coeur — Activez votre compte")
    html_body = render_to_string("emails/welcome_email.html", context)

    try:
        email = EmailMessage(
            subject=subject,
            body=html_body,
            to=[user.email],
        )
        email.content_subtype = "html"
        email.send()
    except Exception:
        # Do not let an email failure prevent account creation.  Log the
        # error so it can be investigated, but swallow the exception.
        logger.exception(
            "Failed to send welcome email to %s (user pk=%s)",
            user.email,
            user.pk,
        )


def send_cart_available_email(cart: Cart, request) -> None:
    """
    Send a notification email to a recipient informing them that a basket
    is available for pick-up in a shop.

    The email (in French) contains:
    - A greeting with the recipient's name.
    - The list of articles in the basket (name and brand label when present).
    - The shop name and address where the basket can be collected.

    Parameters
    ----------
    cart:
        The Cart instance to notify about.  Must have a non-null recipient.
    request:
        The current Django HttpRequest, used to build absolute URLs
        (logo, etc.).

    Raises
    ------
    ValueError
        If the cart has no recipient assigned.
    """
    if cart.recipient is None:
        raise ValueError(f"Cannot send notification for cart #{cart.pk}: no recipient assigned.")

    articles = cart.articles.order_by("name").select_related()
    logo_url = request.build_absolute_uri(static("logo.png"))
    recipient_user = cart.recipient.user

    context = {
        "cart": cart,
        "articles": articles,
        "shop": cart.shop,
        "recipient": recipient_user,
        "logo_url": logo_url,
    }

    subject = _("Un panier est disponible pour vous — Le réSOS du coeur")
    html_body = render_to_string("emails/cart_available_email.html", context)

    try:
        email = EmailMessage(
            subject=subject,
            body=html_body,
            to=[recipient_user.email],
        )
        email.content_subtype = "html"
        email.send()
    except Exception:
        logger.exception(
            "Failed to send cart available email to %s (cart pk=%s)",
            recipient_user.email,
            cart.pk,
        )
        raise
