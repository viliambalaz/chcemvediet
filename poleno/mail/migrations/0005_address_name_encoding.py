# vim: expandtab
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from poleno.utils.mail import full_decode_header


def forward(apps, schema_editor):
    Message = apps.get_model(u'mail', u'Message')
    Recipient = apps.get_model(u'mail', u'Recipient')
    for message in Message.objects.all():
        decoded = full_decode_header(message.from_name)
        if decoded != message.from_name:
            message.from_name = decoded
            message.save()
    for recipient in Recipient.objects.all():
        decoded = full_decode_header(recipient.name)
        if decoded != recipient.name:
            recipient.name = decoded
            recipient.save()

def backward(apps, schema_editor):
    # No need to encode headers back.
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('mail', '0004_message_index_created'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
