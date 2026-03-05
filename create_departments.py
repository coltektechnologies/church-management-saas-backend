#!/usr/bin/env python3
import os

import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "church_saas.settings")
django.setup()

from accounts.models import Church
from departments.models import Department


def create_departments():
    # Get the first church (you may need to adjust this if you have multiple churches)
    church = Church.objects.first()
    if not church:
        print("Error: No church found in the database. Please create a church first.")
        return

    departments_data = [
        {
            "name": "Secretariat",
            "code": "SEC-001",
            "description": "Church secretariat - handles records, communications, and announcements",
            "icon": "clipboard",
            "color": "#3498db",
            "is_active": True,
        },
        {
            "name": "Treasury",
            "code": "TRS",
            "description": "Church treasury - manages finances, budgets, and expenses",
            "icon": "dollar-sign",
            "color": "#2ecc71",
            "is_active": True,
        },
        {
            "name": "Sabbath School",
            "code": "SS",
            "description": "Sabbath School department - Bible study and education",
            "icon": "book",
            "color": "#9b59b6",
            "is_active": True,
        },
        {
            "name": "Youth Ministry",
            "code": "YOUTH",
            "description": "Ministry focused on young people aged 13-30",
            "icon": "users",
            "color": "#3498db",
            "is_active": True,
        },
        {
            "name": "Deaconry",
            "code": "DEAC",
            "description": "Deacons and deaconesses - pastoral care and church maintenance",
            "icon": "heart",
            "color": "#f39c12",
            "is_active": True,
        },
        {
            "name": "Music Department",
            "code": "MUSIC",
            "description": "Worship and praise ministry",
            "icon": "music",
            "color": "#9b59b6",
            "is_active": True,
        },
    ]

    created_count = 0
    for dept_data in departments_data:
        # Check if department with this code already exists
        if not Department.objects.filter(code=dept_data["code"]).exists():
            try:
                Department.objects.create(church=church, **dept_data)
                print(f"Created department: {dept_data['name']}")
                created_count += 1
            except Exception as e:
                print(f"Error creating department {dept_data['name']}: {str(e)}")
        else:
            print(
                f"Department with code {dept_data['code']} already exists. Skipping..."
            )

    print(f"\nCompleted! Created {created_count} new departments.")


if __name__ == "__main__":
    create_departments()
