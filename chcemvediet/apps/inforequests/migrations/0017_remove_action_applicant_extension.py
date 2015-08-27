# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inforequests', '0016_action_snooze'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='action',
            name='applicant_extension',
        ),
    ]
