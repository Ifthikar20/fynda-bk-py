from django.db import migrations, models


def deactivate_non_ios_tokens(apps, schema_editor):
    """Orphan any existing non-iOS device tokens by marking them inactive.

    Existing rows with platform='android' (or anything else) stay in the DB
    for audit / rollback, but they stop being used for push.
    """
    DeviceToken = apps.get_model('mobile', 'DeviceToken')
    DeviceToken.objects.exclude(platform='ios').update(is_active=False)


def noop_reverse(apps, schema_editor):
    # Rollback cannot meaningfully re-activate individually chosen rows.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('mobile', '0005_add_deal_alerts'),
    ]

    operations = [
        migrations.RunPython(deactivate_non_ios_tokens, noop_reverse),
        migrations.AlterField(
            model_name='devicetoken',
            name='platform',
            field=models.CharField(choices=[('ios', 'iOS')], max_length=10),
        ),
    ]
