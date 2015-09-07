# vim: expandtab
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
from django.db import models, migrations


def forward(apps, schema_editor):
    Message = apps.get_model(u'mail', u'Message')
    for message in Message.objects.all():
        message.created = message.processed or datetime.datetime.now()
        message.save()

def backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('mail', '0002_message_created'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
