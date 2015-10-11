# vim: expandtab
# -*- coding: utf-8 -*-
import re
from numbers import Number, Real, Integral
from collections import Mapping, defaultdict, OrderedDict
from optparse import make_option
from openpyxl import load_workbook

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import color_style
from django.db import transaction, DEFAULT_DB_ALIAS
from django.conf import settings
from django.contrib.admin.utils import NestedObjects
from django.utils.text import capfirst
from django.utils.encoding import force_text

from poleno.utils.forms import validate_comma_separated_emails
from poleno.utils.misc import squeeze, slugify, ensure_tuple, Bunch
from chcemvediet.apps.obligees.models import ObligeeTag, ObligeeGroup
from chcemvediet.apps.obligees.models import Obligee, HistoricalObligee, ObligeeAlias
from chcemvediet.apps.inforequests.models import Inforequest


def common_repr(value):
    if isinstance(value, basestring):
        return u'"{}"'.format(value)
    else:
        return unicode(repr(value), u'utf-8')


class RollingError(Exception):
    def __init__(self, count=1):
        self.count = count
        super(RollingError, self).__init__()

class CellError(Exception):
    def __init__(self, code, msg, *args, **kwargs):
        self.code = code
        super(CellError, self).__init__(msg.format(*args, **kwargs))

class RollbackDryRun(Exception):
    pass


class Columns(object):

    def __init__(self, **kwargs):
        for name, column in kwargs.items():
            column.name = name
            if column.field is not None:
                column.field.name = name
                column.field.column = column
        vars(self).update(kwargs)

class Column(object):
    value_type = None

    def __init__(self, label, default=None, null=False, blank=False, choices=None, unique=False,
            validators=None, coercers=None, post_coerce_validators=None, field=None):
        self.name = None
        self.label = label
        self.default = default # pre coerce
        self.null = null # pre coerce
        self.blank = blank # post coerce
        self.choices = choices # pre coerce + coerce if it is mapping
        self.unique = unique # post coerce
        self.validators = validators # pre coerce
        self.coercers = coercers # coerce
        self.post_coerce_validators = post_coerce_validators # post coerce
        self.field = field

    def validate_type(self, value):
        if self.value_type is None:
            return
        if self.null and value is None:
            return
        if not isinstance(value, self.value_type):
            raise CellError(u'type', u'Expecting {} but found {}',
                    self.value_type.__name__, value.__class__.__name__)

    def validate_choices(self, value):
        if self.choices is None:
            return
        if value not in self.choices:
            raise CellError(u'choices', u'Expecting one of {} but found {}',
                    u', '.join(self.value_repr(c) for c in self.choices),
                    self.value_repr(value))

    def validate_pre_coerce_validators(self, value):
        if self.validators is None:
            return
        for validator in ensure_tuple(self.validators):
            try:
                validator(value)
            except ValidationError as e:
                raise CellError((u'validator', validator.__name__), u'{}', u'; '.join(e.messages))

    def do_pre_coerce_validation(self, sheet, row_idx, value):
        self.validate_type(value)
        self.validate_choices(value)
        self.validate_pre_coerce_validators(value)

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

    def do_coerce(self, sheet, row_idx, value):
        value = self.apply_choices(value)
        value = self.apply_coercers(value)
        return value

    def validate_blank(self, value):
        if self.blank:
            return
        if not value:
            raise CellError(u'blank', u'Expecting nonempty value but found {}',
                    self.coerced_repr(value))

    def validate_unique(self, sheet, row_idx, value):
        if not self.unique:
            return
        if not hasattr(sheet, u'_validate_unique_cache'):
            sheet._validate_unique_cache = defaultdict(dict)
        if value in sheet._validate_unique_cache[self]:
            raise CellError(u'unique', u'Expecting unique value but {} is in row {} as well',
                    self.coerced_repr(value), sheet._validate_unique_cache[self][value])
        sheet._validate_unique_cache[self][value] = row_idx

    def validate_post_coerce_validators(self, value):
        if self.post_coerce_validators is None:
            return
        for validator in ensure_tuple(self.post_coerce_validators):
            try:
                validator(value)
            except ValidationError as e:
                raise CellError((u'validator', validator.__name__), u'{}', u'; '.join(e.messages))

    def do_post_ceorce_validation(self, sheet, row_idx, value):
        self.validate_blank(value)
        self.validate_unique(sheet, row_idx, value)
        self.validate_post_coerce_validators(value)

    def do_import(self, sheet, row_idx, value):
        self.do_pre_coerce_validation(sheet, row_idx, value)
        value = self.do_coerce(sheet, row_idx, value)
        self.do_post_ceorce_validation(sheet, row_idx, value)
        return value

    def value_repr(self, value):
        return common_repr(value)

    def coerced_repr(self, value):
        return common_repr(value)

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

    def validate_unique_slug(self, sheet, row_idx, value):
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
        sheet._validate_unique_slug_cache[self][slug] = (row_idx, value)
        return value

    def do_pre_coerce_validation(self, sheet, row_idx, value):
        super(TextColumn, self).do_pre_coerce_validation(sheet, row_idx, value)
        self.validate_min_length(value)
        self.validate_max_length(value)
        self.validate_regex(value)
        self.validate_unique_slug(sheet, row_idx, value)

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

    def do_pre_coerce_validation(self, sheet, row_idx, value):
        super(NumericColumn, self).do_pre_coerce_validation(sheet, row_idx, value)
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
            obj = self.to_model.objects.get(**{self.to_field: unicode(value)})
        except self.to_model.DoesNotExist:
            raise CellError(u'relation_not_found', u'There is no {} with {}={}',
                    self.to_model.__name__, self.to_field, self.value_repr(value))
        except self.to_model.MultipleObjectsReturned:
            raise CellError(u'relation_found_more', u'There are multiple {} with {}={}',
                    self.to_model.__name__, self.to_field, self.value_repr(value))
        except Exception as e:
            raise CellError(u'relation_type', u'Invalid value {} for {}: {}',
                    self.value_repr(value), self.to_field, e)
        if obj in sheet.book.marked_for_deletion:
            raise CellError(u'deleted', u'{} with {}={} was omitted and is going to be deleted',
                    self.to_model.__name__, self.to_field, self.value_repr(value))
        return obj

    def do_coerce(self, sheet, row_idx, value):
        value = super(ForeignKeyColumn, self).do_coerce(sheet, row_idx, value)
        value = self.apply_relation(sheet, value)
        return value

class ManyToManyColumn(ForeignKeyColumn):
    value_type = basestring

    def __init__(self, label, to_model, **kwargs):
        kwargs.setdefault(u'default', u'')
        super(ManyToManyColumn, self).__init__(label, to_model, null=False, unique=False, **kwargs)

    def apply_relation(self, sheet, value):
        res = []
        for key in value.split():
            obj = super(ManyToManyColumn, self).apply_relation(sheet, key)
            res.append(obj)
        return res


class Field(object):
    is_related = False

    def __init__(self, confirm_changed=None, confirm_unchanged_if_changed=None):
        self.name = None
        self.column = None
        self.confirm_changed = confirm_changed
        self.confirm_unchanged_if_changed = confirm_unchanged_if_changed

    def do_confirm_changed(self, sheet, row_idx, value, original):
        if not self.confirm_changed:
            return
        if original and self.has_changed(original, value):
            inputed = sheet.importer.input_yes_no(
                    u'{} in row {} changed {}:\n\t{} -> {}',
                    u'Is it correct?',
                    sheet.obj_repr(original), row_idx, self.name,
                    self.value_repr(self.value_from_obj(original)),
                    self.value_repr(value),
                    default=u'Y')
            if inputed != u'Y':
                raise RollingError

    def do_confirm_unchanged_if_changed(self, sheet, row_idx, value, values, original):
        if not self.confirm_unchanged_if_changed:
            return
        if original and not self.has_changed(original, value):
            for other_name in ensure_tuple(self.confirm_unchanged_if_changed):
                other_field = sheet.columns.__dict__[other_name].field
                other_value = other_field.value_from_dict(values)
                if other_field.has_changed(original, other_value):
                    inputed = sheet.importer.input_yes_no(
                            u'{} in row {} changed {}:\n\t{} -> {}\nBut not {}:\n\t{}',
                            u'Is it correct?',
                            sheet.obj_repr(original), row_idx, other_field.name,
                            other_field.value_repr(other_field.value_from_obj(original)),
                            other_field.value_repr(other_value),
                            self.name, self.value_repr(value),
                            default=u'Y')
                    if inputed != u'Y':
                        raise RollingError
                    return

    def do_import(self, sheet, row_idx, values, original):
        value = self.value_from_dict(values)
        self.do_confirm_changed(sheet, row_idx, value, original)
        self.do_confirm_unchanged_if_changed(sheet, row_idx, value, values, original)
        return value

    def value_from_obj(self, obj):
        return getattr(obj, self.name)

    def value_from_dict(self, values):
        return values[self.column.label]

    def value_repr(self, value):
        return common_repr(value)

    def has_changed(self, obj, value):
        return getattr(obj, self.name) != value

    def save(self, obj, value):
        setattr(obj, self.name, value)

class FieldChoicesField(Field):

    def __init__(self, field_choices, **kwargs):
        super(FieldChoicesField, self).__init__(**kwargs)
        self.field_choices = field_choices

    def value_repr(self, value):
        return self.field_choices._inverse[value]

class ForeignKeyField(Field):
    is_related = False

    def value_from_obj(self, obj):
        try:
            return getattr(obj, self.name)
        except ObjectDoesNotExist:
            return None

    def has_changed(self, obj, value):
        try:
            return getattr(obj, self.name) != value
        except ObjectDoesNotExist:
            return True

class ManyToManyField(Field):
    is_related = True

    def value_from_obj(self, obj):
        return list(getattr(obj, self.name).all())

    def has_changed(self, obj, value):
        return set(getattr(obj, self.name).all()) != set(value)


class Sheet(object):
    label = None
    model = None
    ignore_superfluous_columns = False
    delete_omitted = None
    columns = None

    def __init__(self, book):
        self.book = book
        self.importer = book.importer
        self.column_map = None

    def error(self, code, msg, *args, **kwargs):
        if code:
            code = (self.label, code)
        self.importer.error(code, msg, *args, **kwargs)

    def cell_error(self, code, row_idx, column, msg, *args, **kwargs):
        self.error((column.label, code), u'Invalid value in row {} of "{}.{}": {}',
                row_idx, self.label, column.label, msg.format(*args, **kwargs))

    def reset_model(self, model):
        count = model.objects.count()
        model.objects.all().delete()
        self.importer.write(1, u'Reset {}: {} deleted', model.__name__, count)

    def do_reset(self):
        self.reset_model(self.model)

    def validate_structure(self):
        errors = 0

        self.column_map = {}
        row = next(self.book.wb[self.label].rows, [])
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
        if not self.ignore_superfluous_columns:
            for column in superfluous_columns:
                self.error(None, u'Sheet "{}" contains unexpected column: {}', self.label, column)
                errors += 1

        if errors:
            raise RollingError(errors)

    def process_cell(self, row_idx, row, column):
        try:
            col_idx = self.column_map[column.label]
        except KeyError:
            self.cell_error(u'missing', row_idx, column, u'Missing column')
            raise RollingError

        try:
            value = row[col_idx].value
        except IndexError:
            value = None
        if value is None:
            value = column.default

        try:
            return column.do_import(self, row_idx, value)
        except CellError as e:
            self.cell_error(e.code, row_idx, column, u'{}', e)
            raise RollingError

    def process_row(self, row_idx, row):
        res = {}
        errors = 0
        for column in self.columns.__dict__.values():
            try:
                res[column.label] = self.process_cell(row_idx, row, column)
            except RollingError as e:
                errors += e.count
        if errors:
            raise RollingError(errors)
        return res

    def process_rows(self, rows):
        res = OrderedDict()
        errors = 0
        for row_idx, row in enumerate(rows, start=1):
            if row_idx == 1 or all(c.value is None for c in row):
                continue
            try:
                res[row_idx] = self.process_row(row_idx, row)
            except RollingError as e:
                errors += e.count
        if errors:
            raise RollingError(errors)
        return res

    def process_fields(self, row_idx, values, original):
        res = {}
        errors = 0
        for column in self.columns.__dict__.values():
            if column.field is not None:
                field = column.field
                try:
                    res[field.name] = field.do_import(self, row_idx, values, original)
                except RollingError as e:
                    errors += e.count
        if errors:
            raise RollingError(errors)
        return res

    def save_object(self, fields, original):
        # Save only if the instance is new or changed to prevent excessive change history. Many to
        # many relations may only be saved after the instance is created.
        obj = original or self.model()
        has_changed = False
        for column in self.columns.__dict__.values():
            if column.field is not None:
                field = column.field
                value = fields[field.name]
                if not field.is_related and field.has_changed(obj, value):
                    field.save(obj, value)
                    has_changed = True
        if has_changed:
            obj.save()
        for column in self.columns.__dict__.values():
            if column.field is not None:
                field = column.field
                value = fields[field.name]
                if field.is_related and field.has_changed(obj, value):
                    field.save(obj, value)
                    has_changed = True
        return obj, has_changed

    def save_objects(self, rows):
        errors = 0
        stats = Bunch(created=0, changed=0, unchanged=0, deleted=0)
        originals = {o.pk: o for o in self.model.objects.all()}
        for row_idx, values in rows.items():
            try:
                pk = values[self.columns.pk.label]
                original = originals.pop(pk, None)
                fields = self.process_fields(row_idx, values, original)
                assert fields[u'pk'] == pk

                obj, has_changed = self.save_object(fields, original)
                if has_changed and original:
                    self.importer.write(2, u'Changed {}', self.obj_repr(obj))
                    stats.changed += 1
                elif has_changed:
                    self.importer.write(2, u'Created {}', self.obj_repr(obj))
                    stats.created += 1
                else:
                    stats.unchanged += 1
            except RollingError as e:
                errors += e.count
        # Mark omitted instances for deletion or add an error if delete is not permitted. Don't
        # delete anything if there were any errors as we don't know which instances are missing for
        # real and which are missing because of errors. The instances will be deleted only after
        # all sheets are imported to prevent unintentional cascades.
        if errors:
            raise RollingError(errors)
        for obj in originals.values():
            if self.delete_omitted:
                self.book.marked_for_deletion[obj] = self
                stats.deleted += 1
            else:
                self.error(u'omitted', u'Omitted {}', self.obj_repr(obj))
                errors += 1
        if errors:
            raise RollingError(errors)
        return stats

    def do_import(self):
        self.importer.write(1, u'Importing {}...', self.model.__name__)
        errors = 0

        try:
            self.validate_structure()
        except RollingError as e:
            errors += e.count

        try:
            rows = self.process_rows(self.book.wb[self.label].rows)
            stats = self.save_objects(rows)
        except RollingError as e:
            errors += e.count

        if errors:
            self.importer.write(1, u'Importing {} failed.', self.model.__name__)
            raise RollingError(errors)

        self.importer.write(1,
                u'Imported {}: {} created, {} changed, {} unchanged and {} marked for deletion',
                self.model.__name__, stats.created, stats.changed, stats.unchanged, stats.deleted)

    def _collect_related_format(self, collected, level=0):
        res = []
        for obj in collected:
            if isinstance(obj, list):
                res.extend(self._collect_related_format(obj, level=level+1))
            else:
                res.append(u'\n{} -- {}: {}'.format(u'    '*level,
                        capfirst(obj._meta.verbose_name), force_text(obj)))
        return res

    def _collect_related(self, obj):
        collector = NestedObjects(using=DEFAULT_DB_ALIAS)
        collector.collect([obj])
        collected = collector.nested()
        return u''.join(self._collect_related_format(collected))

    def delete_object(self, obj):
        inputed = self.importer.input_yes_no(
                u'{} was omitted. All the following related items will be deleted with it:{}',
                u'Are you sure, you want to delete it?',
                self.obj_repr(obj), self._collect_related(obj),
                default=u'N')
        if inputed != u'Y':
            raise RollingError
        obj.delete()

    def obj_repr(self, obj):
        return common_repr(obj)

class Book(object):
    sheets = None

    def __init__(self, importer, wb):
        self.importer = importer
        self.wb = wb
        self.actual_sheets = None
        self.marked_for_deletion = None

    def validate_structure(self):
        expected_sheets = set(s.label for s in self.sheets)
        found_sheets = {n for n in self.wb.get_sheet_names() if not n.startswith(u'#')}
        missing_sheets = expected_sheets - found_sheets
        superfluous_sheets = found_sheets - expected_sheets
        self.actual_sheets = expected_sheets & found_sheets
        if superfluous_sheets:
            inputed = self.importer.input_yes_no(
                    u'The file contains the following unexpected sheets:{}',
                    u'Ignore them?',
                    u''.join(u'\n\t-- {}'.format(s) for s in superfluous_sheets),
                    default=u'Y')
            if inputed != u'Y':
                raise CommandError(u'The file contains unexpected sheets')
        if missing_sheets:
            inputed = self.importer.input_yes_no(
                    u'The file does not contain the following required sheets:{}\n'
                    u'It contains only the following sheets:{}',
                    u'Skip the missing sheets and import only the present ones?',
                    u''.join(u'\n\t-- {}'.format(s) for s in missing_sheets),
                    u''.join(u'\n\t-- {}'.format(s) for s in self.actual_sheets),
                    default=u'Y')
            if inputed != u'Y':
                raise CommandError(u'The file does not contain required sheets')

    def do_import(self):
        errors = 0
        self.validate_structure()

        sheets = [s(self) for s in self.sheets]
        if self.importer.reset:
            for sheet in reversed(sheets):
                if sheet.label in self.actual_sheets:
                    sheet.do_reset()

        self.marked_for_deletion = OrderedDict()
        for sheet in sheets:
            if sheet.label in self.actual_sheets:
                try:
                    sheet.do_import()
                except RollingError as e:
                    errors += e.count

        self.importer.write(1, u'Deleting...')
        for obj, sheet in reversed(self.marked_for_deletion.items()):
            try:
                sheet.delete_object(obj)
            except RollingError as e:
                errors += e.count

        if errors:
            raise RollingError(errors)

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

        try:
            wb = load_workbook(filename, read_only=True)
        except Exception as e:
            raise CommandError(u'Could not read input file: {}'.format(e))

        try:
            self.book(self, wb).do_import()
        except RollingError as e:
            raise CommandError(u'Detected {} errors; Rolled back'.format(e.count))

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
    delete_omitted = True

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
            iczsj=IntegerColumn(u'ICZSJ', # FIXME: foreign key
                min_value=1,
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
    delete_omitted = True

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

class ObligeeBook(Book):
    sheets = [ObligeeTagSheet, ObligeeGroupSheet, ObligeeSheet, ObligeeAliasSheet]


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
        except (KeyboardInterrupt, EOFError):
            self.stdout.write(u'\n')
            raise CommandError(u'Aborted')
        except RollbackDryRun:
            pass
