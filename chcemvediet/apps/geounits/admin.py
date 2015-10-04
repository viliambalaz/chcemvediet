# vim: expandtab
# -*- coding: utf-8 -*-
from django.contrib import admin

from poleno.utils.misc import decorate
from poleno.utils.admin import admin_obj_format

from .models import Region, District, Municipality, Neighbourhood


@admin.register(Region, site=admin.site)
class RegionAdmin(admin.ModelAdmin):
    list_display = [
            u'id',
            u'name',
            ]
    list_filter = [
            ]
    search_fields = [
            u'=id',
            u'name',
            ]
    ordering = [
            u'id',
            ]
    readonly_fields = [
            u'slug',
            ]
    raw_id_fields = [
            ]

@admin.register(District, site=admin.site)
class DistrictAdmin(admin.ModelAdmin):
    list_display = [
            u'id',
            u'name',
            decorate(
                lambda o: admin_obj_format(o.region, u'{obj.name}'),
                short_description=u'Region',
                admin_order_field=u'region__name',
                ),
            ]
    list_filter = [
            u'region__name',
            ]
    search_fields = [
            u'=id',
            u'name',
            u'=region__id',
            u'region__name',
            ]
    ordering = [
            u'id',
            ]
    readonly_fields = [
            u'slug',
            ]
    raw_id_fields = [
            u'region',
            ]

@admin.register(Municipality, site=admin.site)
class MunicipalityAdmin(admin.ModelAdmin):
    list_display = [
            u'id',
            u'name',
            decorate(
                lambda o: admin_obj_format(o.district, u'{obj.name}'),
                short_description=u'District',
                admin_order_field=u'district__name',
                ),
            decorate(
                lambda o: admin_obj_format(o.region, u'{obj.name}'),
                short_description=u'Region',
                admin_order_field=u'region__name',
                ),
            ]
    list_filter = [
            u'district__name',
            u'region__name',
            ]
    search_fields = [
            u'=id',
            u'name',
            u'=district__id',
            u'district__name',
            u'=region__id',
            u'region__name',
            ]
    ordering = [
            u'id',
            ]
    readonly_fields = [
            u'slug',
            ]
    raw_id_fields = [
            u'district',
            u'region',
            ]

@admin.register(Neighbourhood, site=admin.site)
class NeighbourhoodAdmin(admin.ModelAdmin):
    list_display = [
            u'id',
            u'name',
            decorate(
                lambda o: admin_obj_format(o.municipality, u'{obj.name}'),
                short_description=u'Municipality',
                admin_order_field=u'municipality__name',
                ),
            decorate(
                lambda o: admin_obj_format(o.district, u'{obj.name}'),
                short_description=u'District',
                admin_order_field=u'district__name',
                ),
            decorate(
                lambda o: admin_obj_format(o.region, u'{obj.name}'),
                short_description=u'Region',
                admin_order_field=u'region__name',
                ),
            ]
    list_filter = [
            u'district__name',
            u'region__name',
            ]
    search_fields = [
            u'=id',
            u'name',
            u'=municipality__id',
            u'municipality__name',
            u'=district__id',
            u'district__name',
            u'=region__id',
            u'region__name',
            ]
    ordering = [
            u'id',
            ]
    readonly_fields = [
            u'slug',
            ]
    raw_id_fields = [
            u'municipality',
            u'district',
            u'region',
            ]
