# vim: expandtab
# -*- coding: utf-8 -*-
import itertools

def idgenerator(request):
    return {
            u'idgenerator': itertools.count(1),
            }
