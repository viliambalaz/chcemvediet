# vim: expandtab
# -*- coding: utf-8 -*-
from django.contrib import admin

from poleno.utils.misc import decorate
from poleno.utils.admin import admin_obj_format

from .models import ObligeeTag, ObligeeGroup, Obligee, HistoricalObligee, ObligeeAlias

@admin.register(ObligeeTag, site=admin.site)
class ObligeeTagAdmin(admin.ModelAdmin):
    list_display = [
            u'id',
            u'key',
            u'name',
            ]
    list_filter = [
            ]
    search_fields = [
            u'=id',
            u'key',
            u'name',
            ]
    ordering = [
            u'id',
            ]
    readonly_fields = [
            u'slug',
            ]

@admin.register(ObligeeGroup, site=admin.site)
class ObligeeGroupAdmin(admin.ModelAdmin):
    list_display = [
            u'id',
            u'key',
            u'name',
            ]
    list_filter = [
            ]
    search_fields = [
            u'=id',
            u'key',
            u'name',
            ]
    ordering = [
            u'id',
            ]
    readonly_fields = [
            u'slug',
            ]

@admin.register(Obligee, site=admin.site)
class ObligeeAdmin(admin.ModelAdmin):
    list_display = [
            u'id',
            u'name',
            u'city',
            u'type',
            u'status',
            decorate(
                lambda o: u' '.join(t.key for t in o.tags.all()),
                short_description=u'Tags',
                ),
            decorate(
                lambda o: u' '.join(t.key for t in o.groups.all()),
                short_description=u'Groups',
                ),
            ]
    list_filter = [
            u'type',
            u'status',
            ]
    search_fields = [
            u'=id',
            u'name',
            u'ico',
            u'city',
            u'emails',
            u'tags__key',
            u'groups__key',
            ]
    ordering = [
            u'id',
            ]
    readonly_fields = [
            u'slug',
            ]
    raw_id_fields = [
            u'tags',
            u'groups',
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

@admin.register(ObligeeAlias, site=admin.site)
class ObligeeAliasAdmin(admin.ModelAdmin):
    list_display = [
            u'id',
            decorate(
                lambda o: admin_obj_format(o.obligee, u'{obj.name}'),
                short_description=u'Obligee',
                admin_order_field=u'obligee__name',
                ),
            u'name',
            ]
    list_filter = [
            u'obligee__type',
            u'obligee__status',
            ]
    search_fields = [
            u'=id',
            u'name',
            u'obligee__name',
            ]
    ordering = [
            u'id',
            ]
    readonly_fields = [
            u'slug',
            ]
    raw_id_fields = [
            u'obligee',
            ]
