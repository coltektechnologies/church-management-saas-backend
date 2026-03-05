# Generated manually for baptism_status field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0004_member_is_active_member_last_login_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="member",
            name="baptism_status",
            field=models.CharField(
                blank=True,
                choices=[("BAPTISED", "Baptised"), ("NOT_BAPTISED", "Not Baptised")],
                help_text="Whether the member is baptised or not",
                max_length=20,
                null=True,
            ),
        ),
    ]
