# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('geounits', '0001_initial'),
        ('obligees', '0010_tables_name_key_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalobligee',
            name='iczsj_id',
            field=models.CharField(help_text='City neighbourhood the obligee address is in.', max_length=32, null=True, db_index=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='obligee',
            name='iczsj',
            field=models.ForeignKey(default=20418, to='geounits.Neighbourhood', help_text='City neighbourhood the obligee address is in.'),
            preserve_default=False,
        ),
    ]
