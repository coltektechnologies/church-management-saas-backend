from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Create a platform administrator (super admin for entire SaaS)"

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, help="Admin email address")
        parser.add_argument("--username", type=str, help="Admin username")
        parser.add_argument("--password", type=str, help="Admin password")

    def handle(self, *args, **options):
        email = options.get("email") or input("Email address: ")
        username = options.get("username") or input("Username: ")
        password = options.get("password")

        if not password:
            from getpass import getpass

            password = getpass("Password: ")
            password_confirm = getpass("Password (again): ")

            if password != password_confirm:
                self.stdout.write(self.style.ERROR("Passwords do not match"))
                return

        # Check if user exists
        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.ERROR(f"User with email {email} already exists")
            )
            return

        # Create platform admin
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_platform_admin=True,
            is_staff=True,
            is_superuser=True,
            church=None,  # No church assignment
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Platform admin "{username}" created successfully!\n'
                f"Email: {email}\n"
                f"User ID: {user.id}\n"
                f"This user can access all churches and manage the entire platform."
            )
        )
