# vim: expandtab
# -*- coding: utf-8 -*-
import re
from numbers import Real, Integral
from collections import defaultdict
from optparse import make_option
from openpyxl import load_workbook

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import color_style
from django.db import transaction
from django.conf import settings

from poleno.utils.forms import validate_comma_separated_emails
from poleno.utils.misc import squeeze, slugify
from chcemvediet.apps.obligees.models import ObligeeTag, ObligeeGroup, Obligee, HistoricalObligee
from chcemvediet.apps.inforequests.models import Inforequest


zip_regex = re.compile(r'^\d\d\d \d\d$')
tag_regex = re.compile(r'^[\w-]+$')
tags_regex_0 = re.compile(r'^([\w-]+(\s+[\w-]+)*)?$') # 0 or more tags
tags_regex_1 = re.compile(r'^[\w-]+(\s+[\w-]+)*$') # 1 or more tags
group_regex = re.compile(r'^[\w-]+(/[\w-]+)*$')
groups_regex_0 = re.compile(r'^([\w-]+(/[\w-]+)*(\s+[\w-]+(/[\w-]+)*)*)?$') # 0 or more groups
groups_regex_1 = re.compile(r'^[\w-]+(/[\w-]+)*(\s+[\w-]+(/[\w-]+)*)*$') # 1 or more groups


class RollingCommandError(CommandError):
    def __init__(self, count=1):
        self.count = count
        super(CommandError, self).__init__(
                u'Detected {} errors; Rolled back'.format(count))

class RollbackDryRun(Exception):
    pass


class Columns(object):
    def __init__(self, **kwargs):
        vars(self).update(kwargs)

class Column(object):
    def __init__(self, label, field=None, typ=None, default=None,
            min_value=None, max_value=None, min_length=None, max_length=None, nonempty=None,
            choices=None, regex=None, unique=None, unique_slug=None, validators=None,
            confirm_changed=None, confirm_unchanged_if_changed=None, value_repr=None):

        tuple_unless_none = (lambda v: v if v is None or isinstance(v, (list, tuple)) else (v,))

        self.label = label
        self.field = field
        self.typ = tuple_unless_none(typ)
        self.default = default
        self.min_value = min_value
        self.max_value = max_value
        self.min_length = min_length
        self.max_length = max_length
        self.nonempty = nonempty
        self.choices = choices
        self.regex = regex
        self.unique = unique
        self.unique_slug = unique_slug
        self.validators = tuple_unless_none(validators)
        self.confirm_changed = confirm_changed
        self.confirm_unchanged_if_changed = tuple_unless_none(confirm_unchanged_if_changed)
        self._value_repr = value_repr

    def value_repr(self, value):
        if self._value_repr is not None:
            return self._value_repr(value)
        elif isinstance(value, Real):
            return u'{}'.format(value)
        else:
            return u'"{}"'.format(value)

class Sheet(object):
    label = None
    model = None
    delete_omitted = None
    columns = None

    def __init__(self, book):
        self.book = book
        self.importer = book.importer
        self.ws = book.wb[self.label]
        self.column_map = None

    def error(self, code, msg, *args, **kwargs):
        if code:
            code = (self.label, code)
        self.importer.error(code, msg, *args, **kwargs)

    def validate_structure(self):
        errors = 0

        self.column_map = {}
        row = next(self.ws.rows, [])
        for idx, column in enumerate(row):
            if column.value is not None and not column.value.startswith(u'#'):
                self.column_map[column.value] = idx

        expected_columns = set(c.label for c in self.columns.__dict__.values())
        found_columns = set(self.column_map)
        missing_columns = expected_columns - found_columns
        superfluous_columns = found_columns - expected_columns
        for column in missing_columns:
            self.error(None, u'Sheet "{}" does not contain required column: {}', self.label, column)
            errors += 1
        for column in superfluous_columns:
            self.error(None, u'Sheet "{}" contains unexpected column: {}', self.label, column)
            errors += 1

        if errors:
            raise RollingCommandError(errors)

    def cell_error(self, code, idx, column, msg, *args, **kwargs):
        self.error((column.label, code), u'Invalid value in row {} of "{}.{}": {}',
                idx+1, self.label, column.label, msg.format(*args, **kwargs))
        raise RollingCommandError

    def validate_type(self, value, idx, column):
        if column.typ is None:
            return value
        if not isinstance(value, column.typ):
            self.cell_error(u'type', idx, column, u'Expecting {} but found {}',
                    u', '.join(t.__name__ for t in column.typ), value.__class__.__name__)
        return value

    def validate_min_value(self, value, idx, column):
        if column.min_value is None:
            return value
        if value < column.min_value:
            self.cell_error(u'min_value', idx, column,
                    u'Expecting value not smaller than {} but found "{}"',
                    column.min_value, value)
        return value

    def validate_max_value(self, value, idx, column):
        if column.max_value is None:
            return value
        if value > column.max_value:
            self.cell_error(u'max_value', idx, column,
                    u'Expecting value not bigger than "{}" but found "{}"',
                    column.max_value, value)
        return value

    def validate_min_length(self, value, idx, column):
        if column.min_length is None:
            return value
        if len(value) < column.min_length:
            self.cell_error(u'min_length', idx, column,
                    u'Expecting value not shorter than {} but found "{}" with length {}',
                    column.min_length, value, len(value))
        return value

    def validate_max_length(self, value, idx, column):
        if column.max_length is None:
            return value
        if len(value) > column.max_length:
            self.cell_error(u'max_length', idx, column,
                    u'Expecting value not longer than {} but found "{}" with length {}',
                    column.max_length, value, len(value))
        return value

    def validate_nonempty(self, value, idx, column):
        if not column.nonempty:
            return value
        if not value:
            self.cell_error(u'nonempty', idx, column,
                    u'Expecting nonempty value but found "{}"', value)
        return value

    def validate_choices(self, value, idx, column):
        if column.choices is None:
            return value
        if value not in column.choices:
            self.cell_error(u'choices', idx, column, u'Expecting one of {} but found "{}"',
                    u', '.join(u'"{}"'.format(c) for c in column.choices), value)
        if isinstance(column.choices, dict):
            value = column.choices[value]
        return value

    def validate_regex(self, value, idx, column):
        if column.regex is None:
            return value
        if not column.regex.match(value):
            self.cell_error(u'regex', idx, column,
                    u'Expecting value matching "{}" but found "{}"', column.regex.pattern, value)
        return value

    def validate_unique(self, value, idx, column):
        if not column.unique:
            return value
        if not hasattr(self, u'_unique_cache'):
            self._unique_cache = defaultdict(dict)
        if value in self._unique_cache[column.label]:
            self.cell_error(u'unique', idx, column,
                    u'Expecting unique value but "{}" is in row {} as well',
                    value, self._unique_cache[column.label][value]+1)
        self._unique_cache[column.label][value] = idx
        return value

    def validate_unique_slug(self, value, idx, column):
        if not column.unique_slug:
            return value
        if not hasattr(self, u'_unique_slug_cache'):
            self._unique_slug_cache = defaultdict(dict)
        slug = slugify(value)
        if slug in self._unique_slug_cache[column]:
            other_idx, other_value = self._unique_slug_cache[column][slug]
            self.cell_error(u'unique_slug', idx, column,
                    u'Expecting value with unique slug but "{}" has the same slug as "{}" in row {}',
                    value, other_value, other_idx+1)
        self._unique_slug_cache[column][slug] = (idx, value)
        return value

    def validate_validators(self, value, idx, column):
        if column.validators is None:
            return value
        for validator in column.validators:
            try:
                validator(value)
            except ValidationError as e:
                self.cell_error((u'validator', validator.__name__), idx, column,
                        u'{}', u'; '.join(e.messages))
        return value

    def process_cell(self, idx, row, column):
        try:
            col_idx = self.column_map[column.label]
        except KeyError:
            self.cell_error(u'missing', idx, column, u'Missing column')

        try:
            value = row[col_idx].value
        except IndexError:
            value = None
        if value is None:
            value = column.default

        value = self.validate_type(value, idx, column)
        value = self.validate_min_value(value, idx, column)
        value = self.validate_max_value(value, idx, column)
        value = self.validate_min_length(value, idx, column)
        value = self.validate_max_length(value, idx, column)
        value = self.validate_nonempty(value, idx, column)
        value = self.validate_choices(value, idx, column)
        value = self.validate_regex(value, idx, column)
        value = self.validate_unique(value, idx, column)
        value = self.validate_unique_slug(value, idx, column)
        value = self.validate_validators(value, idx, column)
        return value

    def process_row(self, idx, row):
        res = {}
        errors = 0
        for column in self.columns.__dict__.values():
            try:
                res[column.label] = self.process_cell(idx, row, column)
            except RollingCommandError as e:
                errors += e.count
        if errors:
            raise RollingCommandError(errors)
        return res

    def confirm_changed(self, value, original, idx, column):
        if not column.confirm_changed:
            return value
        if original and value != getattr(original, column.field):
            inputed = self.importer.input_yes_no(
                    u'{} {} in row {} changed {}:\n\t{} -> {}',
                    u'Is it correct?',
                    self.model.__name__,
                    self.get_obj_repr(original),
                    idx+1,
                    column.field,
                    column.value_repr(getattr(original, column.field)),
                    column.value_repr(value),
                    default=u'Y')
            if inputed != u'Y':
                raise RollingCommandError
        return value

    def confirm_unchanged_if_changed(self, value, values, original, idx, column):
        if not column.confirm_unchanged_if_changed:
            return value
        if original and value == getattr(original, column.field):
            for other_column in column.confirm_unchanged_if_changed:
                other_column = self.columns.__dict__[other_column]
                other_value = values[other_column.label]
                if other_value != getattr(original, other_column.field):
                    inputed = self.importer.input_yes_no(
                            u'{} {} in row {} changed {}:\n\t{} -> {}\nBut not {}:\n\t{}',
                            u'Is it correct?',
                            self.model.__name__,
                            self.get_obj_repr(original),
                            idx+1,
                            other_column.field,
                            other_column.value_repr(getattr(original, other_column.field)),
                            other_column.value_repr(other_value),
                            column.field,
                            column.value_repr(value),
                            default=u'Y')
                    if inputed != u'Y':
                        raise RollingCommandError
                    break
        return value

    def process_value(self, values, original, idx, column):
        value = values[column.label]
        value = self.confirm_changed(value, original, idx, column)
        value = self.confirm_unchanged_if_changed(value, values, original, idx, column)
        return value

    def process_values(self, idx, values, original):
        errors = 0
        for column in self.columns.__dict__.values():
            try:
                values[column.label] = self.process_value(values, original, idx, column)
            except RollingCommandError as e:
                errors += e.count
        if errors:
            raise RollingCommandError(errors)
        return values

    def do_import(self):
        errors = 0

        try:
            self.validate_structure()
        except RollingCommandError as e:
            errors += e.count

        created, changed, unchanged, deleted = 0, 0, 0, 0
        originals = {o.pk: o for o in self.model.objects.all()}
        for idx, row in enumerate(self.ws.rows):
            if idx == 0 or all(c.value is None for c in row):
                continue
            try:
                values = self.process_row(idx, row)
                original = originals.pop(values[self.columns.pk.label], None)
                values = self.process_values(idx, values, original)
                fields = {c.field: values[c.label] for c in self.columns.__dict__.values() if c.field}
                fields = self.get_obj_fields(original, values, fields)
                assert fields[u'pk'] == values[self.columns.pk.label]

                # Save only if the instance is new or changed to prevent excessive change history
                if not original or any(fields[f] != getattr(original, f) for f in fields):
                    obj = self.model(**fields)
                    obj.save()
                    self.save_obj_rel(obj, values)
                    self.importer.write(2, u'{} {}: {}', u'Changed' if original else u'Created',
                            self.model.__name__, self.get_obj_repr(obj))
                    if original:
                        changed += 1
                    else:
                        created += 1
                else:
                    self.save_obj_rel(original, values)
                    unchanged += 1

            except RollingCommandError as e:
                errors += e.count

        # Delete omitted instances or add an error if delete is not permitted. Don't delete
        # anything if there were any import errors as we don't know which instances are missing for
        # real and which are missing because of parse errors.
        if errors:
            raise RollingCommandError(errors)
        for obj in originals.values():
            if self.delete_omitted:
                inputed = self.importer.input_yes_no(
                        u'{} {} was omitted.', u'Are you sure, you want to delete it?',
                        self.model.__name__, self.get_obj_repr(obj), default=u'Y')
                if inputed == u'Y':
                    obj.delete()
                    deleted += 1
                else:
                    errors += 1
            else:
                self.error(u'omitted', u'Omitted {}: {}', self.model.__name__, self.get_obj_repr(obj))
                errors += 1

        if errors:
            raise RollingCommandError(errors)

        self.importer.write(1, u'Imported model {}: {} created, {} changed, {} unchanged and {} deleted',
                self.model.__name__, created, changed, unchanged, deleted)

    def get_obj_fields(self, original, values, fields):
        return fields

    def save_obj_rel(self, obj, values):
        pass

    def get_obj_repr(self, obj):
        return u'ID={}'.format(obj.pk)

class Book(object):
    sheets = None

    def __init__(self, importer):
        self.importer = importer
        self.wb = None
        self.actual_sheets = None

    def reset_model(self, model):
        count = model.objects.count()
        model.objects.all().delete()
        self.importer.write(1, u'Reset model {}: {} deleted', model.__name__, count)

    def validate_structure(self):
        errors = 0

        expected_sheets = set(s.label for s in self.sheets)
        found_sheets = {n for n in self.wb.get_sheet_names() if not n.startswith(u'#')}
        missing_sheets = expected_sheets - found_sheets
        superfluous_sheets = found_sheets - expected_sheets
        self.actual_sheets = expected_sheets & found_sheets
        for sheet in missing_sheets:
            self.importer.error(None, u'The file does not contain required sheet: {}', sheet)
            errors += 1
        for sheet in superfluous_sheets:
            self.importer.error(None, u'The file contains unexpected sheet: {}', sheet)
            errors += 1

        if errors:
            raise RollingCommandError(errors)

    def do_import(self, filename):
        errors = 0

        try:
            self.wb = load_workbook(filename, read_only=True)
        except Exception as e:
            raise CommandError(u'Could not read input file: {}'.format(e))

        try:
            self.validate_structure()
        except RollingCommandError as e:
            errors += e.count

        for sheet in self.sheets:
            if sheet.label not in self.actual_sheets:
                continue
            try:
                sheet(self).do_import()
            except RollingCommandError as e:
                errors += e.count

        if errors:
            raise RollingCommandError(errors)

class Importer(object):

    def __init__(self, book, options, stdout):
        self.reset = options[u'reset']
        self.dry_run = options[u'dry_run']
        self.assume = options[u'assume']
        self.verbosity = int(options[u'verbosity'])
        self.stdout = stdout
        self.color_style = color_style()
        self.book = book

    def write(self, verbosity, msg, *args, **kwargs):
        if self.verbosity >= verbosity:
            self.stdout.write(msg.format(*args, **kwargs))

    def error(self, code, msg, *args, **kwargs):
        if not hasattr(self, u'_error_cache'):
            self._error_cache = defaultdict(int)

        msg = self.color_style.NOTICE(u'Error: ' + msg.format(*args, **kwargs))

        if self.verbosity == 1:
            if code:
                self._error_cache[code] += 1
                if self._error_cache[code] < 3:
                    self.stdout.write(msg)
                elif self._error_cache[code] == 3:
                    self.stdout.write(msg + u' (skipping further similar errors)')
            else:
                self.stdout.write(msg)
        elif self.verbosity >= 2:
            self.stdout.write(msg)

    def input_yes_no(self, text, prompt, *args, **kwargs):
        default = kwargs.pop(u'default', u'')
        while True:
            self.stdout.write(self.color_style.WARNING(
                    u'Warning: {}'.format(text.format(*args, **kwargs))))
            self.stdout.write(self.color_style.ERROR(
                    u'{} Yes/No/Abort [{}]: '.format(prompt, default)), ending=u'')

            if self.assume == u'yes':
                inputed = u'Yes'
                self.stdout.write(inputed)
            elif self.assume == u'no':
                inputed = u'No'
                self.stdout.write(inputed)
            elif self.assume == u'default':
                inputed = default
            else:
                inputed = raw_input() or default

            if not inputed:
                error = u'The value is required.'
            elif inputed.upper() in [u'A', u'ABORT']:
                raise CommandError(u'Aborted')
            elif inputed.upper() not in [u'Y', u'YES', u'N', u'NO']:
                error = u'Enter Yes, No or Abort.'
            else:
                return inputed.upper()[0]

            if self.assume:
                raise CommandError(error)
            self.stdout.write(self.color_style.ERROR(u'Error: {}'.format(error)))

    @transaction.atomic
    def do_import(self, filename):
        if self.dry_run:
            self.write(0, u'Importing: {} (dry run)', filename)
        else:
            self.write(0, u'Importing: {}', filename)

        self.book(self).do_import(filename)

        if self.dry_run:
            self.write(0, u'Rolled back (dry run)')
            raise RollbackDryRun
        else:
            self.write(0, u'Done.')


class ObligeeTagSheet(Sheet):
    label = u'Tagy'
    model = ObligeeTag
    delete_omitted = True

    columns = Columns( # {{{
            pk=Column(u'ID', field=u'pk',
                typ=Integral, unique=True, min_value=1,
                ),
            key=Column(u'Kod', field=u'key',
                typ=basestring, unique=True, max_length=255, regex=tag_regex,
                confirm_changed=True,
                ),
            name=Column(u'Nazov', field=u'name',
                typ=basestring, unique_slug=True, nonempty=True, max_length=255,
                ),
            ) # }}}

    def get_obj_repr(self, obj):
        return u'ID={} "{}"'.format(obj.pk, obj.key)

class ObligeeGroupSheet(Sheet):
    label = u'Hierarchia'
    model = ObligeeGroup
    delete_omitted = True

    columns = Columns( # {{{
            pk=Column(u'ID', field=u'pk',
                typ=Integral, unique=True, min_value=1,
                ),
            key=Column(u'Kod', field=u'key',
                typ=basestring, unique=True, max_length=255, regex=group_regex,
                confirm_changed=True,
                ),
            name=Column(u'Nazov v hierarchii', field=u'name',
                typ=basestring, unique_slug=True, nonempty=True, max_length=255,
                ),
            description=Column(u'Popis', field=u'description',
                typ=basestring, default=u'',
                ),
            ) # }}}

    def get_obj_repr(self, obj):
        return u'ID={} "{}"'.format(obj.pk, obj.key)

class ObligeeSheet(Sheet):
    label = u'Obligees'
    model = Obligee
    delete_omitted = False

    columns = Columns( # {{{
            pk=Column(u'ID', field=u'pk',
                typ=Integral, unique=True, min_value=1,
                ),
            official_name=Column(u'Oficialny nazov', field=u'official_name',
                typ=basestring, nonempty=True,
                confirm_changed=True,
                ),
            name=Column(u'Rozlisovaci nazov nominativ', field=u'name',
                typ=basestring, unique_slug=True, nonempty=True,
                confirm_unchanged_if_changed=u'official_name',
                ),
            name_genitive=Column(u'Rozlisovaci nazov genitiv', field=u'name_genitive',
                typ=basestring, nonempty=True,
                confirm_unchanged_if_changed=u'name',
                ),
            name_dative=Column(u'Rozlisovaci nazov dativ', field=u'name_dative',
                typ=basestring, nonempty=True,
                confirm_unchanged_if_changed=u'name',
                ),
            name_accusative=Column(u'Rozlisovaci nazov akuzativ', field=u'name_accusative',
                typ=basestring, nonempty=True,
                confirm_unchanged_if_changed=u'name',
                ),
            name_locative=Column(u'Rozlisovaci nazov lokal', field=u'name_locative',
                typ=basestring, nonempty=True,
                confirm_unchanged_if_changed=u'name',
                ),
            name_instrumental=Column(u'Rozlisovaci nazov instrumental', field=u'name_instrumental',
                typ=basestring, nonempty=True,
                confirm_unchanged_if_changed=u'name',
                ),
            gender=Column(u'Rod', field=u'gender',
                typ=basestring, choices={
                    u'muzsky': Obligee.GENDERS.MASCULINE,
                    u'zensky': Obligee.GENDERS.FEMININE,
                    u'stredny': Obligee.GENDERS.NEUTER,
                    u'pomnozny': Obligee.GENDERS.PLURALE,
                    },
                ),
            ico=Column(u'ICO', field=u'ico',
                typ=basestring, default=u'',
                ),
            street=Column(u'Adresa: Ulica s cislom', field=u'street',
                typ=basestring, nonempty=True,
                ),
            city=Column(u'Adresa: Obec', field=u'city',
                typ=basestring, nonempty=True,
                ),
            zip=Column(u'Adresa: PSC', field=u'zip',
                typ=basestring, regex=zip_regex,
                ),
            emails=Column(u'Adresa: Email', field=u'emails',
                typ=basestring, default=u'', validators=validate_comma_separated_emails,
                # Override with dummy emails for local and dev server modes
                ),
            official_description=Column(u'Oficialny popis', field=u'official_description',
                typ=basestring, default=u'',
                ),
            simple_description=Column(u'Zrozumitelny popis', field=u'simple_description',
                typ=basestring, default=u'',
                ),
            status=Column(u'Stav', field=u'status',
                typ=basestring, choices={
                    u'aktivny': Obligee.STATUSES.PENDING,
                    u'neaktivny': Obligee.STATUSES.DISSOLVED,
                    },
                confirm_changed=True,
                value_repr=(lambda v: Obligee.STATUSES._inverse[v]),
                ),
            type=Column(u'Typ', field=u'type',
                typ=basestring, choices={
                    u'odsek 1': Obligee.TYPES.SECTION_1,
                    u'odsek 2': Obligee.TYPES.SECTION_2,
                    u'odsek 3': Obligee.TYPES.SECTION_3,
                    u'odsek 4': Obligee.TYPES.SECTION_4,
                    },
                ),
            group=Column(u'Hierarchia', # FIXME: m2m foreign key
                typ=basestring, regex=groups_regex_1,
                ),
            tags=Column(u'Tagy', # FIXME: m2m foreign key
                typ=basestring, default=u'', regex=tags_regex_0,
                ),
            latitude=Column(u'Lat', field=u'latitude',
                typ=Real, min_value=-90.0, max_value=90.0,
                ),
            longitude=Column(u'Lon', field=u'longitude',
                typ=Real, min_value=-180.0, max_value=180.0,
                ),
            iczsj=Column(u'ICZSJ', # FIXME: foreign key
                typ=Integral, min_value=1,
                ),
            notes=Column(u'Poznamka', field=u'notes',
                typ=basestring, default=u'',
                ),
            ) # }}}

    def get_obj_fields(self, original, values, fields):

        # Dummy emails for local and dev server modes
        if hasattr(settings, u'OBLIGEE_DUMMY_MAIL'):
            fields[u'emails'] = Obligee.dummy_email(fields[u'name'], settings.OBLIGEE_DUMMY_MAIL)

        return fields

    def get_obj_repr(self, obj):
        return u'ID={} "{}"'.format(obj.pk, obj.name)

class ObligeeAliasSheet(Sheet):
    label = u'Aliasy'
    model = None # FIXME
    delete_omitted = True

    columns = Columns( # {{{
            pk=Column(u'ID',
                typ=Integral, unique=True, min_value=1,
                ),
            obligee_pk=Column(u'ID institucie', # FIXME: foreign key
                typ=Integral, min_value=1,
                ),
            obligee_name=Column(u'Rozlisovaci nazov institucie', # FIXME: overit vzhladom na ID institucie
                typ=basestring, nonempty=True,
                ),
            alias=Column(u'Alternativny nazov',
                typ=basestring, unique_slug=True, nonempty=True,
                ),
            description=Column(u'Vysvetlenie',
                typ=basestring, default=u'',
                ),
            notes=Column(u'Poznamka',
                typ=basestring, default=u'',
                ),
            ) # }}}

    def get_obj_fields(self, original, values, fields):
        raise NotImplementedError

class ObligeeBook(Book):
    #sheets = [ObligeeTagSheet, ObligeeGroupSheet, ObligeeSheet, ObligeeAliasSheet]
    sheets = [ObligeeTagSheet, ObligeeGroupSheet, ObligeeSheet]

    def do_import(self, filename):

        # Reset obligees if requested
        if self.importer.reset:
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

        super(ObligeeBook, self).do_import(filename)


class Command(BaseCommand):
    help = u'Loads .xlsx file with obligees'
    args = u'file'
    option_list = BaseCommand.option_list + (
        make_option(u'--dry-run', action=u'store_true', default=False,
            help=squeeze(u"""
                Just show if the file would be imported correctly. Rollback all changes at the end.
                """)),
        make_option(u'--reset', action=u'store_true', default=False,
            help=squeeze(u"""
                Discard current obligees before imporing the file.
                """)),
        make_option(u'--assume', choices=[u'yes', u'no', u'default'],
            help=squeeze(u"""
                Assume yes/no/default answer to all yes/no questions.
                """)),
        )

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError(u'Expecting exactly one argument')

        try:
            importer = Importer(ObligeeBook, options, self.stdout)
            importer.do_import(args[0])
        except KeyboardInterrupt:
            self.stdout.write(u'\n')
            raise CommandError(u'Aborted')
        except RollbackDryRun:
            pass
