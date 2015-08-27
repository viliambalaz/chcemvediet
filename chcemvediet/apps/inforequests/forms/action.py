# vim: expandtab
# -*- coding: utf-8 -*-
from django import forms
from django.utils.translation import ugettext_lazy as _

from poleno.utils.forms import PrefixedForm
from poleno.utils.template import lazy_render_to_string


class ExtendDeadlineForm(PrefixedForm):
    template = u'inforequests/modals/extend_deadline.html'

    def save(self, action):
        assert self.is_valid()

        # Extend by 3 CD relative to today.
        action.applicant_extension = action.deadline.calendar_days_behind + 3
