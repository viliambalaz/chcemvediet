# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('obligees', '0002_obligeetag'),
    ]

    operations = [
        migrations.CreateModel(
            name='ObligeeGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('key', models.CharField(help_text='Unique key to identify the group. The key is a path of slash separated words each of which represents a supergroup. Every word in the path should be a nonempty string and should only contain alphanumeric characters, underscores and hyphens.', unique=True, max_length=255, db_index=True)),
                ('name', models.CharField(help_text='Human readable group name.', max_length=255)),
                ('slug', models.SlugField(help_text='Unique slug to identify the group used in urls. Automaticly computed from the group name. May not be changed manually.', unique=True, max_length=255)),
                ('description', models.TextField(help_text='Human readable group description.', blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterField(
            model_name='obligeetag',
            name='key',
            field=models.CharField(help_text='Unique key to identify the tag. Should contain only alphanumeric characters, underscores and hyphens.', unique=True, max_length=255, db_index=True),
            preserve_default=True,
        ),
    ]
