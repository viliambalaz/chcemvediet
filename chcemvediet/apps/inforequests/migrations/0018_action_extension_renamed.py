# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inforequests', '0017_remove_action_applicant_extension'),
    ]

    operations = [
        migrations.RenameField(
            model_name='action',
            old_name='obligee_extension',
            new_name='extension',
        ),
    ]
