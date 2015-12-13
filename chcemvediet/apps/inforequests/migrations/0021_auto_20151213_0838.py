# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inforequests', '0020_inforequestdraft_modified'),
    ]

    operations = [
        migrations.AlterField(
            model_name='action',
            name='type',
            field=models.SmallIntegerField(choices=[(1, '\u017diados\u0165'), (12, 'Doplnenie \u017eiadosti'), (13, 'Odvolanie'), (2, 'Potvrdenie prijatia \u017eiadosti'), (3, 'Pred\u013a\u017eenie lehoty na odpove\u010f od in\u0161tit\xfacie'), (4, 'Post\xfapenie \u017eiadosti'), (5, 'V\xfdzva na doplnenie \u017eiadosti'), (6, 'Spr\xedstupnenie inform\xe1cie'), (7, 'Rozhodnutie o nespr\xedstupnen\xed inform\xe1cie'), (8, 'Potvrdenie rozhodnutia'), (9, 'Zru\u0161enie rozhodnutia'), (10, 'Vr\xe1tenie rozhodnutia'), (11, 'Doru\u010denie post\xfapenej \u017eiadosti novej povinnej osobe'), (14, 'Vypr\u0161anie lehoty'), (15, 'Vypr\u0161anie lehoty po podan\xed odvolania')]),
            preserve_default=True,
        ),
    ]
