# vim: expandtab
# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
from django.contrib import admin

from poleno.utils.misc import decorate, filesize
from poleno.utils.admin import admin_obj_format

from .views import download
from .models import Attachment

@admin.register(Attachment, site=admin.site)
class AttachmentAdmin(admin.ModelAdmin):
    date_hierarchy = u'created'
    list_display = [
            u'id',
            decorate(
                lambda o: admin_obj_format(o.generic_object),
                short_description=u'Generic Object',
                admin_order_field=u'generic_type__name',
                ),
            decorate(
                lambda o: admin_obj_format(o, u'{obj.file.name}', link=u'download'),
                short_description=u'File',
                admin_order_field=u'file',
                ),
            u'name',
            u'content_type',
            u'created',
            decorate(
                lambda o: filesize(o.size),
                short_description=u'Size',
                admin_order_field=u'size',
                ),
            ]
    list_filter = [
            u'created',
            u'content_type',
            u'generic_type',
            ]
    search_fields = [
            u'=id',
            u'=generic_id',
            u'generic_type__name',
            u'file',
            u'name',
            u'content_type',
            ]
    ordering = [
            u'-id',
            ]
    exclude = [
            u'file',
            ]

    def get_queryset(self, request):
        queryset = super(AttachmentAdmin, self).get_queryset(request)
        queryset = queryset.prefetch_related(u'generic_object')
        return queryset

    def download_view(self, request, attachment_pk):
        attachment = Attachment.objects.get_or_404(pk=attachment_pk)
        return download(request, attachment)

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        download_view = self.admin_site.admin_view(self.download_view)
        urls = patterns('',
                url(r'^(.+)/download/$', download_view, name=u'%s_%s_download' % info),
                )
        return urls + super(AttachmentAdmin, self).get_urls()
