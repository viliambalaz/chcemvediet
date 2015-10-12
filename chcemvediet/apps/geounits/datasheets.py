# vim: expandtab
# -*- coding: utf-8 -*-
from collections import defaultdict

from poleno.datasheets import Field, ForeignKeyField
from poleno.datasheets import Columns, TextColumn, ForeignKeyColumn
from poleno.datasheets import RollingError, Sheet
from poleno.utils.misc import slugify

from .models import Region, District, Municipality, Neighbourhood


class GeounitsSheet(Sheet):

    def merge_duplicate_rows(self, rows, check_columns=None):
        errors = 0

        seen = {}
        if check_columns is None:
            check_columns = self.columns.__dict__.values()
        for row_idx, values in rows.items():
            pk = values[self.columns.pk.label]
            if pk in seen:
                del rows[row_idx]
                for column in check_columns:
                    if values[column.label] != seen[pk][column.label]:
                        self.cell_error(u'unification', row_idx, column,
                                u'Expecting {} but found {}',
                                column.coerced_repr(seen[pk][column.label]),
                                column.coerced_repr(values[column.label]))
                        errors += 1
            else:
                seen[pk] = values

        if errors:
            raise RollingError(errors)
        return rows

    def check_unique_slugs(self, rows, column):
        errors = 0

        seen = {}
        for row_idx, values in rows.items():
            value = values[column.label]
            slug = slugify(value)
            if slug in seen:
                del rows[row_idx]
                other_row, other_value = seen[slug]
                self.cell_error(u'unique_slug', row_idx, column,
                        u'Expecting value with unique slug but {} has the same slug as {} in row {}',
                        column.coerced_repr(value),
                        column.coerced_repr(other_value),
                        other_row)
                errors += 1
            else:
                seen[slug] = (row_idx, value)

        if errors:
            raise RollingError(errors)
        return rows

class RegionSheet(GeounitsSheet):
    label = u'REGPJ'
    model = Region
    ignore_superfluous_columns = True

    columns = Columns(
            # {{{
            pk=TextColumn(u'RSUJ3',
                # Merge duplicate rows; see process_rows()
                max_length=32,
                field=Field(),
                ),
            name=TextColumn(u'NAZKRJ = NAZRSUJ3',
                # Check that names have unique slugs; see process_rows()
                max_length=255,
                field=Field(),
                ),
            # }}}
            )

    def process_rows(self, rows):
        rows = super(RegionSheet, self).process_rows(rows)

        # Merge duplicate rows
        rows = self.merge_duplicate_rows(rows)

        # Check that names have unique slugs
        rows = self.check_unique_slugs(rows, self.columns.name)

        return rows

class DistrictSheet(GeounitsSheet):
    label = u'REGPJ'
    model = District
    ignore_superfluous_columns = True

    columns = Columns(
            # {{{
            pk=TextColumn(u'LSUJ1',
                # Merge duplicate rows; see process_rows()
                max_length=32,
                field=Field(),
                ),
            name=TextColumn(u'NAZOKS = NAZLSUJ1',
                # Check that names have unique slugs; see process_rows()
                max_length=255,
                field=Field(),
                ),
            region=ForeignKeyColumn(u'RSUJ3', Region,
                field=ForeignKeyField(),
                ),
            # }}}
            )

    def process_rows(self, rows):
        rows = super(DistrictSheet, self).process_rows(rows)

        # Merge duplicate rows
        rows = self.merge_duplicate_rows(rows)

        # Check that names have unique slugs
        rows = self.check_unique_slugs(rows, self.columns.name)

        return rows

class MunicipalitySheet(GeounitsSheet):
    label = u'REGPJ'
    model = Municipality
    ignore_superfluous_columns = True

    columns = Columns(
            # {{{
            pk=TextColumn(u'LSUJ2',
                # Merge duplicate rows; see process_rows()
                max_length=32,
                field=Field(),
                ),
            name=TextColumn(u'NAZZUJ = NAZLSUJ2',
                # Append district names to ambiguous names; see process_rows()
                # Check that names have unique slugs; see process_rows()
                max_length=255,
                field=Field(),
                ),
            district=ForeignKeyColumn(u'LSUJ1', District,
                field=ForeignKeyField(),
                ),
            region=ForeignKeyColumn(u'RSUJ3', Region,
                field=ForeignKeyField(),
                ),
            # }}}
            )

    def make_names_unique(self, rows):
        groups = defaultdict(list)
        for row_idx, values in rows.items():
            name = values[self.columns.name.label]
            slug = slugify(name)
            groups[slug].append(row_idx)
        for group in groups.values():
            if len(group) > 1:
                for row_idx in group:
                    name = rows[row_idx][self.columns.name.label]
                    district = rows[row_idx][self.columns.district.label]
                    new_name = u'{}, okres {}'.format(name, district.name)
                    rows[row_idx][self.columns.name.label] = new_name
        return rows

    def process_rows(self, rows):
        rows = super(MunicipalitySheet, self).process_rows(rows)

        # Merge duplicate rows
        rows = self.merge_duplicate_rows(rows)

        # Append district names to ambiguous names
        rows = self.make_names_unique(rows)

        # Check that names have unique slugs
        rows = self.check_unique_slugs(rows, self.columns.name)

        return rows

class NeighbourhoodSheet(GeounitsSheet):
    label = u'REGPJ'
    model = Neighbourhood
    ignore_superfluous_columns = True

    columns = Columns(
            # {{{
            pk=TextColumn(u'ICZSJ',
                # Skip duplicate rows ignoring inconsistencies; see process_rows()
                max_length=32,
                field=Field(),
                ),
            name=TextColumn(u'NAZZSJ',
                max_length=255,
                field=Field(),
                ),
            cadastre=TextColumn(u'NAZUTJ',
                max_length=255,
                field=Field(),
                ),
            municipality=ForeignKeyColumn(u'LSUJ2', Municipality,
                field=ForeignKeyField(),
                ),
            district=ForeignKeyColumn(u'LSUJ1', District,
                field=ForeignKeyField(),
                ),
            region=ForeignKeyColumn(u'RSUJ3', Region,
                field=ForeignKeyField(),
                ),
            # }}}
            )

    def process_rows(self, rows):
        rows = super(NeighbourhoodSheet, self).process_rows(rows)

        # Skip duplicate rows ignoring inconsistencies
        rows = self.merge_duplicate_rows(rows, check_columns=[])

        return rows
