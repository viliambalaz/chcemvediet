# vim: expandtab
# -*- coding: utf-8 -*-
from poleno.utils.forms import EditableSpan
from chcemvediet.apps.wizards.forms import PaperCharField

from .common import AppealStep, AppealSectionStep, AppealPaperStep, AppealFinalStep

class Paper(AppealPaperStep):
    post_step_class = AppealFinalStep

class Reason(AppealSectionStep):
    text_template = u'inforequests/appeal/texts/disclosure.html'
    section_template = u'inforequests/appeal/papers/disclosure.html'
    global_fields = [u'reason']
    post_step_class = Paper

    def add_fields(self):
        super(Reason, self).add_fields()
        self.fields[u'reason'] = PaperCharField(widget=EditableSpan())

    def paper_fields(self, paper):
        super(Reason, self).paper_fields(paper)
        paper.fields[u'reason'] = PaperCharField(widget=EditableSpan())

class DisclosureAppeal(AppealStep):
    u"""
    Appeal wizard for branches that end with a non-full disclosure action.
    """
    pre_step_class = Reason
