# Generated manually to fix IntegrityError when deleting users

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_add_church_group"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                # Drop existing FK (was created without ON DELETE SET NULL)
                (
                    "ALTER TABLE accounts_auditlog "
                    "DROP CONSTRAINT IF EXISTS audit_logs_user_id_752b0e2b_fk_users_id;"
                ),
                # Re-add with ON DELETE SET NULL so user deletion doesn't fail
                (
                    "ALTER TABLE accounts_auditlog "
                    "ADD CONSTRAINT audit_logs_user_id_752b0e2b_fk_users_id "
                    "FOREIGN KEY (user_id) REFERENCES accounts_user(id) "
                    "ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;"
                ),
            ],
            reverse_sql=[
                # Reverse: restore original constraint (without ON DELETE SET NULL)
                (
                    "ALTER TABLE accounts_auditlog "
                    "DROP CONSTRAINT IF EXISTS audit_logs_user_id_752b0e2b_fk_users_id;"
                ),
                (
                    "ALTER TABLE accounts_auditlog "
                    "ADD CONSTRAINT audit_logs_user_id_752b0e2b_fk_users_id "
                    "FOREIGN KEY (user_id) REFERENCES accounts_user(id) "
                    "DEFERRABLE INITIALLY DEFERRED;"
                ),
            ],
        ),
    ]
