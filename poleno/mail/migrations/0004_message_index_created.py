# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mail', '0003_message_created_data'),
    ]

    operations = [
        migrations.AlterIndexTogether(
            name='message',
            index_together=set([('created', 'id'), ('processed', 'id')]),
        ),
    ]
