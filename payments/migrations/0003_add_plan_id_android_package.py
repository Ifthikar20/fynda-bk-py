from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0002_add_revenuecat_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='plan_id',
            field=models.CharField(
                blank=True, default='', max_length=255,
                help_text='Store product id, e.g. com.outfi.outfiApp.premium.monthly',
            ),
        ),
        migrations.AddField(
            model_name='subscription',
            name='android_package',
            field=models.CharField(
                blank=True, default='', max_length=255,
                help_text='Android package name used for Play subscription deep-links',
            ),
        ),
    ]
