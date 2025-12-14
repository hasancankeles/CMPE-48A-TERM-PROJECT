# Generated migration for adding badges to User model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_profile_and_certificate_gcs_uri'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='badges',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Pre-calculated user badges (updated by Cloud Function)'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='badges_updated_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Last time badges were recalculated'
            ),
        ),
    ]
