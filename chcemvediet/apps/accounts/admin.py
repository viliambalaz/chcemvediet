# vim: expandtab
# -*- coding: utf-8 -*-
from django.contrib import admin

from poleno.utils.misc import decorate
from poleno.utils.admin import admin_obj_format

from .models import Profile


@admin.register(Profile, site=admin.site)
class ProfileAdmin(admin.ModelAdmin):
    date_hierarchy = None
    list_display = [
            u'id',
            decorate(
                lambda o: admin_obj_format(o.user,
                    u'{obj.first_name} {obj.last_name} <{obj.email}>'),
                short_description=u'User',
                admin_order_field=u'user__email',
                ),
            u'street',
            u'city',
            u'zip',
            ]
    list_filter = [
            ]
    search_fields = [
            u'=id',
            u'user__first_name',
            u'user__last_name',
            u'user__email',
            u'street',
            u'city',
            u'zip',
            ]
    ordering = [
            u'id',
            ]
    exclude = [
            ]
    readonly_fields = [
            ]
    raw_id_fields = [
            u'user',
            ]
    inlines = [
            ]

    def get_queryset(self, request):
        queryset = super(ProfileAdmin, self).get_queryset(request)
        queryset = queryset.select_related(u'user')
        return queryset
