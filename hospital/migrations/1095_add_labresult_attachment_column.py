# Fix: Ensure hospital_labresult.attachment column exists (1094 may have been partially applied)

from django.db import migrations, connection


def add_attachment_column(apps, schema_editor):
    """Add attachment column if it doesn't exist."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'hospital_labresult' AND column_name = 'attachment';
        """)
        if cursor.fetchone():
            return  # Column already exists
        cursor.execute("""
            ALTER TABLE hospital_labresult
            ADD COLUMN attachment varchar(100) NULL;
        """)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1094_add_lab_result_attachment'),
    ]

    operations = [
        migrations.RunPython(add_attachment_column, noop),
    ]
