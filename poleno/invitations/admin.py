# vim: expandtab
# -*- coding: utf-8 -*-
from django.contrib import admin

from poleno.utils.misc import decorate
from poleno.utils.admin import simple_list_filter_factory, admin_obj_format

from .models import Invitation, InvitationSupply

@admin.register(Invitation, site=admin.site)
class InvitationAdmin(admin.ModelAdmin):
    date_hierarchy = u'created'
    list_display = [
            u'id',
            u'email',
            u'created',
            decorate(
                lambda o: u'Accepted' if o.is_accepted else
                          u'Expired' if o.is_expired else
                          u'Pending' if o.is_pending else u'--',
                short_description=u'State',
                ),
            decorate(
                lambda o: admin_obj_format(o.invitor, u'{obj.first_name} {obj.last_name} <{obj.email}>'),
                short_description=u'Invitor',
                admin_order_field=u'invitor__email',
                ),
            decorate(
                lambda o: admin_obj_format(o.invitee, u'{obj.first_name} {obj.last_name} <{obj.email}>'),
                short_description=u'Invitee',
                admin_order_field=u'invitee__email',
                ),
            ]
    list_filter = [
            u'created',
            simple_list_filter_factory(u'State', u'state', [
                (u'1', u'Accepted', lambda qs: qs.accepted()),
                (u'2', u'Expired',  lambda qs: qs.expired()),
                (u'3', u'Pending',  lambda qs: qs.pending()),
                ]),
            ]
    search_fields = [
            u'=id',
            u'email',
            u'invitor__first_name',
            u'invitor__last_name',
            u'invitor__email',
            u'invitee__first_name',
            u'invitee__last_name',
            u'invitee__email',
            ]
    ordering = [
            u'-created',
            u'-id',
            ]
    raw_id_fields = [
            u'invitor',
            u'invitee',
            u'message',
            ]

    def get_queryset(self, request):
        queryset = super(InvitationAdmin, self).get_queryset(request)
        queryset = queryset.select_related(u'invitor')
        queryset = queryset.select_related(u'invitee')
        return queryset

@admin.register(InvitationSupply, site=admin.site)
class InvitationSupplyAdmin(admin.ModelAdmin):
    list_display = [
            u'id',
            decorate(
                lambda o: admin_obj_format(o.user, u'{obj.first_name} {obj.last_name} <{obj.email}>'),
                short_description=u'User',
                admin_order_field=u'user__email',
                ),
            u'enabled',
            u'unlimited',
            u'supply',
            ]
    list_filter = [
            u'enabled',
            u'unlimited',
            ]
    search_fields = [
            u'=id',
            u'user__first_name',
            u'user__last_name',
            u'user__email',
            ]
    ordering = [
            u'id',
            ]
    raw_id_fields = [
            u'user',
            ]

    def get_queryset(self, request):
        queryset = super(InvitationSupplyAdmin, self).get_queryset(request)
        queryset = queryset.select_related(u'user')
        return queryset
