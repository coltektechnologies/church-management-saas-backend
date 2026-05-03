# Generated manually for MemberPledge + IncomeTransaction.pledge

import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("members", "0001_initial"),
        ("treasury", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MemberPledge",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "pledge_year",
                    models.PositiveIntegerField(
                        help_text="Calendar year this pledge applies to."
                    ),
                ),
                ("title", models.CharField(blank=True, max_length=200)),
                (
                    "target_amount",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=15,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0.01"))
                        ],
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ACTIVE", "Active"),
                            ("FULFILLED", "Fulfilled"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="ACTIVE",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("fulfilled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "church",
                    models.ForeignKey(
                        db_column="church_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="member_pledges",
                        to="accounts.church",
                    ),
                ),
                (
                    "member",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pledges",
                        to="members.member",
                    ),
                ),
            ],
            options={
                "verbose_name": "Member pledge",
                "verbose_name_plural": "Member pledges",
                "db_table": "member_pledges",
                "ordering": ["-pledge_year", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="memberpledge",
            index=models.Index(
                fields=["church", "member", "pledge_year"],
                name="member_pled_church_m_7c8f9e_idx",
            ),
        ),
        migrations.AddField(
            model_name="incometransaction",
            name="pledge",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="income_payments",
                to="treasury.memberpledge",
            ),
        ),
        migrations.AddIndex(
            model_name="incometransaction",
            index=models.Index(fields=["pledge"], name="income_trans_pledge_b8e2_idx"),
        ),
    ]
