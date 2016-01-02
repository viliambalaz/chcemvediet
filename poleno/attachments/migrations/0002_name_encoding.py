# vim: expandtab
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from poleno.utils.mail import full_decode_header


def forward(apps, schema_editor):
    Attachment = apps.get_model(u'attachments', u'Attachment')
    for attachment in Attachment.objects.all():
        decoded = full_decode_header(attachment.name)
        if decoded != attachment.name:
            attachment.name = decoded
            attachment.save()

def backward(apps, schema_editor):
    # No need to encode names back.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('attachments', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
