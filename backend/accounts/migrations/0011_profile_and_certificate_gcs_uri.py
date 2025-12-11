from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_nutritiontargets_usermetrics"),
    ]

    operations = [
        migrations.AddField(
            model_name="usertag",
            name="certificate_gcs_uri",
            field=models.CharField(max_length=512, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="user",
            name="profile_image_gcs_uri",
            field=models.CharField(max_length=512, null=True, blank=True),
        ),
    ]


