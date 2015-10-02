# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('obligees', '0006_obligee_latitude_longitude'),
    ]

    operations = [
        migrations.AddField(
            model_name='obligee',
            name='groups',
            field=models.ManyToManyField(to='obligees.ObligeeGroup'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='obligee',
            name='tags',
            field=models.ManyToManyField(to='obligees.ObligeeTag'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='historicalobligee',
            name='type',
            field=models.SmallIntegerField(help_text='Obligee type according to \xa72.', choices=[(1, 'Odsek 1'), (2, 'Odsek 2'), (3, 'Odsek 3'), (4, 'Odsek 4')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='obligee',
            name='type',
            field=models.SmallIntegerField(help_text='Obligee type according to \xa72.', choices=[(1, 'Odsek 1'), (2, 'Odsek 2'), (3, 'Odsek 3'), (4, 'Odsek 4')]),
            preserve_default=True,
        ),
    ]
