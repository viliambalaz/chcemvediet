# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inforequests', '0011_action_dates_remove'),
    ]

    operations = [
        migrations.RenameField(
            model_name='action',
            old_name='extension',
            new_name='applicant_extension',
        ),
        migrations.AlterField(
            model_name='action',
            name='deadline',
            field=models.IntegerField(help_text='The deadline that apply after the action, if the action sets a deadline, NULL otherwise. The deadline is expressed in a number of working days (WD) counting since ``deadline_base_date``. It may apply to the applicant or to the obligee, depending on the action type.', null=True, blank=True),
            preserve_default=True,
        ),
    ]
