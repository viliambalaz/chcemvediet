# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('geounits', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='neighbourhood',
            name='cadastre',
            field=models.CharField(default=1, help_text='Human readable neighbourhood cadastre name. (REGPJ.NAZUTJ)', max_length=255),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='municipality',
            name='id',
            field=models.CharField(help_text='Municipality primary key. Example: "SK031B518042" (REGPJ.LSUJ2)', max_length=32, serialize=False, primary_key=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='neighbourhood',
            name='name',
            field=models.CharField(help_text='Human readable neighbourhood name. Neighbourhood names are not unique, not even within a municipality. (REGPJ.NAZZSJ)', max_length=255),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='neighbourhood',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='neighbourhood',
            name='slug',
        ),
    ]
