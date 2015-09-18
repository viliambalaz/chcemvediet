# vim: expandtab
# -*- coding: utf-8 -*-
from .common import AppealStep, AppealPaperStep, AppealFinalStep

class Paper(AppealPaperStep):
    text_template = u'inforequests/appeals/texts/expiration.html'
    content_template = u'inforequests/appeals/papers/expiration.html'
    post_step_class = AppealFinalStep

class ExpirationAppeal(AppealStep):
    u"""
    Appeal wizard for branches that end with an action with an expired obligee deadline, or an
    expiration action.
    """
    pre_step_class = Paper
