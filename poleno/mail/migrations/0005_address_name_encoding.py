# vim: expandtab
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from email.header import decode_header

from django.db import models, migrations


def full_decode_header(header):
    if isinstance(header, unicode):
        header = header.encode(u'utf-8')
    parts = decode_header(header)
    decoded = u''.join(unicode(part, enc or u'utf-8', u'replace') for part, enc in parts)
    return decoded

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
