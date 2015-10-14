# vim: expandtab
# -*- coding: utf-8 -*-
from .models import Action, InforequestEmail

def constants(request):
    return {
            u'ACTION_TYPES': Action.TYPES,
            u'ACTION_CONTENT_TYPES': Action.CONTENT_TYPES,
            u'ACTION_DISCLOSURE_LEVELS': Action.DISCLOSURE_LEVELS,
            u'ACTION_REFUSAL_REASONS': Action.REFUSAL_REASONS,
            u'INFOREQUESTEMAIL_TYPES': InforequestEmail.TYPES,
            }
