# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('obligees', '0008_obligeealias'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='obligeealias',
            options={'verbose_name_plural': 'obligee aliases'},
        ),
    ]
