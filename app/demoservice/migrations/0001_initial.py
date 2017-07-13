from django.db import migrations
from django.contrib.auth.models import Group


def create_groups(apps, schema_editor):
    authors = Group(name='canonical-content-people')
    authors.save()


class Migration(migrations.Migration):
    dependencies = [
        ('auth', '0001_initial'),
        ('django_openid_auth', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(create_groups),
    ]
