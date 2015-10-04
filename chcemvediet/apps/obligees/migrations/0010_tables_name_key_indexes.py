# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('obligees', '0009_obligeealias_meta'),
    ]

    operations = [
        migrations.AlterField(
            model_name='obligee',
            name='name',
            field=models.CharField(help_text='Unique human readable obligee name. If official obligee name is ambiguous, it should be made more specific.', unique=True, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='obligeealias',
            name='name',
            field=models.CharField(help_text='Unique human readable obligee alias if the obligee has multiple common names.', unique=True, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='obligeegroup',
            name='key',
            field=models.CharField(help_text='Unique key to identify the group. The key is a path of slash separated words each of which represents a parent group. Every word in the path should be a nonempty string and should only contain alphanumeric characters, underscores and hyphens.', unique=True, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='obligeegroup',
            name='name',
            field=models.CharField(help_text='Unique human readable group name.', unique=True, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='obligeetag',
            name='key',
            field=models.CharField(help_text='Unique key to identify the tag. Should contain only alphanumeric characters, underscores and hyphens.', unique=True, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='obligeetag',
            name='name',
            field=models.CharField(help_text='Unique human readable tag name.', unique=True, max_length=255),
            preserve_default=True,
        ),
    ]
