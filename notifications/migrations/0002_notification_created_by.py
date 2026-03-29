import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                db_column="created_by_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="notifications_created",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
