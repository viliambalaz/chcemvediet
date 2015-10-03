# vim: expandtab
# -*- coding: utf-8 -*-
import re
from numbers import Number, Real, Integral
from collections import Mapping, defaultdict
from optparse import make_option
from openpyxl import load_workbook

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import color_style
from django.db import transaction
from django.conf import settings

from poleno.utils.forms import validate_comma_separated_emails
from poleno.utils.misc import squeeze, slugify, ensure_tuple
from chcemvediet.apps.obligees.models import ObligeeTag, ObligeeGroup, Obligee, HistoricalObligee, ObligeeAlias
from chcemvediet.apps.inforequests.models import Inforequest


class RollingCommandError(CommandError):
    def __init__(self, count=1):
        self.count = count
        super(CommandError, self).__init__(
                u'Detected {} errors; Rolled back'.format(count))

class RollbackDryRun(Exception):
    pass

class CellError(Exception):
    def __init__(self, code, msg, *args, **kwargs):
        self.code = code
        super(CellError, self).__init__(msg.format(*args, **kwargs))


class Column(object):
    value_type = None

    def __init__(self, label, field=None, default=None, null=False, blank=False, choices=None,
            unique=False, validators=None, coercers=None, post_coerce_validators=None,
            confirm_changed=None, confirm_unchanged_if_changed=None):
        self.label = label
        self.field = field
        self.default = default # pre coerce
        self.null = null # pre coerce
        self.blank = blank # post coerce
        self.choices = choices # pre coerce + coerce if it is mapping
        self.unique = unique # post coerce
        self.validators = validators # pre coerce
        self.coercers = coercers # coerce
        self.post_coerce_validators = post_coerce_validators # post coerce
        self.confirm_changed = confirm_changed # post row
        self.confirm_unchanged_if_changed = confirm_unchanged_if_changed # post row

    def validate_type(self, value):
        if self.value_type is None:
            return
        if self.null and value is None:
            return
        if not isinstance(value, self.value_type):
            raise CellError(u'type', u'Expecting {} but found {}',
                    self.value_type.__name__, value.__class__.__name__)

    def validate_blank(self, value):
        if self.blank:
            return
        if not value:
            raise CellError(u'blank', u'Expecting nonempty value but found {}',
                    self.value_repr(value))

    def validate_choices(self, value):
        if self.choices is None:
            return
        if value not in self.choices:
            raise CellError(u'choices', u'Expecting one of {} but found {}',
                    u', '.join(self.value_repr(c) for c in self.choices),
                    self.value_repr(value))

    def validate_unique(self, sheet, row, value):
        if not self.unique:
            return
        if not hasattr(sheet, u'_validate_unique_cache'):
            sheet._validate_unique_cache = defaultdict(dict)
        if value in sheet._validate_unique_cache[self]:
            raise CellError(u'unique', u'Expecting unique value but {} is in row {} as well',
                    self.value_repr(value), sheet._validate_unique_cache[self][value])
        sheet._validate_unique_cache[self][value] = row

    def validate_pre_coerce_validators(self, value):
        if self.validators is None:
            return
        for validator in ensure_tuple(self.validators):
            try:
                validator(value)
            except ValidationError as e:
                raise CellError((u'validator', validator.__name__), u'{}', u'; '.join(e.messages))

    def validate_post_coerce_validators(self, value):
        if self.post_coerce_validators is None:
            return
        for validator in ensure_tuple(self.post_coerce_validators):
            try:
                validator(value)
            except ValidationError as e:
                raise CellError((u'validator', validator.__name__), u'{}', u'; '.join(e.messages))

    def apply_choices(self, value):
        if not isinstance(self.choices, Mapping):
            return value
        return self.choices[value]

    def apply_coercers(self, value):
        if self.coercers is None:
            return value
        for coercer in ensure_tuple(self.coercers):
            value = coercer(value)
        return value

    def do_pre_coerce_validation(self, sheet, row, value):
        self.validate_type(value)
        self.validate_choices(value)
        self.validate_pre_coerce_validators(value)

    def do_coerce(self, sheet, row, value):
        value = self.apply_choices(value)
        value = self.apply_coercers(value)
        return value

    def do_post_ceorce_validation(self, sheet, row, value):
        self.validate_blank(value)
        self.validate_unique(sheet, row, value)
        self.validate_post_coerce_validators(value)

    def do_import(self, sheet, row, value):
        self.do_pre_coerce_validation(sheet, row, value)
        value = self.do_coerce(sheet, row, value)
        self.do_post_ceorce_validation(sheet, row, value)
        return value

    def value_repr(self, value):
        if isinstance(value, basestring):
            return u'"{}"'.format(value)
        else:
            return unicode(repr(value), u'utf-8')

    def coerced_repr(self, value):
        return self.value_repr(value)

class TextColumn(Column):
    value_type = basestring

    def __init__(self, label, min_length=None, max_length=None, regex=None, unique_slug=False,
            **kwargs):
        kwargs.setdefault(u'default', u'')
        super(TextColumn, self).__init__(label, null=False, **kwargs)
        self.min_length = min_length # pre coerce
        self.max_length = max_length # pre coerce
        self.regex = regex # pre coerce
        self.unique_slug = unique_slug # pre coerce

    def validate_min_length(self, value):
        if self.min_length is None:
            return
        if len(value) < self.min_length:
            raise CellError(u'min_length',
                    u'Expecting value not shorter than {} but found "{}" with length {}',
                    self.min_length, value, len(value))

    def validate_max_length(self, value):
        if self.max_length is None:
            return
        if len(value) > self.max_length:
            raise CellError(u'max_length',
                    u'Expecting value not longer than {} but found {} with length {}',
                    self.max_length, self.value_repr(value), len(value))

    def validate_regex(self, value):
        if self.regex is None:
            return
        if not self.regex.match(value):
            raise CellError(u'regex',
                    u'Expecting value matching "{}" but found {}',
                    self.regex.pattern, self.value_repr(value))

    def validate_unique_slug(self, sheet, row, value):
        if not self.unique_slug:
            return
        if not hasattr(sheet, u'_validate_unique_slug_cache'):
            sheet._validate_unique_slug_cache = defaultdict(dict)
        slug = slugify(value)
        if slug in sheet._validate_unique_slug_cache[self]:
            other_row, other_value = sheet._validate_unique_slug_cache[self][slug]
            raise CellError(u'unique_slug',
                    u'Expecting value with unique slug but {} has the same slug as {} in row {}',
                    self.value_repr(value), self.value_repr(other_value), other_row)
        sheet._validate_unique_slug_cache[self][slug] = (row, value)
        return value

    def do_pre_coerce_validation(self, sheet, row, value):
        super(TextColumn, self).do_pre_coerce_validation(sheet, row, value)
        self.validate_min_length(value)
        self.validate_max_length(value)
        self.validate_regex(value)
        self.validate_unique_slug(sheet, row, value)

class NumericColumn(Column):
    value_type = Number

    def __init__(self, label, min_value=None, max_value=None, **kwargs):
        super(NumericColumn, self).__init__(label, **kwargs)
        self.min_value = min_value # pre coerce
        self.max_value = max_value # pre coerce

    def validate_min_value(self, value):
        if self.min_value is None:
            return
        if value < self.min_value:
            raise CellError(u'min_value',
                    u'Expecting value not smaller than {} but found {}',
                    self.min_value, self.value_repr(value))

    def validate_max_value(self, value):
        if self.max_value is None:
            return
        if value > self.max_value:
            raise CellError(u'max_value',
                    u'Expecting value not bigger than {} but found {}',
                    self.max_value, self.value_repr(value))

    def do_pre_coerce_validation(self, sheet, row, value):
        super(NumericColumn, self).do_pre_coerce_validation(sheet, row, value)
        self.validate_min_value(value)
        self.validate_max_value(value)

class FloatColumn(NumericColumn):
    value_type = Real

class IntegerColumn(NumericColumn):
    value_type = Integral

class FieldChoicesColumn(Column):
    value_type = None

    def __init__(self, label, field_choices, **kwargs):
        kwargs.setdefault(u'choices', {n: v for v, n in field_choices._inverse.items()})
        super(FieldChoicesColumn, self).__init__(label, **kwargs)
        self.field_choices = field_choices

    def coerced_repr(self, value):
        return self.field_choices._inverse[value]

class ForeignKeyColumn(Column):
    value_type = None

    def __init__(self, label, to_model, to_field=u'pk', **kwargs):
        super(ForeignKeyColumn, self).__init__(label, choices=None, **kwargs)
        self.to_model = to_model
        self.to_field = to_field

    def apply_relation(self, sheet, value):
        try:
            obj = self.to_model.objects.get(**{self.to_field: value})
        except self.to_model.DoesNotExist:
            raise CellError(u'relation_not_found', u'There is no {} with {}="{}"',
                    self.to_model.__name__, self.to_field, value)
        except self.to_model.MultipleObjectsReturned:
            raise CellError(u'relation_found_more', u'There are multiple {} with {}="{}"',
                    self.to_model.__name__, self.to_field, value)
        if obj in sheet.book.marked_for_deletion:
            raise CellError(u'deleted', u'{} with {}="{}" was deleted',
                    self.to_model.__name__, self.to_field, value)
        return obj

    def do_coerce(self, sheet, row, value):
        value = super(ForeignKeyColumn, self).do_coerce(sheet, row, value)
        value = self.apply_relation(sheet, value)
        return value

class ManyToManyColumn(Column):
    value_type = basestring

    def __init__(self, label, to_model, to_field=u'pk', **kwargs):
        super(ManyToManyColumn, self).__init__(label, default=u'', null=False, choices=None,
                unique=False, **kwargs)
        self.to_model = to_model
        self.to_field = to_field

    def apply_relation(self, sheet, value):
        res = []
        for key in value.split():
            try:
                obj = self.to_model.objects.get(**{self.to_field: key})
            except self.to_model.DoesNotExist:
                raise CellError(u'relation_not_found', u'There is no {} with {}="{}"',
                        self.to_model.__name__, self.to_field, key)
            except self.to_model.MultipleObjectsReturned:
                raise CellError(u'relation_found_more', u'There are multiple {} with {}="{}"',
                        self.to_model.__name__, self.to_field, key)
            if obj in sheet.book.marked_for_deletion:
                raise CellError(u'deleted', u'{} with {}="{}" was deleted',
                        self.to_model.__name__, self.to_field, key)
            res.append(obj)
        return res

    def do_coerce(self, sheet, row, value):
        value = super(ManyToManyColumn, self).do_coerce(sheet, row, value)
        value = self.apply_relation(sheet, value)
        return value


class Columns(object):
    def __init__(self, **kwargs):
        vars(self).update(kwargs)

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
        self.m2m = {f.name for f, _ in self.model._meta.get_m2m_with_model()}

    def obj_field(self, obj, field):
        if field in self.m2m:
            return list(getattr(obj, field).all())
        else:
            try:
                return getattr(obj, field)
            except ObjectDoesNotExist:
                return None

    def obj_field_eq(self, obj, field, value):
        if field in self.m2m:
            return set(getattr(obj, field).all()) == set(value)
        else:
            try:
                return getattr(obj, field) == value
            except ObjectDoesNotExist:
                return False

    def error(self, code, msg, *args, **kwargs):
        if code:
            code = (self.label, code)
        self.importer.error(code, msg, *args, **kwargs)

    def validate_structure(self):
        errors = 0

        self.column_map = {}
        row = next(self.ws.rows, [])
        for col_idx, column in enumerate(row):
            if column.value is not None and not column.value.startswith(u'#'):
                self.column_map[column.value] = col_idx

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

    def process_cell(self, row_idx, row, column):
        try:
            col_idx = self.column_map[column.label]
        except KeyError:
            self.error((column.label, u'missing'),
                    u'Invalid value in row {} of "{}.{}": Missing column',
                    row_idx+1, self.label, column.label)
            raise RollingCommandError

        try:
            value = row[col_idx].value
        except IndexError:
            value = None
        if value is None:
            value = column.default

        try:
            return column.do_import(self, row_idx+1, value)
        except CellError as e:
            self.error((column.label, e.code), u'Invalid value in row {} of "{}.{}": {}',
                    row_idx+1, self.label, column.label, e)
            raise RollingCommandError

    def process_row(self, row_idx, row):
        res = {}
        errors = 0
        for column in self.columns.__dict__.values():
            try:
                res[column.label] = self.process_cell(row_idx, row, column)
            except RollingCommandError as e:
                errors += e.count
        if errors:
            raise RollingCommandError(errors)
        return res

    def confirm_changed(self, value, original, row_idx, column):
        if not column.confirm_changed:
            return
        if original and not self.obj_field_eq(original, column.field, value):
            inputed = self.importer.input_yes_no(
                    u'{} in row {} changed {}:\n\t{} -> {}',
                    u'Is it correct?',
                    self.get_obj_repr(original),
                    row_idx+1,
                    column.field,
                    column.coerced_repr(self.obj_field(original, column.field)),
                    column.coerced_repr(value),
                    default=u'Y')
            if inputed != u'Y':
                raise RollingCommandError

    def confirm_unchanged_if_changed(self, value, values, original, row_idx, column):
        if not column.confirm_unchanged_if_changed:
            return
        if original and self.obj_field_eq(original, column.field, value):
            for other_column in ensure_tuple(column.confirm_unchanged_if_changed):
                other_column = self.columns.__dict__[other_column]
                other_value = values[other_column.label]
                if not self.obj_field_eq(original, other_column.field, other_value):
                    inputed = self.importer.input_yes_no(
                            u'{} in row {} changed {}:\n\t{} -> {}\nBut not {}:\n\t{}',
                            u'Is it correct?',
                            self.get_obj_repr(original),
                            row_idx+1,
                            other_column.field,
                            other_column.coerced_repr(self.obj_field(original, other_column.field)),
                            other_column.coerced_repr(other_value),
                            column.field,
                            column.coerced_repr(value),
                            default=u'Y')
                    if inputed != u'Y':
                        raise RollingCommandError
                    return

    def process_value(self, value, values, original, row_idx, column):
        self.confirm_changed(value, original, row_idx, column)
        self.confirm_unchanged_if_changed(value, values, original, row_idx, column)
        return value

    def process_values(self, row_idx, values, original):
        errors = 0
        res = {}
        for column in self.columns.__dict__.values():
            try:
                value = values[column.label]
                res[column.label] = self.process_value(value, values, original, row_idx, column)
            except RollingCommandError as e:
                errors += e.count
        if errors:
            raise RollingCommandError(errors)
        return res

    def do_import(self):
        errors = 0

        try:
            self.validate_structure()
        except RollingCommandError as e:
            errors += e.count

        created, changed, unchanged, deleted = 0, 0, 0, 0
        originals = {o.pk: o for o in self.model.objects.all()}
        for row_idx, row in enumerate(self.ws.rows):
            if row_idx == 0 or all(c.value is None for c in row):
                continue
            try:
                values = self.process_row(row_idx, row)
                original = originals.pop(values[self.columns.pk.label], None)
                values = self.process_values(row_idx, values, original)
                fields = {c.field: values[c.label] for c in self.columns.__dict__.values() if c.field}
                fields = self.get_obj_fields(original, values, fields, row_idx)
                assert fields[u'pk'] == values[self.columns.pk.label]

                # Save only if the instance is new or changed to prevent excessive change history.
                # Many to many relations may only be saved after the instance is created.
                obj = original or self.model()
                was_changed = False
                for field, value in fields.items():
                    if field not in self.m2m and not self.obj_field_eq(obj, field, value):
                        setattr(obj, field, value)
                        was_changed = True
                if was_changed:
                    obj.save()
                for field, value in fields.items():
                    if field in self.m2m and not self.obj_field_eq(obj, field, value):
                        setattr(obj, field, value)
                        was_changed = True

                if was_changed and original:
                    self.importer.write(2, u'Changed {}', self.get_obj_repr(obj))
                    changed += 1
                elif was_changed:
                    self.importer.write(2, u'Created {}', self.get_obj_repr(obj))
                    created += 1
                else:
                    unchanged += 1

            except RollingCommandError as e:
                errors += e.count

        # Mark omitted instances for deletion or add an error if delete is not permitted. Don't
        # delete anything if there were any import errors as we don't know which instances are
        # missing for real and which are missing because of parse errors. The instances will be
        # deleted only after all sheets are imported to prevent unintentional cascades.
        if errors:
            raise RollingCommandError(errors)
        for obj in originals.values():
            if self.delete_omitted:
                inputed = self.importer.input_yes_no(
                        u'{} was omitted.', u'Are you sure, you want to delete it?',
                        self.get_obj_repr(obj), default=u'Y')
                if inputed == u'Y':
                    self.book.marked_for_deletion.add(obj)
                    deleted += 1
                else:
                    errors += 1
            else:
                self.error(u'omitted', u'Omitted {}', self.get_obj_repr(obj))
                errors += 1

        if errors:
            raise RollingCommandError(errors)

        self.importer.write(1, u'Imported model {}: {} created, {} changed, {} unchanged and {} deleted',
                self.model.__name__, created, changed, unchanged, deleted)

    def get_obj_fields(self, original, values, fields, row_idx):
        return fields

    def get_obj_repr(self, obj):
        return unicode(repr(obj), u'utf-8')

class Book(object):
    sheets = None

    def __init__(self, importer):
        self.importer = importer
        self.wb = None
        self.actual_sheets = None
        self.marked_for_deletion = None

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

        self.marked_for_deletion = set()
        for sheet in self.sheets:
            if sheet.label not in self.actual_sheets:
                continue
            try:
                sheet(self).do_import()
            except RollingCommandError as e:
                errors += e.count
        for obj in self.marked_for_deletion:
            obj.delete()

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

            if self.assume:
                if self.assume == u'yes':
                    inputed = u'Yes'
                elif self.assume == u'no':
                    inputed = u'No'
                else:
                    inputed = default
                self.stdout.write(inputed)
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

    columns = Columns(
            # {{{
            pk=IntegerColumn(u'ID', field=u'pk',
                unique=True, min_value=1,
                ),
            key=TextColumn(u'Kod', field=u'key',
                unique=True, max_length=255, regex=re.compile(r'^[\w-]+$'),
                confirm_changed=True,
                ),
            name=TextColumn(u'Nazov', field=u'name',
                unique_slug=True, max_length=255,
                ),
            # }}}
            )

class ObligeeGroupSheet(Sheet):
    label = u'Hierarchia'
    model = ObligeeGroup
    delete_omitted = True

    columns = Columns(
            # {{{
            pk=IntegerColumn(u'ID', field=u'pk',
                unique=True, min_value=1,
                ),
            key=TextColumn(u'Kod', field=u'key',
                unique=True, max_length=255, regex=re.compile(r'^[\w-]+(/[\w-]+)*$'),
                confirm_changed=True,
                ),
            name=TextColumn(u'Nazov v hierarchii', field=u'name',
                unique_slug=True, max_length=255,
                ),
            description=TextColumn(u'Popis', field=u'description',
                blank=True,
                ),
            # }}}
            )

class ObligeeSheet(Sheet):
    label = u'Obligees'
    model = Obligee
    delete_omitted = False

    columns = Columns(
            # {{{
            pk=IntegerColumn(u'ID', field=u'pk',
                unique=True, min_value=1,
                ),
            official_name=TextColumn(u'Oficialny nazov', field=u'official_name',
                max_length=255,
                confirm_changed=True,
                ),
            name=TextColumn(u'Rozlisovaci nazov nominativ', field=u'name',
                unique_slug=True, max_length=255,
                confirm_unchanged_if_changed=u'official_name',
                ),
            name_genitive=TextColumn(u'Rozlisovaci nazov genitiv', field=u'name_genitive',
                max_length=255,
                confirm_unchanged_if_changed=u'name',
                ),
            name_dative=TextColumn(u'Rozlisovaci nazov dativ', field=u'name_dative',
                max_length=255,
                confirm_unchanged_if_changed=u'name',
                ),
            name_accusative=TextColumn(u'Rozlisovaci nazov akuzativ', field=u'name_accusative',
                max_length=255,
                confirm_unchanged_if_changed=u'name',
                ),
            name_locative=TextColumn(u'Rozlisovaci nazov lokal', field=u'name_locative',
                max_length=255,
                confirm_unchanged_if_changed=u'name',
                ),
            name_instrumental=TextColumn(u'Rozlisovaci nazov instrumental', field=u'name_instrumental',
                max_length=255,
                confirm_unchanged_if_changed=u'name',
                ),
            gender=FieldChoicesColumn(u'Rod', Obligee.GENDERS, field=u'gender',
                choices={
                    u'muzsky': Obligee.GENDERS.MASCULINE,
                    u'zensky': Obligee.GENDERS.FEMININE,
                    u'stredny': Obligee.GENDERS.NEUTER,
                    u'pomnozny': Obligee.GENDERS.PLURALE,
                    },
                ),
            ico=TextColumn(u'ICO', field=u'ico',
                blank=True, max_length=32,
                ),
            street=TextColumn(u'Adresa: Ulica s cislom', field=u'street',
                max_length=255,
                ),
            city=TextColumn(u'Adresa: Obec', field=u'city',
                max_length=255,
                ),
            zip=TextColumn(u'Adresa: PSC', field=u'zip',
                max_length=10, regex=re.compile(r'^\d\d\d \d\d$'),
                ),
            iczsj=IntegerColumn(u'ICZSJ', # FIXME: foreign key
                min_value=1,
                ),
            emails=TextColumn(u'Adresa: Email', field=u'emails',
                blank=True, max_length=1024, validators=validate_comma_separated_emails,
                # Overridden with dummy emails for local and dev server modes; See get_obj_fields()
                ),
            latitude=FloatColumn(u'Lat', field=u'latitude',
                min_value=-90.0, max_value=90.0,
                ),
            longitude=FloatColumn(u'Lon', field=u'longitude',
                min_value=-180.0, max_value=180.0,
                ),
            tags=ManyToManyColumn(u'Tagy', ObligeeTag, field=u'tags',
                to_field=u'key', blank=True,
                ),
            groups=ManyToManyColumn(u'Hierarchia', ObligeeGroup, field=u'groups',
                to_field=u'key',
                ),
            type=FieldChoicesColumn(u'Typ', Obligee.TYPES, field=u'type',
                choices={
                    u'odsek 1': Obligee.TYPES.SECTION_1,
                    u'odsek 2': Obligee.TYPES.SECTION_2,
                    u'odsek 3': Obligee.TYPES.SECTION_3,
                    u'odsek 4': Obligee.TYPES.SECTION_4,
                    },
                ),
            official_description=TextColumn(u'Oficialny popis', field=u'official_description',
                blank=True,
                ),
            simple_description=TextColumn(u'Zrozumitelny popis', field=u'simple_description',
                blank=True,
                ),
            status=FieldChoicesColumn(u'Stav', Obligee.STATUSES, field=u'status',
                choices={
                    u'aktivny': Obligee.STATUSES.PENDING,
                    u'neaktivny': Obligee.STATUSES.DISSOLVED,
                    },
                confirm_changed=True,
                ),
            notes=TextColumn(u'Poznamka', field=u'notes',
                blank=True,
                ),
            # }}}
            )

    def get_obj_fields(self, original, values, fields, row_idx):

        # Dummy emails for local and dev server modes
        if hasattr(settings, u'OBLIGEE_DUMMY_MAIL'):
            fields[u'emails'] = Obligee.dummy_email(fields[u'name'], settings.OBLIGEE_DUMMY_MAIL)

        return fields

class ObligeeAliasSheet(Sheet):
    label = u'Aliasy'
    model = ObligeeAlias
    delete_omitted = True

    columns = Columns(
            # {{{
            pk=IntegerColumn(u'ID', field=u'pk',
                unique=True, min_value=1,
                ),
            obligee=ForeignKeyColumn(u'ID institucie', Obligee, field=u'obligee',
                confirm_changed=True,
                ),
            obligee_name=TextColumn(u'Rozlisovaci nazov institucie', # FIXME: overit vzhladom na ID institucie
                ),
            name=TextColumn(u'Alternativny nazov', field=u'name',
                unique_slug=True, max_length=255,
                ),
            description=TextColumn(u'Vysvetlenie', field=u'description',
                blank=True,
                ),
            notes=TextColumn(u'Poznamka', field=u'notes',
                blank=True,
                ),
            # }}}
            )

    def get_obj_fields(self, original, values, fields, row_idx):

        # Check that obligee_name is obligee.name
        column = self.columns.obligee_name
        if values[column.label] != fields[u'obligee'].name:
            self.error(u'obligee_name_mismatch',
                    u'Invalid value in row {} of "{}.{}": Expecting {} but found {}',
                    row_idx+1, self.label, column.label,
                    column.coerced_repr(fields[u'obligee'].name),
                    column.coerced_repr(values[column.label]))

        return fields

class ObligeeBook(Book):
    sheets = [ObligeeTagSheet, ObligeeGroupSheet, ObligeeSheet, ObligeeAliasSheet]

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
