from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('landing', '0003_community_is_private_userprofile_avatar_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='media',
            name='original_url',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
