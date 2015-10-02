# vim: expandtab
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.db.models import F

def forward(apps, schema_editor):
    Obligee = apps.get_model(u'obligees', u'Obligee')
    for obligee in Obligee.objects.all():
        obligee.name = u'{} {}'.format(obligee.name, obligee.pk)
        obligee.slug = u'{}{}-'.format(obligee.slug, obligee.pk)
        obligee.save()

class Migration(migrations.Migration):

    dependencies = [
        ('obligees', '0003_obligeegroup'),
    ]

    operations = [
        migrations.RunPython(forward),
    ]
