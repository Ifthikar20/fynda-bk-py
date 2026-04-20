from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mobile', '0007_notification'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(
                fields=['user', 'alert', 'is_read'],
                name='mobile_noti_user_alert_read_idx',
            ),
        ),
    ]
