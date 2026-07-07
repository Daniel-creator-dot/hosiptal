# Sync migration state: indexes exist in state (1072) but not in current models.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1136_remove_stale_indexes_and_field_updates'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name='drug',
                    name='hospital_dr_is_act_del_idx',
                ),
                migrations.RemoveIndex(
                    model_name='pharmacystock',
                    name='hospital_ph_drug_id_idx',
                ),
                migrations.RemoveIndex(
                    model_name='pharmacystock',
                    name='hospital_ph_is_del_idx',
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql='DROP INDEX IF EXISTS hospital_dr_is_act_del_idx;',
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql='DROP INDEX IF EXISTS hospital_ph_drug_id_idx;',
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql='DROP INDEX IF EXISTS hospital_ph_is_del_idx;',
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
    ]
