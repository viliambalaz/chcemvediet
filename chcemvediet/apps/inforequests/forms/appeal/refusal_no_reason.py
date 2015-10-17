# vim: expandtab
# -*- coding: utf-8 -*-
from django.utils.translation import ugettext_lazy as _

from .common import AppealStep, AppealPaperStep, AppealFinalStep


class Paper(AppealPaperStep):
    label = _(u'inforequests:appeal:refusal_no_reason:Paper:label')
    text_template = u'inforequests/appeal/texts/refusal_no_reason.html'
    content_template = u'inforequests/appeal/papers/refusal_no_reason.html'
    post_step_class = AppealFinalStep

class RefusalNoReasonAppeal(AppealStep):
    u"""
    Appeal wizard for branches that end with a refusal action with no reason specified.
    """
    pre_step_class = Paper
