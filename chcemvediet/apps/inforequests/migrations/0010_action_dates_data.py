# vim: expandtab
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from poleno.utils.date import utc_datetime_from_local


def forward(apps, schema_editor):
    APPLICANT_ACTION_TYPES = [1, 12, 13]
    OBLIGEE_ACTION_TYPES = [2, 3, 4, 5, 6, 7, 8, 9, 10]
    Action = apps.get_model(u'inforequests', u'Action')
    for action in Action.objects.all():
        action.created = utc_datetime_from_local(action.effective_date, hour=10, microsecond=action.pk)
        action.sent_date = action.effective_date if action.type in APPLICANT_ACTION_TYPES else None
        action.delivered_date = action.effective_date if action.type in OBLIGEE_ACTION_TYPES else None
        action.legal_date = action.effective_date
        action.deadline_base_date = action.effective_date if action.deadline else None
        action.save()

def backward(apps, schema_editor):
    Action = apps.get_model(u'inforequests', u'Action')
    for action in Action.objects.all():
        action.effective_date = action.legal_date
        action.save()

class Migration(migrations.Migration):

    dependencies = [
        ('inforequests', '0009_action_dates'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
