# vim: expandtab
# -*- coding: utf-8 -*-
from .models import Message, Recipient

def constants(request):
    return {
            u'MESSAGE_TYPES': Message.TYPES,
            u'RECIPIENT_TYPES': Recipient.TYPES,
            u'RECIPIENT_STATUSES': Recipient.STATUSES,
            }
