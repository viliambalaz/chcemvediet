# vim: expandtab
# -*- coding: utf-8 -*-
from django.contrib import admin

from poleno.utils.misc import decorate
from poleno.utils.admin import simple_list_filter_factory

from .models import Message, Recipient

class RecipientInline(admin.TabularInline):
    model = Recipient
    extra = 0
    ordering = [u'id']

@admin.register(Message, site=admin.site)
class MessageAdmin(admin.ModelAdmin):
    date_hierarchy = u'processed'
    list_display = [
            u'id',
            u'type',
            decorate(
                lambda o: o.from_formatted,
                short_description=u'From',
                admin_order_field=u'from_mail',
                ),
            decorate(
                lambda o: u'; '.join(u'%s: %s' % (k, v) for k, v in [
                    (u'To', o.to_formatted),
                    (u'Cc', o.cc_formatted),
                    (u'Bcc', o.bcc_formatted),
                    ] if v),
                short_description=u'Recipients',
                ),
            u'processed',
            ]
    list_filter = [
            u'type',
            simple_list_filter_factory(u'Processed', u'processed', [
                (u'1', u'Yes', lambda qs: qs.processed()),
                (u'0', u'No',  lambda qs: qs.not_processed()),
                ]),
            u'processed',
            ]
    search_fields = [
            u'=id',
            u'from_name',
            u'from_mail',
            u'recipient__name',
            u'recipient__mail',
            u'received_for',
            ]
    ordering = [
            u'-processed',
            u'-id',
            ]
    inlines = [
            RecipientInline,
            ]

    def get_queryset(self, request):
        queryset = super(MessageAdmin, self).get_queryset(request)
        queryset = queryset.prefetch_related(Message.prefetch_recipients())
        return queryset
