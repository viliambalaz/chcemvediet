# vim: expandtab
# -*- coding: utf-8 -*-
from poleno.utils.forms import EditableSpan
from django.utils.translation import ugettext_lazy as _
from chcemvediet.apps.wizards.forms import PaperCharField

from .common import AppealStep, AppealPaperStep, AppealFinalStep


class Paper(AppealPaperStep):
    label = _(u'inforequests:appeal:fallback:Paper:label')
    text_template = u'inforequests/appeal/texts/fallback.html'
    content_template = u'inforequests/appeal/papers/fallback.html'
    post_step_class = AppealFinalStep

    def add_fields(self):
        super(Paper, self).add_fields()
        self.fields[u'reason'] = PaperCharField(widget=EditableSpan())

class FallbackAppeal(AppealStep):
    u"""
    Fallback appeal wizard for all cases not covered with a more specific wizard.
    """
    pre_step_class = Paper
