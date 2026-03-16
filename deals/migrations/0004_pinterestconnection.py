# Generated manually — Pinterest Connection model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('deals', '0003_seed_brands'),
    ]

    operations = [
        migrations.CreateModel(
            name='PinterestConnection',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('access_token', models.TextField()),
                ('refresh_token', models.TextField(blank=True, default='')),
                ('token_expires_at', models.DateTimeField(blank=True, null=True)),
                ('pinterest_user_id', models.CharField(blank=True, default='', max_length=100)),
                ('pinterest_username', models.CharField(blank=True, default='', max_length=150)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='pinterest_connection', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Pinterest Connection',
                'verbose_name_plural': 'Pinterest Connections',
                'db_table': 'pinterest_connections',
            },
        ),
    ]
