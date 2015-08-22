# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inforequests', '0010_action_dates_data'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='action',
            name='effective_date',
        ),
        migrations.AlterField(
            model_name='action',
            name='legal_date',
            field=models.DateField(help_text='The date the action legally occured. Mandatory for every action.'),
            preserve_default=True,
        ),
    ]
