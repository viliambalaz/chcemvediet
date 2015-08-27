# vim: expandtab
# -*- coding: utf-8 -*-
import datetime

from poleno.utils.forms import PrefixedForm
from poleno.utils.date import local_today


class SnoozeForm(PrefixedForm):
    template = u'inforequests/modals/snooze.html'

    def save(self, action):
        assert self.is_valid()

        action.snooze = local_today() + datetime.timedelta(days=3)
