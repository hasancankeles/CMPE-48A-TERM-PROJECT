# Generated migration for adding gcs_url to ImageCache

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('foods', '0008_foodentry_micronutrients_foodproposal_micronutrients'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagecache',
            name='gcs_url',
            field=models.URLField(blank=True, help_text='GCS public URL after Cloud Function caches the image', null=True),
        ),
        migrations.AlterField(
            model_name='imagecache',
            name='cached_file',
            field=models.ImageField(blank=True, null=True, upload_to='cached_images/'),
        ),
    ]
