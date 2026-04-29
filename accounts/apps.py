from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        import accounts.signals  # noqa: F401

        # Custom admin index (dashboard KPIs + template)
        from accounts.admin_dashboard import patch_admin_index

        patch_admin_index()
