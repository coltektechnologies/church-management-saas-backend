# Generated manually for Phase 1-3 settings integration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_fix_auditlog_user_fk_on_delete"),
    ]

    operations = [
        migrations.AddField(
            model_name="church",
            name="tagline",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="church",
            name="mission",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="church",
            name="primary_color",
            field=models.CharField(blank=True, default="#0B2A4A", max_length=20),
        ),
        migrations.AddField(
            model_name="church",
            name="accent_color",
            field=models.CharField(blank=True, default="#2FC4B2", max_length=20),
        ),
        migrations.AddField(
            model_name="church",
            name="sidebar_color",
            field=models.CharField(blank=True, default="#0B2A4A", max_length=20),
        ),
        migrations.AddField(
            model_name="church",
            name="background_color",
            field=models.CharField(blank=True, default="#F8FAFC", max_length=20),
        ),
        migrations.AddField(
            model_name="church",
            name="dark_mode",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="church",
            name="service_times",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
