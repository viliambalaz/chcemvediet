# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inforequests', '0015_action_remove_deadline'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='snooze',
            field=models.DateField(help_text='The applicant may snooze for few days after the obligee misses its deadline and wait a little longer. He may snooze multiple times. Ignored for applicant deadlines.', null=True, blank=True),
            preserve_default=True,
        ),
    ]
