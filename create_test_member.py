import os

import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "church_saas.settings")
django.setup()

from accounts.models import Church
from members.models import Member, MemberLocation


def create_test_member():
    try:
        # Get the first church
        church = Church.objects.first()
        if not church:
            print("No churches found. Please create a church first.")
            return

        from django.utils import timezone

        # Create member
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            gender="MALE",
            church=church,
            has_system_access=True,
            membership_status="ACTIVE",
            member_since=timezone.now().date(),
        )

        # Create member location with email
        MemberLocation.objects.create(
            member=member,
            church=church,
            phone_primary="+233123456789",
            email="kyerematengcollins93@gmail.com",
            address="123 Test Street",
            city="Accra",
            country="Ghana",
        )

        print(f"Created test member: {member.first_name} {member.last_name}")
        print("Now updating to trigger email notification...")

        # Save again to trigger email notification
        member.save()
        print("Email notification should be sent to:", member.location.email)

    except Exception as e:
        print(f"Error creating test member: {str(e)}")


if __name__ == "__main__":
    print("Creating test member with email notification...")
    create_test_member()
