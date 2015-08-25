# vim: expandtab
# -*- coding: utf-8 -*-
from django import forms
from django.utils.translation import ugettext_lazy as _

from poleno.utils.forms import PrefixedForm
from poleno.utils.template import lazy_render_to_string


class ExtendDeadlineForm(PrefixedForm):
    template = u'inforequests/modals/extend_deadline.html'

    def __init__(self, *args, **kwargs):
        max_value = kwargs.pop(u'max_value')
        super(ExtendDeadlineForm, self).__init__(*args, **kwargs)

        self.fields[u'applicant_extension'] = forms.IntegerField(
                label=_(u'inforequests:ExtendDeadlineForm:applicant_extension:label'),
                initial=(2+max_value+1)/2,
                min_value=2,
                max_value=max_value,
                widget=forms.NumberInput(attrs={
                    u'placeholder': _(u'inforequests:ExtendDeadlineForm:applicant_extension:placeholder'),
                    u'class': u'with-tooltip',
                    u'data-toggle': u'tooltip',
                    u'title': lazy_render_to_string(u'inforequests/modals/tooltips/extend_deadline.txt'),
                    }),
                )

    def save(self, action):
        assert self.is_valid()

        # User sets the extended deadline relative to today.
        until_today = -action.deadline.calendar_days_remaining
        action.applicant_extension = until_today + self.cleaned_data[u'applicant_extension']
