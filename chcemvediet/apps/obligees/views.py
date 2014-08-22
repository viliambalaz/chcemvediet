# vim: expandtab
import json, re
from unidecode import unidecode

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render
from django.forms.models import model_to_dict
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.db.models import Q

import models

@require_http_methods([u'HEAD', u'GET'])
def index(request):
    obligee_list = models.Obligee.objects.all()
    paginator = Paginator(obligee_list, 25)

    page = request.GET.get(u'page')
    try:
        obligee_page = paginator.page(page)
    except PageNotAnInteger:
        obligee_page = paginator.page(1)
    except EmptyPage:
        obligee_page = paginator.page(paginator.num_pages)

    context = {u'obligee_page': obligee_page}
    return render(request, u'obligees/index.html', context)

@require_http_methods([u'HEAD', u'GET'])
def autocomplete(request):
    term = request.GET.get(u'term', u'')
    term = unidecode(term).lower() # transliterate unicode to ascii
    words = filter(None, re.split(r'[^a-z0-9]+', term))

    query = reduce(lambda p, q: p & q, (Q(slug__contains=u'-'+w) for w in words), Q())
    obligee_list = models.Obligee.objects.filter(query).order_by(u'name')[:10]

    data = [{
        u'label': obligee.name,
        u'obligee': model_to_dict(obligee),
    } for obligee in obligee_list]

    return HttpResponse(json.dumps(data), content_type=u'application/json')

