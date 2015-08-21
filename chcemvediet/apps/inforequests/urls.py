# vim: expandtab
# -*- coding: utf-8 -*-
from django.conf import settings
from django.conf.urls import patterns, url
from django.utils.translation import ugettext_lazy as _

from poleno.utils.lazy import lazy_concat, lazy_format

from . import views

parts = {
    u'inforequest_pk':         r'(?P<inforequest_pk>\d+)/',
    u'inforequest_slug_pk': r'(?:(?P<inforequest_slug>[a-z0-9-]+)-)?(?P<inforequest_pk>\d+)/',
    u'branch_pk':              r'(?P<branch_pk>\d+)/',
    u'action_pk':              r'(?P<action_pk>\d+)/',
    u'draft_pk':               r'(?P<draft_pk>\d+)/',
    u'draft_pk?':           r'(?:(?P<draft_pk>\d+)/)?',
    u'attachment_pk':          r'(?P<attachment_pk>\d+)/',
    u'step_idx':               r'(?P<step_idx>\d+)/',
    u'step_idx?':           r'(?:(?P<step_idx>\d+)/)?',
    u'create':                 lazy_concat(_(u'inforequests:urls:create'), u'/'),
    u'delete_draft':           lazy_concat(_(u'inforequests:urls:delete_draft'), u'/'),
    u'obligee_action':         lazy_concat(_(u'inforequests:urls:obligee_action'), u'/'),
    u'clarification_response': lazy_concat(_(u'inforequests:urls:clarification_response'), u'/'),
    u'appeal':                 lazy_concat(_(u'inforequests:urls:appeal'), u'/'),
    u'extend_deadline':        lazy_concat(_(u'inforequests:urls:extend_deadline'), u'/'),
    u'attachments':            lazy_concat(_(u'inforequests:urls:attachments'), u'/'),
    }

urlpatterns = patterns(u'',
    url(lazy_format(r'^$'),                                                                             views.inforequest_index,        name=u'index'),
    url(lazy_format(r'^{create}{draft_pk?}$', **parts),                                                 views.inforequest_create,       name=u'create'),
    url(lazy_format(r'^{delete_draft}{draft_pk}$', **parts),                                            views.inforequest_delete_draft, name=u'delete_draft'),
    url(lazy_format(r'^{inforequest_slug_pk}$', **parts),                                               views.inforequest_detail,       name=u'detail'),
    url(lazy_format(r'^{inforequest_slug_pk}{obligee_action}{step_idx?}$', **parts),                    views.obligee_action,           name=u'obligee_action'),
    url(lazy_format(r'^{inforequest_slug_pk}{clarification_response}{branch_pk}{step_idx?}$', **parts), views.clarification_response,   name=u'clarification_response'),
    url(lazy_format(r'^{inforequest_slug_pk}{appeal}{branch_pk}{step_idx?}$', **parts),                 views.appeal,                   name=u'appeal'),
    url(lazy_format(r'^{inforequest_slug_pk}{extend_deadline}{branch_pk}{action_pk}$', **parts),        views.extend_deadline,          name=u'extend_deadline'),
    url(lazy_format(r'^{attachments}$', **parts),                                                       views.attachment_upload,        name=u'upload_attachment'),
    url(lazy_format(r'^{attachments}{attachment_pk}$', **parts),                                        views.attachment_download,      name=u'download_attachment'),
)

if settings.DEBUG: # pragma: no cover
    urlpatterns += patterns(u'',
        url(lazy_format(r'^devtools/mock-response/{inforequest_pk}$', **parts),    views.devtools_mock_response,    name=u'devtools_mock_response'),
        url(lazy_format(r'^devtools/undo-last-action/{inforequest_pk}$', **parts), views.devtools_undo_last_action, name=u'devtools_undo_last_action'),
        url(lazy_format(r'^devtools/push-history/{inforequest_pk}$', **parts),     views.devtools_push_history,     name=u'devtools_push_history'),
    )
