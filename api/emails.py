"""
api/emails.py — Transactional email helpers for the Les Réseaux du Coeur API.

All emails are sent in French.  Functions in this module should be called
from admin form saves and are intentionally kept free of Django request
dependencies where possible so that they can be tested in isolation.
"""

import logging
from urllib.parse import urlencode

from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import CustomUser

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

    context = {
        "user": user,
        "callback_url": callback_url,
        "reset_url": reset_url,
    }

    subject = "Bienvenue sur Les Réseaux du Coeur — Activez votre compte"
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
