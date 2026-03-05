import warnings

from django.test.runner import DiscoverRunner


class TestRunner(DiscoverRunner):
    """
    Custom test runner that disables SECURE_SSL_REDIRECT before running tests.

    The test client communicates over plain HTTP, so leaving the redirect
    active would turn every request into a 301 and break all tests.

    Also suppresses WhiteNoise's UserWarning about the staticfiles directory
    not existing, which is expected when collectstatic hasn't been run locally.
    """

    def setup_test_environment(self, **kwargs: object) -> None:
        from django.conf import settings

        settings.SECURE_SSL_REDIRECT = False
        warnings.filterwarnings(
            "ignore",
            message="No directory at.*staticfiles",
            category=UserWarning,
        )
        super().setup_test_environment(**kwargs)
