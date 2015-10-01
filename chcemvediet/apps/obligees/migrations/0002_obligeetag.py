# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('obligees', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ObligeeTag',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('key', models.CharField(help_text='Unique key to identify the tag. Should contain only alphanumeric characters, underscore and hyphen.', unique=True, max_length=255, db_index=True)),
                ('name', models.CharField(help_text='Human readable tag name.', max_length=255)),
                ('slug', models.SlugField(help_text='Unique slug to identify the tag used in urls. Automaticly computed from the tag name. May not be changed manually.', unique=True, max_length=255)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterField(
            model_name='historicalobligee',
            name='status',
            field=models.SmallIntegerField(help_text='"Pending" for obligees that exist and accept inforequests; "Dissolved" for obligees that do not exist any more and no further inforequests may be submitted to them.', choices=[(1, '\u010cakaj\xface'), (2, 'Zru\u0161en\xe9')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='obligee',
            name='status',
            field=models.SmallIntegerField(help_text='"Pending" for obligees that exist and accept inforequests; "Dissolved" for obligees that do not exist any more and no further inforequests may be submitted to them.', choices=[(1, '\u010cakaj\xface'), (2, 'Zru\u0161en\xe9')]),
            preserve_default=True,
        ),
    ]
