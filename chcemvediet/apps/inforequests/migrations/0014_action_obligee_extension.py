# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inforequests', '0013_action_help_texts'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='obligee_extension',
            field=models.IntegerField(help_text='Obligee extension to the original deadline. Applicable only to extension actions. Ignored for all other actions.', null=True, blank=True),
            preserve_default=True,
        ),
    ]
