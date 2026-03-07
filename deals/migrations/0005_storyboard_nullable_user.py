from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('deals', '0004_pinterestconnection'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sharedstoryboard',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='shared_storyboards',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='sharedstoryboard',
            name='device_id',
            field=models.CharField(blank=True, db_index=True, default='', max_length=128),
        ),
    ]
