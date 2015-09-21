# vim: expandtab
# -*- coding: utf-8 -*-
from django import forms
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe

from poleno.attachments.forms import AttachmentsField
from poleno.workdays import workdays
from poleno.utils.models import after_saved
from poleno.utils.urls import reverse
from poleno.utils.forms import CompositeTextField, PrefixedForm
from chcemvediet.apps.obligees.forms import ObligeeWidget, ObligeeField
from chcemvediet.apps.inforequests.models import Inforequest

from poleno.utils.template import lazy_render_to_string


class InforequestForm(PrefixedForm):
    obligee = ObligeeField(
            label=_(u'inforequests:InforequestForm:obligee:label'),
            help_text=lazy_render_to_string(u'inforequests/create/tooltips/obligee.txt'),
            widget=ObligeeWidget(input_attrs={
                u'placeholder': _(u'inforequests:InforequestForm:obligee:placeholder'),
                u'class': u'span5',
                u'data-container': u'body',
                }),
            )
    subject = CompositeTextField(
            label=_(u'inforequests:InforequestForm:subject:label'),
            template=u'inforequests/create/forms/subject.txt',
            fields=[
                forms.CharField(max_length=50, widget=forms.TextInput(attrs={
                    u'placeholder': _(u'inforequests:InforequestForm:subject:placeholder'),
                    u'class': u'span3',
                    })),
                ],
            )
    content = CompositeTextField(
            label=_(u'inforequests:InforequestForm:content:label'),
            template=u'inforequests/create/forms/content.txt',
            fields=[
                forms.CharField(widget=forms.Textarea(attrs={
                    u'placeholder': _(u'inforequests:InforequestForm:content:placeholder'),
                    u'class': u'autosize',
                    u'cols': u'', u'rows': u'',
                    })),
                ],
            composite_attrs={
                u'class': u'input-block-level',
                },
            )
    attachments = AttachmentsField(
            label=_(u'inforequests:InforequestForm:attachments:label'),
            required=False,
            upload_url_func=(lambda: reverse(u'inforequests:upload_attachment')),
            download_url_func=(lambda a: reverse(u'inforequests:download_attachment', args=[a.pk])),
            )

    def __init__(self, *args, **kwargs):
        self.draft = kwargs.pop(u'draft', False)
        self.attached_to = kwargs.pop(u'attached_to')
        self.user = kwargs.pop(u'user')
        super(InforequestForm, self).__init__(*args, **kwargs)

        unique_email = settings.INFOREQUEST_UNIQUE_EMAIL.format(token=u'xxxx')
        unique_email = mark_safe(render_to_string(u'inforequests/create/content_unique_email.html',
                dict(unique_email=unique_email)).strip())
        self.fields[u'content'].widget.context[u'user'] = self.user
        self.fields[u'content'].widget.context[u'unique_email'] = unique_email
        self.fields[u'attachments'].attached_to = self.attached_to

        if self.draft:
            self.fields[u'obligee'].required = False
            self.fields[u'subject'].required = False
            self.fields[u'content'].required = False

    def save(self):
        assert self.is_valid()
        subject_finalize = lambda inforequest: self.fields[u'subject'].finalize(self.cleaned_data[u'subject'])
        content_finalize = lambda inforequest: self.fields[u'content'].finalize(self.cleaned_data[u'content'], dict(
                unique_email=inforequest.unique_email,
                obligee=self.cleaned_data[u'obligee'],
                ))
        inforequest = Inforequest.create(
                applicant=self.user,
                subject=self.cleaned_data[u'subject'][0],
                content=self.cleaned_data[u'content'][0],
                obligee=self.cleaned_data[u'obligee'],
                subject_finalize=subject_finalize,
                content_finalize=content_finalize,
                attachments=self.cleaned_data[u'attachments'],
                )
        return inforequest

    def save_to_draft(self, draft):
        assert self.is_valid()

        draft.obligee = self.cleaned_data[u'obligee']
        draft.subject = self.cleaned_data[u'subject']
        draft.content = self.cleaned_data[u'content']

        @after_saved(draft)
        def deferred(draft):
            draft.attachment_set = self.cleaned_data[u'attachments']

    def load_from_draft(self, draft):
        self.initial[u'obligee'] = draft.obligee
        self.initial[u'subject'] = draft.subject
        self.initial[u'content'] = draft.content
        self.initial[u'attachments'] = draft.attachments
