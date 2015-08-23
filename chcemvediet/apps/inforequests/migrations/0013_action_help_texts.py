# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import multiselectfield.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('inforequests', '0012_action_applicant_extension_renamed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='action',
            name='applicant_extension',
            field=models.IntegerField(help_text='Applicant extension to the deadline, if the action sets an obligee deadline. The applicant may extend the deadline after it is missed in order to be patient and wait a little longer. He may extend it multiple times. Ignored for applicant deadlines, as they may not be extended.', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='action',
            name='content_type',
            field=models.SmallIntegerField(default=1, help_text='Mandatory choice for action content type. Supported formats are plain text and html code. The html code is assumed to be safe. It is passed to the client without sanitizing. It must be sanitized before saving it here.', choices=[(1, 'Plain Text'), (2, 'HTML')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='action',
            name='disclosure_level',
            field=models.SmallIntegerField(blank=True, help_text='Mandatory choice for obligee actions that may disclose the information, NULL otherwise. Specifies if the obligee disclosed any requested information by this action.', null=True, choices=[(1, 'No Disclosure at All'), (2, 'Partial Disclosure'), (3, 'Full Disclosure')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='action',
            name='file_number',
            field=models.CharField(help_text='A file number assigned to the action by the obligee. Usually only obligee actions have it. However, if we know tha obligee assigned a file number to an applicant action, we should keep it here as well. The file number is optional.', max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='action',
            name='refusal_reason',
            field=multiselectfield.db.fields.MultiSelectField(blank=True, help_text='Optional multichoice for obligee actions that may provide a reason for not disclosing the information, Should be empty for all other actions. Specifies the reason why the obligee refused to disclose the information. An empty value means that the obligee did not provide any reason.', max_length=16, choices=[('3', 'Does not Have Information'), ('4', 'Does not Provide Information'), ('5', 'Does not Create Information'), ('6', 'Copyright Restriction'), ('7', 'Business Secret'), ('8', 'Personal Information'), ('9', 'Confidential Information'), ('-2', 'Other Reason')]),
            preserve_default=True,
        ),
    ]
