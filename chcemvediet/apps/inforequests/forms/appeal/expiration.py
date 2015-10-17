# vim: expandtab
# -*- coding: utf-8 -*-
from django.utils.translation import ugettext_lazy as _

from .common import AppealStep, AppealPaperStep, AppealFinalStep


class Paper(AppealPaperStep):
    label = _(u'inforequests:appeal:expiration:Paper:label')
    text_template = u'inforequests/appeal/texts/expiration.html'
    content_template = u'inforequests/appeal/papers/expiration.html'
    post_step_class = AppealFinalStep

class ExpirationAppeal(AppealStep):
    u"""
    Appeal wizard for branches that end with an action with an expired obligee deadline, or an
    expiration action.
    """
    pre_step_class = Paper
