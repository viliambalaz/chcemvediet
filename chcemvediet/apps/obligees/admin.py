# vim: expandtab
# -*- coding: utf-8 -*-
from django.contrib import admin

from poleno.utils.misc import decorate
from poleno.utils.admin import admin_obj_format

from .models import Obligee, HistoricalObligee

@admin.register(Obligee, site=admin.site)
class ObligeeAdmin(admin.ModelAdmin):
    list_display = [
            u'id',
            u'name',
            u'street',
            u'city',
            u'zip',
            u'status',
            ]
    list_filter = [
            u'status',
            ]
    search_fields = [
            u'=id',
            u'name',
            u'street',
            u'city',
            u'zip',
            u'emails',
            ]
    ordering = [
            u'id',
            ]

@admin.register(HistoricalObligee, site=admin.site)
class HistoricalObligeeAdmin(admin.ModelAdmin):
    date_hierarchy = u'history_date'
    list_display = [
            u'id',
            decorate(
                lambda o: admin_obj_format(o.history_object),
                short_description=u'Obligee',
                admin_order_field=u'id',
                ),
            u'name',
            u'status',
            u'history_date',
            u'history_type',
            ]
    list_filter = [
            u'status',
            u'history_date',
            u'history_type',
            ]
    search_fields = [
            u'=id',
            u'name',
            ]
    ordering = [
            u'id',
            ]
    raw_id_fields = [
            u'history_user',
            ]
