# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('obligees', '0004_obligee_add_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalobligee',
            name='type',
            field=models.SmallIntegerField(default=1, help_text='Obligee type according to \xa72.', choices=[(1, 'obligees:Obligee:type:SECTION_1'), (2, 'obligees:Obligee:type:SECTION_2'), (3, 'obligees:Obligee:type:SECTION_3'), (4, 'obligees:Obligee:type:SECTION_4')]),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='obligee',
            name='type',
            field=models.SmallIntegerField(default=1, help_text='Obligee type according to \xa72.', choices=[(1, 'obligees:Obligee:type:SECTION_1'), (2, 'obligees:Obligee:type:SECTION_2'), (3, 'obligees:Obligee:type:SECTION_3'), (4, 'obligees:Obligee:type:SECTION_4')]),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='historicalobligee',
            name='gender',
            field=models.SmallIntegerField(help_text='Obligee name grammar gender.', choices=[(1, 'Mu\u017esk\xfd'), (2, '\u017densk\xfd'), (3, 'Stredn\xfd'), (4, 'Pomno\u017en\xfd')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='historicalobligee',
            name='status',
            field=models.SmallIntegerField(help_text='"Pending" for obligees that exist and accept inforequests; "Dissolved" for obligees that do not exist any more and no further inforequests may be submitted to them.', choices=[(1, 'Akt\xedvna'), (2, 'Zru\u0161en\xe1')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='obligee',
            name='gender',
            field=models.SmallIntegerField(help_text='Obligee name grammar gender.', choices=[(1, 'Mu\u017esk\xfd'), (2, '\u017densk\xfd'), (3, 'Stredn\xfd'), (4, 'Pomno\u017en\xfd')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='obligee',
            name='status',
            field=models.SmallIntegerField(help_text='"Pending" for obligees that exist and accept inforequests; "Dissolved" for obligees that do not exist any more and no further inforequests may be submitted to them.', choices=[(1, 'Akt\xedvna'), (2, 'Zru\u0161en\xe1')]),
            preserve_default=True,
        ),
    ]
