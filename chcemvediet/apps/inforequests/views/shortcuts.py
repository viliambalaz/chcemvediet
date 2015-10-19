# vim: expandtab
# -*- coding: utf-8 -*-
from django.shortcuts import render
from django.template import RequestContext

from poleno.utils.http import JsonOperations, JsonContent, JsonCloseModal
from poleno.utils.template import render_to_string


def render_form(request, form, **context):
    return render(request, form.template, dict(context, form=form))

def json_form(request, form, **context):
    return JsonOperations(
            JsonContent(target=None, content=render_to_string(
                form.template, dict(context, form=form))),
            )

def json_success(request, inforequest):
    return JsonOperations(
            JsonCloseModal(),
            JsonContent(target=u'#content', content=render_to_string(
                u'inforequests/detail/detail.html', dict(inforequest=inforequest))),
            )
