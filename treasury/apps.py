from django.apps import AppConfig


class TreasuryConfig(AppConfig):
    name = "treasury"

    def ready(self):
        import treasury.signals  # noqa: F401
