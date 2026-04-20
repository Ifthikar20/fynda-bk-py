import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mobile', '0006_devicetoken_ios_only'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('kind', models.CharField(choices=[
                    ('new_matches', 'New matches found'),
                    ('price_drop', 'Price dropped'),
                    ('alert_expired', 'Alert expired'),
                    ('alert_paused', 'Alert paused'),
                    ('subscription', 'Subscription update'),
                    ('system', 'System message'),
                ], max_length=30)),
                ('title', models.CharField(max_length=200)),
                ('body', models.CharField(blank=True, default='', max_length=500)),
                ('data', models.JSONField(blank=True, default=dict, help_text='Client deep-link hints')),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('alert', models.ForeignKey(blank=True, null=True,
                                            on_delete=django.db.models.deletion.SET_NULL,
                                            related_name='notifications',
                                            to='mobile.dealalert')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                           related_name='mobile_notifications',
                                           to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'mobile_notifications',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user', '-created_at'], name='mobile_noti_user_id_created_idx'),
                    models.Index(fields=['user', 'is_read'], name='mobile_noti_user_id_isread_idx'),
                ],
            },
        ),
    ]
