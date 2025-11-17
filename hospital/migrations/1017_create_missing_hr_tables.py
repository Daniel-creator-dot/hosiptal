from django.db import migrations


def create_missing_hr_tables(apps, schema_editor):
    """
    Some environments were primed with a snapshot taken before the
    recruitment and wellness tables actually existed, but the migration
    1001 was still marked as applied (faked). That leaves Django thinking
    the tables are present while SQLite is missing them, causing runtime
    OperationalError exceptions. We recreate any absent tables here so the
    schema matches the recorded migration state.
    """

    connection = schema_editor.connection
    existing_tables = set(connection.introspection.table_names())

    models_to_create = [
        apps.get_model("hospital", "RecruitmentPosition"),
        apps.get_model("hospital", "Candidate"),
        apps.get_model("hospital", "WellnessProgram"),
        apps.get_model("hospital", "WellnessParticipation"),
    ]

    created = []
    for model in models_to_create:
        table_name = model._meta.db_table
        if table_name not in existing_tables:
            schema_editor.create_model(model)
            created.append(table_name)

    if created:
        print(f"Created missing HR tables: {', '.join(created)}")
    else:
        print("All HR tables already present; nothing to do.")


class Migration(migrations.Migration):
    dependencies = [
        ("hospital", "1016_budgetlineitem_budgetperiod_departmentbudget_and_more"),
    ]

    operations = [
        migrations.RunPython(
            code=create_missing_hr_tables,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

