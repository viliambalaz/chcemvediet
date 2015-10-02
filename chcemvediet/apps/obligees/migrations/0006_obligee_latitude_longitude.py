# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('obligees', '0005_obligee_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalobligee',
            name='latitude',
            field=models.FloatField(help_text='Obligee GPS latitude', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='historicalobligee',
            name='longitude',
            field=models.FloatField(help_text='Obligee GPS longitude', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='obligee',
            name='latitude',
            field=models.FloatField(help_text='Obligee GPS latitude', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='obligee',
            name='longitude',
            field=models.FloatField(help_text='Obligee GPS longitude', null=True, blank=True),
            preserve_default=True,
        ),
    ]
