# vim: expandtab
# -*- coding: utf-8 -*-
from .models import Obligee

def constants(request):
    return {
            u'OBLIGEE_GENDERS': Obligee.GENDERS,
            u'OBLIGEE_TYPES': Obligee.TYPES,
            u'OBLIGEE_STATUSES': Obligee.STATUSES,
            }
