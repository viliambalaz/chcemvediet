# vim: expandtab
# -*- coding: utf-8 -*-
import re
from collections import defaultdict
from optparse import make_option
from openpyxl import load_workbook

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import color_style
from django.db import transaction
from django.conf import settings

from poleno.utils.forms import validate_comma_separated_emails
from poleno.utils.misc import Bunch, squeeze
from chcemvediet.apps.obligees.models import Obligee, HistoricalObligee
from chcemvediet.apps.inforequests.models import Inforequest


zip_regex = re.compile(r'^\d\d\d \d\d$')
tag_regex = re.compile(r'^[\w-]+$')
tags_regex_0 = re.compile(r'^([\w-]+(\s+[\w-]+)*)?$') # 0 or more tags
tags_regex_1 = re.compile(r'^[\w-]+(\s+[\w-]+)*$') # 1 or more tags
hierarchy_regex = re.compile(r'^[\w-]+(/[\w-]+)*$')
hierarchies_regex_0 = re.compile(r'^([\w-]+(/[\w-]+)*(\s+[\w-]+(/[\w-]+)*)*)?$') # 0 or more hierarchies
hierarchies_regex_1 = re.compile(r'^[\w-]+(/[\w-]+)*(\s+[\w-]+(/[\w-]+)*)*$') # 1 or more hierarchies


class RollingCommandError(CommandError):
    def __init__(self, count=1):
        self.count = count
        super(CommandError, self).__init__(
                u'Detected {} errors; Rollbacking and giving up'.format(count))

class RollbackDryRun(Exception):
    pass


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

        expected_columns = set(c.column for c in self.columns.__dict__.values())
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
        self.error((column, code), u'Invalid value in row {} of "{}.{}": {}',
                idx+1, self.label, column, msg.format(*args, **kwargs))
        raise RollingCommandError

    def validate_type(self, value, idx, column, typ):
        if not isinstance(typ, tuple):
            typ = (typ,)
        if not isinstance(value, typ):
            self.cell_error(u'type', idx, column, u'Expecting {} but found {}',
                    u', '.join(t.__name__ for t in typ), value.__class__.__name__)
        return value

    def validate_min_value(self, value, idx, column, min_value):
        if value < min_value:
            self.cell_error(u'min_value', idx, column,
                    u'Expecting value not smaller than "{}" but found "{}"', min_value, value)
        return value

    def validate_max_value(self, value, idx, column, max_value):
        if value > max_value:
            self.cell_error(u'max_value', idx, column,
                    u'Expecting value not bigger than "{}" but found "{}"', max_value, value)
        return value

    def validate_nonempty(self, value, idx, column, nonempty):
        if nonempty and not value:
            self.cell_error(u'nonempty', idx, column,
                    u'Expecting nonempty value but found "{}"', value)
        return value

    def validate_choices(self, value, idx, column, choices):
        if value not in choices:
            self.cell_error(u'choices', idx, column, u'Expecting one of {} but found "{}"',
                    u', '.join(u'"{}"'.format(c) for c in choices), value)
        if isinstance(choices, dict):
            value = choices[value]
        return value

    def validate_regex(self, value, idx, column, regex):
        if not regex.match(value):
            self.cell_error(u'regex', idx, column,
                    u'Expecting value matching "{}" but found "{}"', regex.pattern, value)
        return value

    def validate_validators(self, value, idx, column, validators):
        if not isinstance(validators, (list, tuple)):
            validators = [validators]
        for validator in validators:
            try:
                validator(value)
            except ValidationError as e:
                self.cell_error((u'validator', validator.__name__), idx, column,
                        u'{}', u'; '.join(e.messages))
        return value

    def validate_cell(self, idx, row, column, default=None, typ=None,
                min_value=None, max_value=None, nonempty=None, choices=None, regex=None,
                validators=None):
        try:
            col_idx = self.column_map[column]
        except KeyError:
            self.cell_error(u'missing', idx, column, u'Missing column')

        try:
            value = row[col_idx].value
        except IndexError:
            value = None
        if value is None:
            value = default

        if typ is not None:
            value = self.validate_type(value, idx, column, typ)
        if min_value is not None:
            value = self.validate_min_value(value, idx, column, min_value)
        if max_value is not None:
            value = self.validate_max_value(value, idx, column, max_value)
        if nonempty is not None:
            value = self.validate_nonempty(value, idx, column, nonempty)
        if choices is not None:
            value = self.validate_choices(value, idx, column, choices)
        if regex is not None:
            value = self.validate_regex(value, idx, column, regex)
        if validators is not None:
            value = self.validate_validators(value, idx, column, validators)
        return value

    def validate_row(self, idx, row):
        res = {}
        errors = 0
        for column in self.columns.__dict__.values():
            try:
                res[column.column] = self.validate_cell(idx, row, **column.__dict__)
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
        for idx, row in enumerate(self.ws.rows):
            if idx == 0 or all(c.value is None for c in row):
                continue
            try:
                values = self.validate_row(idx, row)
                original = originals.pop(values[self.columns.pk.column], None)
                fields = self.get_obj_fields(original, values)
                assert fields[u'pk'] == values[self.columns.pk.column]

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

        # Delete omitted instances or add an error if delete is not permitted
        for obj in originals.values():
            if self.delete_omitted:
                inputed = self.importer.input_yes_no(
                        u'{} {} was omitted. Are you sure, you want to delete it?',
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

    def get_obj_fields(self, original, values):
        raise NotImplementedError

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

        msg = self.color_style.WARNING(u'Error: ' + msg.format(*args, **kwargs))

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

    def input_yes_no(self, prompt, *args, **kwargs):
        default = kwargs.pop(u'default', u'')
        while True:
            self.stdout.write(self.color_style.WARNING(
                    u'Warning: {} Yes/No/Abort [{}]: '.format(
                        prompt.format(*args, **kwargs), default)), ending=u'')
            inputed = raw_input() or default
            if not inputed:
                self.stdout.write(self.color_style.ERROR(u'Error: The value is required.'))
                continue
            if inputed.upper() not in [u'Y', u'YES', u'N', u'NO', u'A', u'ABORT']:
                self.stdout.write(self.color_style.ERROR(u'Error: Enter Yes, No or Abort.'))
                continue
            if inputed.upper() in [u'A', u'ABORT']:
                raise CommandError(u'Aborted')
            return inputed.upper()[0]

    @transaction.atomic
    def do_import(self, filename):
        if self.dry_run:
            self.write(0, u'Importing: {} (dry run)', filename)
        else:
            self.write(0, u'Importing: {}', filename)

        self.book(self).do_import(filename)

        if self.dry_run:
            self.write(0, u'Rollbacked (dry run)')
            raise RollbackDryRun
        else:
            self.write(0, u'Done.')


class TagSheet(Sheet):
    label = u'Tagy'
    model = None # FIXME
    delete_omitted = True

    columns = Bunch( # {{{
            pk=Bunch( # FIXME: unique pk
                column=u'Interne ID tagu',
                typ=int, min_value=1,
                ),
            key=Bunch( # FIXME: unique slug
                column=u'Kod', typ=unicode, regex=tag_regex,
                ),
            name=Bunch(
                column=u'Nazov',
                typ=unicode, nonempty=True,
                ),
            ) # }}}

    def get_obj_fields(self, original, values):
        raise NotImplementedError

class HierarchySheet(Sheet):
    label = u'Hierarchia'
    model = None # FIXME
    delete_omitted = True

    columns = Bunch( # {{{
            pk=Bunch( # FIXME: unique pk
                column=u'Interne ID hierarchie',
                typ=int, min_value=1,
                ),
            key=Bunch( # FIXME: unique slug
                column=u'Kod',
                typ=unicode, regex=hierarchy_regex,
                ),
            name=Bunch(
                column=u'Nazov v hierarchii',
                typ=unicode, nonempty=True,
                ),
            description=Bunch(
                column=u'Popis',
                typ=unicode, default=u'',
                ),
            ) # }}}

    def get_obj_fields(self, original, values):
        raise NotImplementedError

class ObligeeSheet(Sheet):
    label = u'Obligees'
    model = Obligee
    delete_omitted = False

    columns = Bunch( # {{{
            pk=Bunch( # FIXME: unique pk
                column=u'Interne ID institucie',
                typ=int, min_value=1,
                ),
            official_name=Bunch(
                column=u'Oficialny nazov',
                typ=unicode, nonempty=True,
                ),
            name=Bunch( # FIXME: unique slug
                column=u'Rozlisovaci nazov nominativ',
                typ=unicode, nonempty=True,
                ),
            name_genitive=Bunch(
                column=u'Rozlisovaci nazov genitiv',
                typ=unicode, nonempty=True,
                ),
            name_dative=Bunch(
                column=u'Rozlisovaci nazov dativ',
                typ=unicode, nonempty=True,
                ),
            name_accusative=Bunch(
                column=u'Rozlisovaci nazov akuzativ',
                typ=unicode, nonempty=True,
                ),
            name_locative=Bunch(
                column=u'Rozlisovaci nazov lokal',
                typ=unicode, nonempty=True,
                ),
            name_instrumental=Bunch(
                column=u'Rozlisovaci nazov instrumental',
                typ=unicode, nonempty=True,
                ),
            name_gender=Bunch(
                column=u'Rod',
                typ=unicode, choices=[u'muzsky', u'zensky', u'stredny', u'pomnozny'],
                ),
            ico=Bunch(
                column=u'ICO',
                typ=unicode, default=u'',
                ),
            hierarchy=Bunch( # FIXME: m2m foreign key
                column=u'Hierarchia',
                typ=unicode, regex=hierarchies_regex_1,
                ),
            street=Bunch(
                column=u'Adresa: Ulica s cislom',
                typ=unicode, nonempty=True,
                ),
            city=Bunch(
                column=u'Adresa: Obec',
                typ=unicode, nonempty=True,
                ),
            zip=Bunch(
                column=u'Adresa: PSC',
                typ=unicode, regex=zip_regex,
                ),
            emails=Bunch(
                column=u'Adresa: Email',
                typ=unicode, default=u'', validators=validate_comma_separated_emails,
                # Override with dummy emails for local and dev server modes
                ),
            official_description=Bunch(
                column=u'Oficialny popis',
                typ=unicode, default=u'',
                ),
            simple_description=Bunch(
                column=u'Zrozumitelny popis',
                typ=unicode, default=u'',
                ),
            status=Bunch(
                column=u'Stav',
                typ=unicode,
                choices={
                    u'aktivny': Obligee.STATUSES.PENDING,
                    u'neaktivny': Obligee.STATUSES.DISSOLVED,
                    },
                ),
            type=Bunch(
                column=u'Typ',
                typ=int, choices=[1, 2, 3, 4],
                ),
            latitude=Bunch(
                column=u'Lat',
                typ=float, min_value=-90.0, max_value=90.0,
                ),
            longitude=Bunch(
                column=u'Lon',
                typ=float, min_value=-180.0, max_value=180.0,
                ),
            iczsj=Bunch( # FIXME: foreign key
                column=u'ICZSJ',
                typ=int, min_value=1,
                ),
            tags=Bunch( # FIXME: m2m foreign key
                column=u'Tagy',
                typ=unicode, default=u'', regex=tags_regex_0,
                ),
            notes=Bunch(
                column=u'Poznamka',
                typ=unicode, default=u'',
                ),
            ) # }}}

    def get_obj_fields(self, original, values):
        errors = 0

        fields = {}
        fields[u'pk'] = values[self.columns.pk.column]
        fields[u'name'] = values[self.columns.name.column]
        fields[u'street'] = values[self.columns.street.column]
        fields[u'city'] = values[self.columns.city.column]
        fields[u'zip'] = values[self.columns.zip.column]
        fields[u'emails'] = values[self.columns.emails.column]
        fields[u'status'] = values[self.columns.status.column]

        # Dummy emails for local and dev server modes
        if hasattr(settings, u'OBLIGEE_DUMMY_MAIL'):
            fields[u'emails'] = Obligee.dummy_email(fields[u'name'], settings.OBLIGEE_DUMMY_MAIL)

        if original and fields[u'status'] != original.status:
            inputed = self.importer.input_yes_no(
                    u'Obligee ID={} "{}" changed status: {} -> {}; Is it correct?',
                    fields[u'pk'], fields[u'name'],
                    Obligee.STATUSES._inverse[original.status],
                    Obligee.STATUSES._inverse[fields[u'status']],
                    default=u'Y')
            if inputed != u'Y':
                errors += 1

        if errors:
            raise RollingCommandError(errors)

        return fields

    def get_obj_repr(self, obj):
        return u'ID={} "{}"'.format(obj.pk, obj.name)

class AliasSheet(Sheet):
    label = u'Aliasy'
    model = None # FIXME
    delete_omitted = True

    columns = Bunch( # {{{
            pk=Bunch( # FIXME: unique pk
                column=u'Interne ID aliasu',
                typ=int, min_value=1,
                ),
            obligee_pk=Bunch( # FIXME: foreign key
                column=u'ID institucie',
                typ=int, min_value=1,
                ),
            obligee_name=Bunch( # FIXME: overit vzhladom na ID institucie
                column=u'Rozlisovaci nazov institucie',
                typ=unicode, nonempty=True,
                ),
            alias=Bunch( # FIXME: unique slug
                column=u'Alternativny nazov',
                typ=unicode, nonempty=True,
                ),
            description=Bunch(
                column=u'Vysvetlenie',
                typ=unicode, default=u'',
                ),
            notes=Bunch(
                column=u'Poznamka',
                typ=unicode, default=u'',
                ),
            ) # }}}

    def get_obj_fields(self, original, values):
        raise NotImplementedError

class ObligeeBook(Book):
    #sheets = [TagSheet, HierarchySheet, ObligeeSheet, AliasSheet]
    sheets = [ObligeeSheet]

    def do_import(self, filename):

        # Reset obligees if requested
        if self.importer.reset:
            count = Inforequest.objects.count()
            if count:
                inputed = self.importer.input_yes_no(squeeze(u"""
                        Discarding current obligees will discard all existing inforequests as well.
                        There are {} inforequests. Are you sure, you want to discard them?
                        """), count, default=u'N')
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
        make_option(u'--dry-run', action=u'store_true', dest=u'dry_run', default=False,
            help=squeeze(u"""
                Just show if the file would be imported correctly. Rollback all changes at the end.
                """)),
        make_option(u'--reset', action=u'store_true', dest=u'reset', default=False,
            help=squeeze(u"""
                Discard current obligees before imporing the file.
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
