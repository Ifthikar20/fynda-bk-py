from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_add_plan_id_android_package'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='subscription',
            name='android_package',
        ),
    ]
