# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('invitations', '0005_auto_20150516_1547'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invitation',
            name='key',
            field=models.CharField(help_text="Unique key to identify the invitation. It's used in the invitation URL.", unique=True, max_length=255),
            preserve_default=True,
        ),
    ]
