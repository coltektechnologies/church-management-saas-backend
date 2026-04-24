"""Set a user's password by email (uses Django hashing)."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Set password for an existing user identified by email (USERNAME_FIELD)."

    def add_arguments(self, parser):
        parser.add_argument(
            "email",
            type=str,
            help="User email (must exist)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default=None,
            help="New password (avoid if possible — use prompts or stdin to reduce shell history exposure)",
        )

    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        raw = options.get("password")

        if not raw:
            from getpass import getpass

            raw = getpass("New password: ")
            again = getpass("New password (again): ")
            if raw != again:
                self.stderr.write(self.style.ERROR("Passwords do not match."))
                return

        if not raw:
            self.stderr.write(self.style.ERROR("Password is empty."))
            return

        qs = User.objects.filter(email__iexact=email)
        if not qs.exists():
            self.stderr.write(self.style.ERROR(f"No user with email {email!r}"))
            return

        user = qs.first()
        user.set_password(raw)
        user.save(update_fields=["password"])
        self.stdout.write(
            self.style.SUCCESS(f"Password updated for {user.email} (id={user.pk}).")
        )
