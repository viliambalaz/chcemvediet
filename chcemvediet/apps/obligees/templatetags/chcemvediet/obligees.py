# vim: expandtab
# -*- coding: utf-8 -*-
from poleno.utils.template import Library
from chcemvediet.apps.obligees.models import Obligee


register = Library()

@register.simple_tag
def gender(gender, masculine, feminine, neuter, plurale):
    if gender == Obligee.GENDERS.MASCULINE:
        return masculine
    elif gender == Obligee.GENDERS.FEMININE:
        return feminine
    elif gender == Obligee.GENDERS.NEUTER:
        return neuter
    elif gender == Obligee.GENDERS.PLURALE:
        return plurale
    else:
        return u''
