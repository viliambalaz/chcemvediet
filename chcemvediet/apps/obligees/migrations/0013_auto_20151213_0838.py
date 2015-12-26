# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('obligees', '0012_obligee_type_help'),
    ]

    operations = [
        migrations.AlterField(
            model_name='obligee',
            name='groups',
            field=models.ManyToManyField(to='obligees.ObligeeGroup', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='obligee',
            name='tags',
            field=models.ManyToManyField(to='obligees.ObligeeTag', blank=True),
            preserve_default=True,
        ),
    ]
