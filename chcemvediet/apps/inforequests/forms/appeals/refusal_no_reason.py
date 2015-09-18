# vim: expandtab
# -*- coding: utf-8 -*-
from .common import AppealStep, AppealPaperStep, AppealFinalStep

class Paper(AppealPaperStep):
    text_template = u'inforequests/appeals/texts/refusal_no_reason.html'
    content_template = u'inforequests/appeals/papers/refusal_no_reason.html'
    post_step_class = AppealFinalStep

class RefusalNoReasonAppeal(AppealStep):
    u"""
    Appeal wizard for branches that end with a refusal action with no reason specified.
    """
    pre_step_class = Paper
