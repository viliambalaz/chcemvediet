# vim: expandtab
# -*- coding: utf-8 -*-
from poleno.utils.forms import EditableSpan
from django.utils.translation import ugettext_lazy as _
from chcemvediet.apps.wizards.forms import PaperCharField

from .common import AppealSectionStep, AppealPaperStep


class AdvancementAppeal(AppealSectionStep):
    u"""
    Appeal wizard for branches that end with an advancement action.
    """
    label = _(u'inforequests:appeal:advancement:AdvancementAppeal:label')
    text_template = u'inforequests/appeal/texts/advancement.html'
    section_template = u'inforequests/appeal/papers/advancement.html'
    global_fields = [u'reason']
    post_step_class = AppealPaperStep

    def add_fields(self):
        super(AdvancementAppeal, self).add_fields()
        self.fields[u'reason'] = PaperCharField(widget=EditableSpan())

    def paper_fields(self, paper):
        super(AdvancementAppeal, self).paper_fields(paper)
        paper.fields[u'reason'] = PaperCharField(widget=EditableSpan())
