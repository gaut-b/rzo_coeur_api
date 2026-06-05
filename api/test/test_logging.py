"""
Unit tests for the logging infrastructure.

Covers:
  - ``sanitize_dict``  — sensitive field redaction, deep nesting, lists,
                         original dict immutability.
  - ``sanitize_body``  — JSON parsing, multipart placeholder, empty body,
                         truncation, invalid JSON, plain text.
  - ``sanitize_structlog_processor`` — top-level key redaction, passthrough
                                        for non-sensitive keys.
  - ``RequestBodyLoggingMiddleware`` — JSON body logged, multipart noted,
                                       static paths skipped, empty body skipped.
"""

import json

from django.test import RequestFactory, TestCase
from structlog.testing import capture_logs

from api.middleware import RequestBodyLoggingMiddleware
from config.log_sanitizer import (
    MAX_BODY_LOG_SIZE,
    REDACTED,
    sanitize_body,
    sanitize_dict,
    sanitize_structlog_processor,
)

# ---------------------------------------------------------------------------
# sanitize_dict
# ---------------------------------------------------------------------------


class SanitizeDictTests(TestCase):
    """Tests for ``sanitize_dict``."""

    def test_redacts_password(self):
        """A ``password`` key is replaced with REDACTED."""
        result = sanitize_dict({"username": "alice", "password": "s3cr3t"})
        self.assertEqual(result["username"], "alice")
        self.assertEqual(result["password"], REDACTED)

    def test_redacts_token_and_refresh(self):
        """JWT-related keys are redacted."""
        result = sanitize_dict({"access": "abc", "refresh": "xyz"})
        self.assertEqual(result["access"], REDACTED)
        self.assertEqual(result["refresh"], REDACTED)

    def test_leaves_non_sensitive_fields_unchanged(self):
        """Non-sensitive fields pass through untouched."""
        result = sanitize_dict({"email": "a@b.com", "name": "Bob"})
        self.assertEqual(result["email"], REDACTED)
        self.assertEqual(result["name"], "Bob")

    def test_recurses_into_nested_dict(self):
        """Sensitive keys nested inside a dict are also redacted."""
        result = sanitize_dict({"user": {"password": "secret", "email": "a@b.com"}})
        self.assertEqual(result["user"]["password"], REDACTED)
        self.assertEqual(result["user"]["email"], REDACTED)

    def test_recurses_into_list_values(self):
        """Dicts nested inside list values are sanitized."""
        result = sanitize_dict({"items": [{"token": "t1"}, {"name": "ok"}]})
        self.assertEqual(result["items"][0]["token"], REDACTED)
        self.assertEqual(result["items"][1]["name"], "ok")

    def test_does_not_mutate_original(self):
        """The input dict is never modified."""
        original = {"password": "secret"}
        sanitize_dict(original)
        self.assertEqual(original["password"], "secret")

    def test_empty_dict(self):
        """An empty dict returns an empty dict."""
        self.assertEqual(sanitize_dict({}), {})

    def test_case_insensitive_key_matching(self):
        """Keys are matched case-insensitively."""
        result = sanitize_dict({"PASSWORD": "secret", "Token": "abc"})
        self.assertEqual(result["PASSWORD"], REDACTED)
        self.assertEqual(result["Token"], REDACTED)

    def test_redacts_email_key_variants(self):
        """Common email field variants are redacted."""
        result = sanitize_dict(
            {
                "user_email": "a@b.com",
                "recipient_email": "c@d.com",
                "email_address": "e@f.com",
                "email_template": "welcome",
            }
        )
        self.assertEqual(result["user_email"], REDACTED)
        self.assertEqual(result["recipient_email"], REDACTED)
        self.assertEqual(result["email_address"], REDACTED)
        self.assertEqual(result["email_template"], "welcome")


# ---------------------------------------------------------------------------
# sanitize_body
# ---------------------------------------------------------------------------


class SanitizeBodyTests(TestCase):
    """Tests for ``sanitize_body``."""

    def test_returns_none_for_empty_body(self):
        """Empty bytes returns None."""
        self.assertIsNone(sanitize_body(b"", "application/json"))

    def test_json_body_sanitized(self):
        """JSON body is parsed and sensitive fields are redacted."""
        body = json.dumps({"email": "a@b.com", "password": "secret"}).encode()
        result = sanitize_body(body, "application/json")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["password"], REDACTED)
        self.assertEqual(result["email"], REDACTED)

    def test_json_body_nested_sanitized(self):
        """Nested sensitive fields in JSON body are redacted."""
        body = json.dumps({"user": {"token": "abc", "name": "Alice"}}).encode()
        result = sanitize_body(body, "application/json")
        self.assertEqual(result["user"]["token"], REDACTED)
        self.assertEqual(result["user"]["name"], "Alice")

    def test_multipart_body_returns_placeholder(self):
        """Multipart bodies always return the placeholder string."""
        result = sanitize_body(b"binary content", "multipart/form-data; boundary=xxx")
        self.assertEqual(result, "[multipart - file upload]")

    def test_invalid_json_returns_placeholder(self):
        """Malformed JSON returns ``[invalid JSON body]``."""
        result = sanitize_body(b"{not valid json", "application/json")
        self.assertEqual(result, "[invalid JSON body]")

    def test_json_body_truncated_when_too_large(self):
        """JSON bodies exceeding MAX_BODY_LOG_SIZE are truncated."""
        big_value = "x" * (MAX_BODY_LOG_SIZE + 500)
        body = json.dumps({"data": big_value}).encode()
        result = sanitize_body(body, "application/json")
        self.assertIsInstance(result, str)
        self.assertIn("[TRUNCATED]", result)

    def test_plain_text_body_returned(self):
        """Non-JSON content types are decoded and returned as a string."""
        result = sanitize_body(b"hello world", "text/plain")
        self.assertEqual(result, "hello world")

    def test_plain_text_truncated_when_too_large(self):
        """Plain text bodies exceeding MAX_BODY_LOG_SIZE are truncated."""
        big_body = ("A" * (MAX_BODY_LOG_SIZE + 100)).encode()
        result = sanitize_body(big_body, "text/plain")
        self.assertIsInstance(result, str)
        self.assertIn("[TRUNCATED]", result)

    def test_content_type_with_charset(self):
        """Content-Type with charset suffix is still recognised as JSON."""
        body = json.dumps({"password": "pw"}).encode()
        result = sanitize_body(body, "application/json; charset=utf-8")
        self.assertEqual(result["password"], REDACTED)

    def test_json_list_root_is_sanitized(self):
        """List-root JSON payloads are sanitized recursively."""
        body = json.dumps(
            [
                {"email": "a@b.com", "password": "secret"},
                {"token": "abc", "name": "ok"},
            ]
        ).encode()
        result = sanitize_body(body, "application/json")
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["email"], REDACTED)
        self.assertEqual(result[0]["password"], REDACTED)
        self.assertEqual(result[1]["token"], REDACTED)
        self.assertEqual(result[1]["name"], "ok")

    def test_form_urlencoded_body_is_sanitized(self):
        """application/x-www-form-urlencoded bodies are parsed and redacted."""
        body = b"email=a%40b.com&password=secret&note=hello"
        result = sanitize_body(body, "application/x-www-form-urlencoded")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["email"], REDACTED)
        self.assertEqual(result["password"], REDACTED)
        self.assertEqual(result["note"], "hello")


# ---------------------------------------------------------------------------
# sanitize_structlog_processor
# ---------------------------------------------------------------------------


class SanitizeStructlogProcessorTests(TestCase):
    """Tests for ``sanitize_structlog_processor``."""

    def test_redacts_sensitive_top_level_key(self):
        """Top-level sensitive keys in the event dict are redacted."""
        event_dict = {"event": "user_login", "password": "pw", "username": "bob"}
        result = sanitize_structlog_processor(None, None, event_dict)
        self.assertEqual(result["password"], REDACTED)
        self.assertEqual(result["username"], "bob")
        self.assertEqual(result["event"], "user_login")

    def test_passes_through_non_sensitive_keys(self):
        """Non-sensitive keys are left unchanged."""
        event_dict = {"event": "ok", "shop_id": 42}
        result = sanitize_structlog_processor(None, None, event_dict)
        self.assertEqual(result["shop_id"], 42)

    def test_returns_event_dict(self):
        """The processor returns the (modified) event dict."""
        event_dict = {"event": "test"}
        result = sanitize_structlog_processor(None, None, event_dict)
        self.assertIs(result, event_dict)

    def test_redacts_sensitive_email_key_variants(self):
        """Structured log email variant fields are redacted."""
        event_dict = {
            "event": "cart_available_email",
            "recipient_email": "beneficiary@example.com",
            "user_email": "user@example.com",
            "email_template": "cart_available",
        }
        result = sanitize_structlog_processor(None, None, event_dict)
        self.assertEqual(result["recipient_email"], REDACTED)
        self.assertEqual(result["user_email"], REDACTED)
        self.assertEqual(result["email_template"], "cart_available")


# ---------------------------------------------------------------------------
# RequestBodyLoggingMiddleware
# ---------------------------------------------------------------------------


def _noop_response(request):
    """Minimal get_response callable for middleware tests."""
    from django.http import HttpResponse

    return HttpResponse()


class RequestBodyLoggingMiddlewareTests(TestCase):
    """Tests for ``RequestBodyLoggingMiddleware``."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = RequestBodyLoggingMiddleware(_noop_response)

    def test_json_body_is_logged(self):
        """A JSON request body is captured and logged at INFO level."""
        payload = {"barcode": 123456, "name": "Biscuits"}
        request = self.factory.post(
            "/api/articles/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        with capture_logs() as logs:
            self.middleware(request)

        body_logs = [e for e in logs if e.get("event") == "request_body"]
        self.assertEqual(len(body_logs), 1)
        self.assertEqual(body_logs[0]["body"]["barcode"], 123456)

    def test_error_response_logs_body_and_detail(self):
        """Error responses keep request_body and add response_error detail."""
        from rest_framework.response import Response

        middleware = RequestBodyLoggingMiddleware(
            lambda request: Response(
                {"detail": "Invalid payload", "password": "secret"},
                status=400,
            )
        )
        payload = {"email": "a@b.com", "password": "s3cr3t"}
        request = self.factory.post(
            "/api/articles/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        with capture_logs() as logs:
            middleware(request)

        body_logs = [e for e in logs if e.get("event") == "request_body"]
        self.assertEqual(len(body_logs), 1)
        self.assertEqual(body_logs[0]["body"]["password"], REDACTED)

        error_logs = [e for e in logs if e.get("event") == "response_error"]
        self.assertEqual(len(error_logs), 1)
        self.assertEqual(error_logs[0]["status_code"], 400)
        self.assertEqual(error_logs[0]["body"]["password"], REDACTED)
        self.assertEqual(error_logs[0]["detail"]["password"], REDACTED)

    def test_multipart_body_logged_inside_response_error(self):
        """Multipart body is logged and included in response_error."""
        from rest_framework.response import Response

        middleware = RequestBodyLoggingMiddleware(lambda request: Response({"detail": "Bad request"}, status=400))
        request = self.factory.post(
            "/api/articles/photos/",
            data={"image": b"fake-binary"},
            content_type="multipart/form-data; boundary=boundary",
        )
        with capture_logs() as logs:
            middleware(request)

        body_logs = [e for e in logs if e.get("event") == "request_body"]
        self.assertEqual(len(body_logs), 1)
        self.assertEqual(body_logs[0]["body"], "[multipart - file upload]")

        error_logs = [e for e in logs if e.get("event") == "response_error"]
        self.assertEqual(len(error_logs), 1)
        self.assertEqual(error_logs[0]["body"], "[multipart - file upload]")

    def test_empty_json_body_not_logged(self):
        """Empty request bodies do not emit request_body entries."""
        request = self.factory.post(
            "/api/articles/",
            data=b"",
            content_type="application/json",
        )
        with capture_logs() as logs:
            self.middleware(request)

        body_logs = [e for e in logs if e.get("event") == "request_body"]
        self.assertEqual(len(body_logs), 0)

    def test_empty_json_body_still_logs_error(self):
        """Even without body, response_error is logged on 4xx."""
        from rest_framework.response import Response

        middleware = RequestBodyLoggingMiddleware(lambda request: Response({"detail": "Bad request"}, status=400))
        request = self.factory.post(
            "/api/articles/",
            data=b"",
            content_type="application/json",
        )
        with capture_logs() as logs:
            middleware(request)

        error_logs = [e for e in logs if e.get("event") == "response_error"]
        self.assertEqual(len(error_logs), 1)
        self.assertIsNone(error_logs[0]["body"])

    def test_plain_text_body_logs_placeholder_not_raw_content(self):
        """text/plain requests log metadata and omit raw content."""
        from rest_framework.response import Response

        middleware = RequestBodyLoggingMiddleware(lambda request: Response({"detail": "Bad request"}, status=400))
        raw_body = b"card=4111111111111111"
        request = self.factory.post(
            "/api/articles/",
            data=raw_body,
            content_type="text/plain",
        )
        with capture_logs() as logs:
            middleware(request)

        body_logs = [e for e in logs if e.get("event") == "request_body"]
        self.assertEqual(len(body_logs), 1)
        self.assertEqual(
            body_logs[0]["body"],
            "[body omitted: unsupported content type]",
        )
        self.assertEqual(body_logs[0]["body_size"], len(raw_body))
        self.assertEqual(body_logs[0]["content_type"], "text/plain")

        error_logs = [e for e in logs if e.get("event") == "response_error"]
        self.assertEqual(len(error_logs), 1)
        self.assertEqual(
            error_logs[0]["body"],
            "[body omitted: unsupported content type]",
        )

    def test_static_path_is_skipped(self):
        """Requests to ``/static/`` paths produce no middleware logs."""
        from rest_framework.response import Response

        middleware = RequestBodyLoggingMiddleware(lambda request: Response({"detail": "Bad request"}, status=400))
        request = self.factory.get("/static/api/logo.png")
        with capture_logs() as logs:
            middleware(request)

        self.assertEqual(len(logs), 0)

    def test_well_known_path_is_skipped(self):
        """Requests to ``/.well-known/`` paths produce no middleware logs."""
        from rest_framework.response import Response

        middleware = RequestBodyLoggingMiddleware(lambda request: Response({"detail": "Bad request"}, status=400))
        request = self.factory.get("/.well-known/apple-app-site-association")
        with capture_logs() as logs:
            middleware(request)

        self.assertEqual(len(logs), 0)

    def test_get_request_without_body_not_logged(self):
        """A GET 4xx logs response_error with body set to None."""
        from rest_framework.response import Response

        middleware = RequestBodyLoggingMiddleware(lambda request: Response({"detail": "Not found"}, status=404))
        request = self.factory.get("/api/shops/")
        with capture_logs() as logs:
            middleware(request)

        error_logs = [e for e in logs if e.get("event") == "response_error"]
        self.assertEqual(len(error_logs), 1)
        self.assertIsNone(error_logs[0]["body"])
