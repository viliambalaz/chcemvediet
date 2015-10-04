# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import multiselectfield.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('inforequests', '0018_action_extension_renamed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='action',
            name='disclosure_level',
            field=models.SmallIntegerField(blank=True, help_text='Mandatory choice for obligee actions that may disclose the information, NULL otherwise. Specifies if the obligee disclosed any requested information by this action.', null=True, choices=[(1, 'Nespr\xedstupnenie'), (2, '\u010ciasto\u010dn\xe9 spr\xedstupnenie'), (3, '\xdapln\xe9 spr\xedstupnenie')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='action',
            name='refusal_reason',
            field=multiselectfield.db.fields.MultiSelectField(blank=True, help_text='Optional multichoice for obligee actions that may provide a reason for not disclosing the information, Should be empty for all other actions. Specifies the reason why the obligee refused to disclose the information. An empty value means that the obligee did not provide any reason.', max_length=16, choices=[('3', 'In\u0161tit\xfacia uviedla, \u017ee nem\xe1 po\u017eadovan\xfa inform\xe1ciu.'), ('4', 'In\u0161tit\xfacia uviedla, \u017ee nie je povinn\xe1 poskytova\u0165 po\u017eadovan\xfa inform\xe1ciu.'), ('5', 'In\u0161tit\xfacia uviedla, \u017ee spr\xedstupnenie po\u017eadovanej inform\xe1cie si vy\u017eaduje t\xfato inform\xe1ciu nanovo vytvori\u0165, a in\u0161tit\xfacia nie je povinn\xe1 vytv\xe1ra\u0165 nov\xe9 inform\xe1cie.'), ('6', 'In\u0161tit\xfacia uviedla, \u017ee spr\xedstupnen\xedm po\u017eadovanej inform\xe1cie by poru\u0161ila autorsk\xe9 pr\xe1vo.'), ('7', 'In\u0161tit\xfacia uviedla, \u017ee po\u017eadovan\xe1 inform\xe1cia je predmetom obchodn\xe9ho tajomstva.'), ('8', 'In\u0161tit\xfacia uviedla, \u017ee spr\xedstupnen\xedm po\u017eadovanej inform\xe1cie by poru\u0161ila ochranu osobn\xfdch \xfadajov.'), ('9', 'In\u0161tit\xfacia uviedla, \u017ee po\u017eadovan\xe1 inform\xe1cia je predmetom utajovanej skuto\u010dnosti.'), ('-2', 'In\u0161tit\xfacia uviedla in\xfa pr\xed\u010dinu.')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='action',
            name='type',
            field=models.SmallIntegerField(choices=[(1, '\u017diados\u0165'), (12, 'Odpove\u010f na v\xfdzvu na doplnenie'), (13, 'Odvolanie'), (2, 'Potvrdenie prijatia'), (3, 'Pred\u013a\u017eenie lehoty'), (4, 'Post\xfapenie \u017eiadosti'), (5, 'V\xfdzva na doplnenie \u017eiadosti'), (6, 'Spr\xedstupnenie inform\xe1ci\xed'), (7, 'Rozhodnutie o odmietnut\xed'), (8, 'Potvrdenie rozhodnutia'), (9, 'Zru\u0161enie rozhodnutia'), (10, 'Vr\xe1tenie rozhodnutia'), (11, 'Doru\u010denie post\xfapenia \u017eiadosti'), (14, 'Vypr\u0161anie lehoty'), (15, 'Vypr\u0161anie lehoty na odvolanie')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='inforequest',
            name='unique_email',
            field=models.EmailField(help_text='Unique email address used to identify which obligee email belongs to which inforequest. If the inforequest was advanced to other obligees, the same email address is used for communication with all such obligees, as there is no way to tell them to send their response to a different email address.', unique=True, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='inforequestemail',
            name='type',
            field=models.SmallIntegerField(help_text='"Applicant Action": the email represents an applicant action; "Obligee Action": the email represents an obligee action; "Undecided": The email is waiting for applicant decision; "Unrelated": Marked as an unrelated email; "Unknown": Marked as an email the applicant didn\'t know how to decide. It must be "Applicant Action" for outbound mesages or one of the remaining values for inbound messages.', choices=[(1, '\xdakon \u017eiadate\u013ea'), (2, '\xdakon in\u0161tit\xfacie'), (3, 'Nerozhodnut\xe9'), (4, 'Nes\xfavisiace'), (5, 'Nezn\xe1me')]),
            preserve_default=True,
        ),
    ]
