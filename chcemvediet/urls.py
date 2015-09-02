# vim: expandtab
# -*- coding: utf-8 -*-
from django.conf import settings
from django.conf.urls import patterns, include, url
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.utils.translation import ugettext_lazy as _

from poleno.utils.lazy import lazy_format

urlpatterns = patterns(u'',
    url(r'^mandrill/', include(u'poleno.mail.transports.mandrill.urls', namespace=u'mandrill')),
    url(r'^i18n/', include(u'django.conf.urls.i18n')),
)

urlpatterns += i18n_patterns(u'',
    url(lazy_format(r'^{0}/', _(u'main:urls:obligees')),     include(u'chcemvediet.apps.obligees.urls', namespace=u'obligees')),
    url(lazy_format(r'^{0}/', _(u'main:urls:inforequests')), include(u'chcemvediet.apps.inforequests.urls', namespace=u'inforequests')),
    url(lazy_format(r'^{0}/', _(u'main:urls:invitations')),  include(u'poleno.invitations.urls', namespace=u'invitations')),
    url(r'^accounts/', include(u'allauth.urls')),
    url(r'^accounts/', include(u'chcemvediet.apps.accounts.urls', namespace=u'accounts')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'', include(u'poleno.pages.urls', namespace=u'pages')),
)

if settings.DEBUG: # pragma: no cover
    urlpatterns = patterns(u'',
        url(r'^media/(?P<path>.*)$', u'django.views.static.serve', {u'document_root': settings.MEDIA_ROOT, u'show_indexes': True}),
        url(r'', include(u'django.contrib.staticfiles.urls')),
    ) + urlpatterns
