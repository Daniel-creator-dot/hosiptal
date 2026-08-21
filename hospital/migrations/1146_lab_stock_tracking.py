from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1145_labreagent_deduct_per_lab_visit'),
    ]

    operations = [
        migrations.AddField(
            model_name='labtest',
            name='stock_tracking',
            field=models.CharField(
                choices=[
                    ('untracked', 'Not tracked'),
                    ('measurable', 'Measurable (kit / cassette)'),
                    ('immeasurable', 'Immeasurable (chemistry reagent)'),
                ],
                db_index=True,
                default='untracked',
                help_text='Measurable kits count pieces per box. Immeasurable chemistry reagents count remaining tests per kit.',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='labtest',
            name='kit_name',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='labtest',
            name='qty_per_box',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Pieces in one box for measurable (kit) tests.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='labtest',
            name='tests_per_kit',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Number of tests one chemistry kit yields (immeasurable).',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='labtest',
            name='reagent_volume_note',
            field=models.CharField(
                blank=True,
                help_text='Kit volume notes, e.g. R1: 4x35ml R2: 2x18ml.',
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name='labreagent',
            name='stock_tracking',
            field=models.CharField(
                choices=[
                    ('untracked', 'Not tracked'),
                    ('measurable', 'Measurable (kit / cassette)'),
                    ('immeasurable', 'Immeasurable (chemistry reagent)'),
                ],
                db_index=True,
                default='untracked',
                help_text='Kit tests: stock in pieces. Chemistry: stock in remaining tests.',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='labreagent',
            name='qty_per_box',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Pieces per box when receiving measurable kits.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='labreagent',
            name='tests_per_kit',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Tests yielded when receiving one chemistry kit.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='labreagent',
            name='reagent_volume_note',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='labreagent',
            name='qty_consumed_per_test',
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal('1'),
                help_text='Quantity deducted from this item when a linked lab test is completed. Set 0 to skip auto-deduct (e.g. FBC diluent until yield is known).',
                max_digits=12,
            ),
        ),
    ]
