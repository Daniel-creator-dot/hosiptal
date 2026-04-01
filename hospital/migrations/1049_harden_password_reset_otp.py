from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1048_password_reset_otp'),
    ]

    operations = [
        migrations.AlterField(
            model_name='passwordresetotp',
            name='code',
            field=models.CharField(max_length=128, db_index=True),
        ),
    ]
















