# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inforequests', '0014_action_obligee_extension'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='action',
            name='deadline',
        ),
        migrations.RemoveField(
            model_name='action',
            name='deadline_base_date',
        ),
    ]
