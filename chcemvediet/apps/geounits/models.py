# vim: expandtab
# -*- coding: utf-8 -*-
from django.db import models

from poleno.utils.models import QuerySet
from poleno.utils.misc import squeeze, decorate, slugify


class RegionQuerySet(QuerySet):
    def order_by_pk(self):
        return self.order_by(u'pk')
    def order_by_name(self):
        return self.order_by(u'name') # no tiebreaker, name is unique

class Region(models.Model): # "Kraj"
    # Primary key
    id = models.CharField(max_length=32, primary_key=True,
            help_text=squeeze(u"""
                Region primary key. Example: "SK031" (REGPJ.RSUJ3)
                """))

    # Should NOT be empty
    name = models.CharField(max_length=255, unique=True,
            help_text=squeeze(u"""
                Unique human readable region name. (REGPJ.NAZKRJ, REGPJ.NAZRSUJ3)
                """))

    # Should NOT be empty; Read-only; Automaticly computed in save()
    slug = models.SlugField(max_length=255, unique=True,
            help_text=squeeze(u"""
                Unique slug to identify the region used in urls. Automaticly computed from the
                region name. May not be changed manually.
                """))

    # Backward relations:
    #
    #  -- district_set: by District.region
    #     May be empty
    #
    #  -- municipality_set: by Municipality.region
    #     May be empty
    #
    #  -- neighbourhood_set: by Neighbourhood.region
    #     May be empty

    # Indexes:
    #  -- id:   primary_key
    #  -- name: unique
    #  -- slug: unique

    objects = RegionQuerySet.as_manager()

    @decorate(prevent_bulk_create=True)
    def save(self, *args, **kwargs):
        update_fields = kwargs.get(u'update_fields', None)

        # Generate and save slug if saving name
        if update_fields is None or u'name' in update_fields:
            self.slug = slugify(self.name)
            if update_fields is not None:
                update_fields.append(u'slug')

        super(Region, self).save(*args, **kwargs)

    def __unicode__(self):
        return u'[%s] %s' % (self.pk, self.name)


class DistrictQuerySet(QuerySet):
    def order_by_pk(self):
        return self.order_by(u'pk')
    def order_by_name(self):
        return self.order_by(u'name') # no tiebreaker, name is unique

class District(models.Model): # "Okres"
    # Primary key
    id = models.CharField(max_length=32, primary_key=True,
            help_text=squeeze(u"""
                District primary key. Example: "SK031B" (REGPJ.LSUJ1)
                """))

    # Should NOT be empty
    name = models.CharField(max_length=255, unique=True,
            help_text=squeeze(u"""
                Unique human readable district name. (REGPJ.NAZOKS, REGPJ.NAZLSUJ1)
                """))

    # Should NOT be empty; Read-only; Automaticly computed in save()
    slug = models.SlugField(max_length=255, unique=True,
            help_text=squeeze(u"""
                Unique slug to identify the district used in urls. Automaticly computed from the
                district name. May not be changed manually.
                """))

    # May NOT be NULL
    region = models.ForeignKey(Region, help_text=u'Region the district belongs to.')

    # Backward relations:
    #
    #  -- municipality_set: by Municipality.district
    #     May be empty
    #
    #  -- neighbourhood_set: by Neighbourhood.district
    #     May be empty

    # Backward relations added to other models:
    #
    #  -- Region.district_set
    #     May be empty

    # Indexes:
    #  -- id:     primary_key
    #  -- name:   unique
    #  -- slug:   unique
    #  -- region: ForeignKey

    objects = DistrictQuerySet.as_manager()

    @decorate(prevent_bulk_create=True)
    def save(self, *args, **kwargs):
        update_fields = kwargs.get(u'update_fields', None)

        # Generate and save slug if saving name
        if update_fields is None or u'name' in update_fields:
            self.slug = slugify(self.name)
            if update_fields is not None:
                update_fields.append(u'slug')

        super(District, self).save(*args, **kwargs)

    def __unicode__(self):
        return u'[%s] %s' % (self.pk, self.name)


class MunicipalityQuerySet(QuerySet):
    def order_by_pk(self):
        return self.order_by(u'pk')
    def order_by_name(self):
        return self.order_by(u'name') # no tiebreaker, name is unique

class Municipality(models.Model): # "Obec"
    # Primary key
    id = models.CharField(max_length=32, primary_key=True,
            help_text=squeeze(u"""
                District primary key. Example: "SK031B518042" (REGPJ.LSUJ2)
                """))

    # Should NOT be empty
    name = models.CharField(max_length=255, unique=True,
            help_text=squeeze(u"""
                Unique human readable municipality name. If municipality name is ambiguous it
                should be amedned with its district name. (REGPJ.NAZZUJ, REGPJ.NAZLSUJ2)
                """))

    # Should NOT be empty; Read-only; Automaticly computed in save()
    slug = models.SlugField(max_length=255, unique=True,
            help_text=squeeze(u"""
                Unique slug to identify the municipality used in urls. Automaticly computed from
                the municipality name. May not be changed manually.
                """))

    # May NOT be NULL
    district = models.ForeignKey(District, help_text=u'District the municipality belongs to.')
    region = models.ForeignKey(Region, help_text=u'Region the municipality belongs to.')

    # Backward relations:
    #
    #  -- neighbourhood_set: by Neighbourhood.municipality
    #     May be empty

    # Backward relations added to other models:
    #
    #  -- District.municipality_set
    #     May be empty
    #
    #  -- Region.municipality_set
    #     May be empty

    # Indexes:
    #  -- id:       primary_key
    #  -- name:     unique
    #  -- slug:     unique
    #  -- region:   ForeignKey
    #  -- district: ForeignKey

    objects = MunicipalityQuerySet.as_manager()

    @decorate(prevent_bulk_create=True)
    def save(self, *args, **kwargs):
        update_fields = kwargs.get(u'update_fields', None)

        # Generate and save slug if saving name
        if update_fields is None or u'name' in update_fields:
            self.slug = slugify(self.name)
            if update_fields is not None:
                update_fields.append(u'slug')

        super(Municipality, self).save(*args, **kwargs)

    def __unicode__(self):
        return u'[%s] %s' % (self.pk, self.name)


class NeighbourhoodQuerySet(QuerySet):
    def order_by_pk(self):
        return self.order_by(u'pk')
    def order_by_name(self):
        return self.order_by(u'name', u'pk')

class Neighbourhood(models.Model): # "Základná sídelná jednotka"
    # Primary key
    id = models.CharField(max_length=32, primary_key=True,
            help_text=squeeze(u"""
                Neighbourhood primary key. Example: "26289" (REGPJ.ICZSJ)
                """))

    # Should NOT be empty
    name = models.CharField(max_length=255,
            help_text=squeeze(u"""
                Human readable neighbourhood name. The name is unique within its municipality.
                (REGPJ.NAZZSJ)
                """))

    # Should NOT be empty; Read-only; Automaticly computed in save()
    slug = models.SlugField(max_length=255,
            help_text=squeeze(u"""
                Slug to identify the neighbourhood used in urls. The slug is unique within the
                municipality. Automaticly computed from the neighbourhood name. May not be changed
                manually.
                """))

    # May NOT be NULL
    municipality = models.ForeignKey(Municipality,
            help_text=u'Municipality the neighbourhood belongs to.')
    district = models.ForeignKey(District,
            help_text=u'District the neighbourhood belongs to.')
    region = models.ForeignKey(Region,
            help_text=u'Region the neighbourhood belongs to.')

    # Backward relations added to other models:
    #
    #  -- Municipality.neighbourhood_set
    #     May be empty
    #
    #  -- District.neighbourhood_set
    #     May be empty
    #
    #  -- Region.neighbourhood_set
    #     May be empty

    # Indexes:
    #  -- id:                 primary_key
    #  -- name, municipality: unique_together
    #  -- slug, municipality: unique_together
    #  -- region:             ForeignKey
    #  -- district:           ForeignKey
    #  -- municipality:       ForeignKey

    objects = NeighbourhoodQuerySet.as_manager()

    class Meta:
        unique_together = [
                [u'name', u'municipality'],
                [u'slug', u'municipality'],
                ]

    @decorate(prevent_bulk_create=True)
    def save(self, *args, **kwargs):
        update_fields = kwargs.get(u'update_fields', None)

        # Generate and save slug if saving name
        if update_fields is None or u'name' in update_fields:
            self.slug = slugify(self.name)
            if update_fields is not None:
                update_fields.append(u'slug')

        super(Neighbourhood, self).save(*args, **kwargs)

    def __unicode__(self):
        return u'[%s] %s' % (self.pk, self.name)
