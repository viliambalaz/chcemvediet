# vim: expandtab
# -*- coding: utf-8 -*-
import re

from django.core.management.base import CommandError
from django.conf import settings

from poleno.datasheets import Field, FieldChoicesField, ForeignKeyField, ManyToManyField
from poleno.datasheets import Columns, TextColumn, IntegerColumn, FloatColumn
from poleno.datasheets import FieldChoicesColumn, ForeignKeyColumn, ManyToManyColumn
from poleno.datasheets import RollingError, Sheet
from poleno.utils.forms import validate_comma_separated_emails
from poleno.utils.misc import squeeze
from chcemvediet.apps.geounits.models import Neighbourhood
from chcemvediet.apps.inforequests.models import Inforequest

from .models import ObligeeTag, ObligeeGroup, Obligee, HistoricalObligee, ObligeeAlias


class ObligeeTagSheet(Sheet):
    label = u'Tagy'
    model = ObligeeTag

    columns = Columns(
            # {{{
            pk=IntegerColumn(u'ID',
                unique=True, min_value=1,
                field=Field(),
                ),
            key=TextColumn(u'Kod',
                unique=True, max_length=255, regex=re.compile(r'^[\w-]+$'),
                field=Field(confirm_changed=True),
                ),
            name=TextColumn(u'Nazov',
                unique_slug=True, max_length=255,
                field=Field(),
                ),
            # }}}
            )

class ObligeeGroupSheet(Sheet):
    label = u'Hierarchia'
    model = ObligeeGroup

    columns = Columns(
            # {{{
            pk=IntegerColumn(u'ID',
                unique=True, min_value=1,
                field=Field(),
                ),
            key=TextColumn(u'Kod',
                # Checked that every subgroup has its parent group; See process_rows()
                unique=True, max_length=255, regex=re.compile(r'^[\w-]+(/[\w-]+)*$'),
                field=Field(confirm_changed=True),
                ),
            name=TextColumn(u'Nazov v hierarchii',
                unique_slug=True, max_length=255,
                field=Field(),
                ),
            description=TextColumn(u'Popis',
                blank=True,
                field=Field(),
                ),
            # }}}
            )

    def process_rows(self, rows):
        rows = super(ObligeeGroupSheet, self).process_rows(rows)
        errors = 0

        # Check that every subgroup has its parent group
        keys = set()
        for values in rows.values():
            key = values[self.columns.key.label]
            keys.add(key)
        for row_idx, values in rows.items():
            key = values[self.columns.key.label]
            if u'/' not in key:
                continue
            parent_key = key.rsplit(u'/', 1)[0]
            if parent_key not in keys:
                self.cell_error(u'no_parent_group', row_idx, self.columns.key,
                        u'Group {} has no parent; Group {} not found',
                        self.columns.key.coerced_repr(key),
                        self.columns.key.coerced_repr(parent_key))
                errors += 1

        if errors:
            raise RollingError(errors)
        return rows

class ObligeeSheet(Sheet):
    label = u'Obligees'
    model = Obligee
    delete_omitted = False

    columns = Columns(
            # {{{
            pk=IntegerColumn(u'ID',
                unique=True, min_value=1,
                field=Field(),
                ),
            official_name=TextColumn(u'Oficialny nazov',
                max_length=255,
                field=Field(confirm_changed=True),
                ),
            name=TextColumn(u'Rozlisovaci nazov nominativ',
                unique_slug=True, max_length=255,
                field=Field(confirm_unchanged_if_changed=u'official_name'),
                ),
            name_genitive=TextColumn(u'Rozlisovaci nazov genitiv',
                max_length=255,
                field=Field(confirm_unchanged_if_changed=u'name'),
                ),
            name_dative=TextColumn(u'Rozlisovaci nazov dativ',
                max_length=255,
                field=Field(confirm_unchanged_if_changed=u'name'),
                ),
            name_accusative=TextColumn(u'Rozlisovaci nazov akuzativ',
                max_length=255,
                field=Field(confirm_unchanged_if_changed=u'name'),
                ),
            name_locative=TextColumn(u'Rozlisovaci nazov lokal',
                max_length=255,
                field=Field(confirm_unchanged_if_changed=u'name'),
                ),
            name_instrumental=TextColumn(u'Rozlisovaci nazov instrumental',
                max_length=255,
                field=Field(confirm_unchanged_if_changed=u'name'),
                ),
            gender=FieldChoicesColumn(u'Rod', Obligee.GENDERS,
                choices={
                    u'muzsky': Obligee.GENDERS.MASCULINE,
                    u'zensky': Obligee.GENDERS.FEMININE,
                    u'stredny': Obligee.GENDERS.NEUTER,
                    u'pomnozny': Obligee.GENDERS.PLURALE,
                    },
                field=FieldChoicesField(Obligee.GENDERS),
                ),
            ico=TextColumn(u'ICO',
                blank=True, max_length=32,
                field=Field(),
                ),
            street=TextColumn(u'Adresa: Ulica s cislom',
                max_length=255,
                field=Field(),
                ),
            city=TextColumn(u'Adresa: Obec',
                max_length=255,
                field=Field(),
                ),
            zip=TextColumn(u'Adresa: PSC',
                max_length=10, regex=re.compile(r'^\d\d\d \d\d$'),
                field=Field(),
                ),
            iczsj=ForeignKeyColumn(u'ICZSJ', Neighbourhood,
                field=ForeignKeyField(),
                ),
            emails=TextColumn(u'Adresa: Email',
                # Overridden with dummy emails for local and dev server modes; See process_row()
                blank=True, max_length=1024, validators=validate_comma_separated_emails,
                field=Field(),
                ),
            latitude=FloatColumn(u'Lat',
                min_value=-90.0, max_value=90.0,
                field=Field(),
                ),
            longitude=FloatColumn(u'Lon',
                min_value=-180.0, max_value=180.0,
                field=Field(),
                ),
            tags=ManyToManyColumn(u'Tagy', ObligeeTag,
                to_field=u'key', blank=True,
                field=ManyToManyField(),
                ),
            groups=ManyToManyColumn(u'Hierarchia', ObligeeGroup,
                to_field=u'key',
                field=ManyToManyField(),
                ),
            type=FieldChoicesColumn(u'Typ', Obligee.TYPES,
                choices={
                    u'odsek 1': Obligee.TYPES.SECTION_1,
                    u'odsek 2': Obligee.TYPES.SECTION_2,
                    u'odsek 3': Obligee.TYPES.SECTION_3,
                    u'odsek 4': Obligee.TYPES.SECTION_4,
                    },
                field=FieldChoicesField(Obligee.TYPES),
                ),
            official_description=TextColumn(u'Oficialny popis',
                blank=True,
                field=Field(),
                ),
            simple_description=TextColumn(u'Zrozumitelny popis',
                blank=True,
                field=Field(),
                ),
            status=FieldChoicesColumn(u'Stav', Obligee.STATUSES,
                choices={
                    u'aktivny': Obligee.STATUSES.PENDING,
                    u'neaktivny': Obligee.STATUSES.DISSOLVED,
                    },
                field=FieldChoicesField(Obligee.STATUSES, confirm_changed=True),
                ),
            notes=TextColumn(u'Poznamka',
                blank=True,
                field=Field(),
                ),
            # }}}
            )

    def do_reset(self):
        count = Inforequest.objects.count()
        if count:
            inputed = self.importer.input_yes_no(squeeze(u"""
                    Discarding current obligees will discard all existing inforequests as well.
                    There are {} inforequests.
                    """),
                    u'Are you sure, you want to discard them?', count, default=u'N')
            if inputed != u'Y':
                raise CommandError(squeeze(u"""
                        Existing inforequests prevented us from discarding current obligees.
                        """))
        self.reset_model(Obligee)
        self.reset_model(HistoricalObligee)
        self.reset_model(Inforequest)

    def process_row(self, row_idx, row):
        values = super(ObligeeSheet, self).process_row(row_idx, row)

        # Dummy emails for local and dev server modes
        if hasattr(settings, u'OBLIGEE_DUMMY_MAIL'):
            name = values[self.columns.name.label]
            dummy_email = Obligee.dummy_email(name, settings.OBLIGEE_DUMMY_MAIL)
            values[self.columns.emails.label] = dummy_email

        return values

class ObligeeAliasSheet(Sheet):
    label = u'Aliasy'
    model = ObligeeAlias

    columns = Columns(
            # {{{
            pk=IntegerColumn(u'ID',
                unique=True, min_value=1,
                field=Field(),
                ),
            obligee=ForeignKeyColumn(u'ID institucie', Obligee,
                field=ForeignKeyField(confirm_changed=True),
                ),
            obligee_name=TextColumn(u'Rozlisovaci nazov institucie',
                # Checked that obligee_name is obligee.name; See process_row()
                ),
            name=TextColumn(u'Alternativny nazov',
                unique_slug=True, max_length=255,
                field=Field(),
                ),
            description=TextColumn(u'Vysvetlenie',
                blank=True,
                field=Field(),
                ),
            notes=TextColumn(u'Poznamka',
                blank=True,
                field=Field(),
                ),
            # }}}
            )

    def process_row(self, row_idx, row):
        values = super(ObligeeAliasSheet, self).process_row(row_idx, row)

        # Check that obligee_name is obligee.name
        value = values[self.columns.obligee_name.label]
        obligee = values[self.columns.obligee.label]
        if value != obligee.name:
            self.cell_error(u'obligee_name', row_idx, self.columns.obligee_name,
                    u'Expecting {} but found {}',
                    self.columns.obligee_name.coerced_repr(obligee.name),
                    self.columns.obligee_name.coerced_repr(value))
            raise RollingError

        return values
