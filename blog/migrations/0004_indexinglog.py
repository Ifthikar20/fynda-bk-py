from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0003_add_retailer_and_optional_url'),
    ]

    operations = [
        migrations.CreateModel(
            name='IndexingLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('google_ping', models.BooleanField(default=False, help_text='Google sitemap ping succeeded')),
                ('bing_ping', models.BooleanField(default=False, help_text='Bing sitemap ping succeeded')),
                ('indexnow', models.BooleanField(default=False, help_text='IndexNow submission succeeded')),
                ('google_api', models.BooleanField(default=False, help_text='Google Indexing API succeeded')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('submitted', 'Submitted'), ('indexed', 'Indexed'), ('failed', 'Failed')], default='pending', max_length=10)),
                ('details', models.TextField(blank=True, help_text='Raw result details')),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='indexing_logs', to='blog.post')),
            ],
            options={
                'verbose_name': 'Indexing Log',
                'verbose_name_plural': 'Indexing Logs',
                'ordering': ['-submitted_at'],
            },
        ),
    ]
