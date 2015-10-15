# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('obligees', '0011_obligee_iczsj'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalobligee',
            name='type',
            field=models.SmallIntegerField(help_text='Obligee type according to \xa72. Obligees defined in section 3 are obliged to disclose some information only.', choices=[(1, 'Odsek 1'), (2, 'Odsek 2'), (3, 'Odsek 3'), (4, 'Odsek 4')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='obligee',
            name='type',
            field=models.SmallIntegerField(help_text='Obligee type according to \xa72. Obligees defined in section 3 are obliged to disclose some information only.', choices=[(1, 'Odsek 1'), (2, 'Odsek 2'), (3, 'Odsek 3'), (4, 'Odsek 4')]),
            preserve_default=True,
        ),
    ]
