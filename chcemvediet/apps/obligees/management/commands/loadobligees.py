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

SHEETS = Bunch( # {{{
        obligees=u'Obligees',
        hierarchy=u'Hierarchia',
        aliases=u'Aliasy',
        tags=u'Tagy',
        ) # }}}

COLUMNS = Bunch( # {{{
        obligees=Bunch(
            pk=u'Interne ID institucie',
            official_name=u'Oficialny nazov',
            name=u'Rozlisovaci nazov nominativ',
            name_genitive=u'Rozlisovaci nazov genitiv',
            name_dative=u'Rozlisovaci nazov dativ',
            name_accusative=u'Rozlisovaci nazov akuzativ',
            name_locative=u'Rozlisovaci nazov lokal',
            name_instrumental=u'Rozlisovaci nazov instrumental',
            name_gender=u'Rod',
            ico=u'ICO',
            hierarchy=u'Hierarchia',
            street=u'Adresa: Ulica s cislom',
            city=u'Adresa: Obec',
            zip=u'Adresa: PSC',
            emails=u'Adresa: Email',
            official_description=u'Oficialny popis',
            simple_description=u'Zrozumitelny popis',
            status=u'Stav',
            type=u'Typ',
            latitude=u'Lat',
            longitude=u'Lon',
            iczsj=u'ICZSJ',
            tags=u'Tagy',
            notes=u'Poznamka',
            ),
        hierarchy=Bunch(
            pk=u'Interne ID hierarchie',
            key=u'Kod',
            name=u'Nazov v hierarchii',
            description=u'Popis',
            ),
        aliases=Bunch(
            pk=u'Interne ID aliasu',
            obligee_pk=u'ID institucie',
            obligee_name=u'Rozlisovaci nazov institucie',
            alias=u'Alternativny nazov',
            description=u'Vysvetlenie',
            notes=u'Poznamka',
            ),
        tags=Bunch(
            pk=u'Interne ID tagu',
            key=u'Kod',
            name=u'Nazov',
            ),
        ) # }}}

STRUCTURE = { # {{{
        SHEETS.obligees: { # {{{
            COLUMNS.obligees.pk: dict( # FIXME: unique pk
                typ=int,
                min_value=1,
                ),
            COLUMNS.obligees.official_name: dict(
                typ=unicode,
                nonempty=True,
                ),
            COLUMNS.obligees.name: dict( # FIXME: unique slug
                typ=unicode,
                nonempty=True,
                ),
            COLUMNS.obligees.name_genitive: dict(
                typ=unicode,
                nonempty=True,
                ),
            COLUMNS.obligees.name_dative: dict(
                typ=unicode,
                nonempty=True,
                ),
            COLUMNS.obligees.name_accusative: dict(
                typ=unicode,
                nonempty=True,
                ),
            COLUMNS.obligees.name_locative: dict(
                typ=unicode,
                nonempty=True,
                ),
            COLUMNS.obligees.name_instrumental: dict(
                typ=unicode,
                nonempty=True,
                ),
            COLUMNS.obligees.name_gender: dict(
                typ=unicode,
                choices=[u'muzsky', u'zensky', u'stredny', u'pomnozny'],
                ),
            COLUMNS.obligees.ico: dict(
                typ=unicode,
                default=u'',
                ),
            COLUMNS.obligees.hierarchy: dict( # FIXME: foreign key
                typ=unicode,
                regex=hierarchies_regex_1,
                ),
            COLUMNS.obligees.street: dict(
                typ=unicode,
                nonempty=True,
                ),
            COLUMNS.obligees.city: dict(
                typ=unicode,
                nonempty=True,
                ),
            COLUMNS.obligees.zip: dict(
                typ=unicode,
                regex=zip_regex,
                ),
            COLUMNS.obligees.emails: dict(
                typ=unicode,
                default=u'',
                validators=validate_comma_separated_emails,
                # Override with dummy emails for local and dev server modes
                ),
            COLUMNS.obligees.official_description: dict(
                typ=unicode,
                default=u'',
                ),
            COLUMNS.obligees.simple_description: dict(
                typ=unicode,
                default=u'',
                ),
            COLUMNS.obligees.status: dict(
                typ=unicode,
                choices={u'aktivny': Obligee.STATUSES.PENDING, u'neaktivny': Obligee.STATUSES.DISSOLVED},
                ),
            COLUMNS.obligees.type: dict(
                typ=int,
                choices=[1, 2, 3, 4],
                ),
            COLUMNS.obligees.latitude: dict(
                typ=float,
                min_value=-90.0,
                max_value=90.0,
                ),
            COLUMNS.obligees.longitude: dict(
                typ=float,
                min_value=-180.0,
                max_value=180.0,
                ),
            COLUMNS.obligees.iczsj: dict( # FIXME: foreign key
                typ=int,
                min_value=1,
                ),
            COLUMNS.obligees.tags: dict( # FIXME: foreign key
                typ=unicode,
                default=u'',
                regex=tags_regex_0,
                ),
            COLUMNS.obligees.notes: dict(
                typ=unicode,
                default=u'',
                ),
            }, # }}}
        SHEETS.hierarchy: { # {{{
            COLUMNS.hierarchy.pk: dict( # FIXME: unique pk
                typ=int,
                min_value=1,
                ),
            COLUMNS.hierarchy.key: dict( # FIXME: unique slug
                typ=unicode,
                regex=hierarchy_regex,
                ),
            COLUMNS.hierarchy.name: dict(
                typ=unicode,
                nonempty=True,
                ),
            COLUMNS.hierarchy.description: dict(
                typ=unicode,
                default=u'',
                ),
            }, # }}}
        SHEETS.aliases: { # {{{
            COLUMNS.aliases.pk: dict( # FIXME: unique pk
                typ=int,
                min_value=1,
                ),
            COLUMNS.aliases.obligee_pk: dict( # FIXME: foreign key
                typ=int,
                min_value=1,
                ),
            COLUMNS.aliases.obligee_name: dict( # FIXME: overit vzhladom na ID institucie
                typ=unicode,
                nonempty=True,
                ),
            COLUMNS.aliases.alias: dict( # FIXME: unique slug
                typ=unicode,
                nonempty=True,
                ),
            COLUMNS.aliases.description: dict(
                typ=unicode,
                default=u'',
                ),
            COLUMNS.aliases.notes: dict(
                typ=unicode,
                default=u'',
                ),
            }, # }}}
        SHEETS.tags: { # {{{
            COLUMNS.tags.pk: dict( # FIXME: unique pk
                typ=int,
                min_value=1,
                ),
            COLUMNS.tags.key: dict( # FIXME: unique slug
                typ=unicode,
                regex=tag_regex,
                ),
            COLUMNS.tags.name: dict(
                typ=unicode,
                nonempty=True,
                ),
            }, # }}}
        } # }}}


class RollingCommandError(CommandError):
    def __init__(self, count=1):
        self.count = count
        super(CommandError, self).__init__(u'Detected {} errors; Rollbacking and giving up'.format(count))

class RollbackDryRun(Exception):
    pass


class Importer(object):

    def __init__(self, filename, options, stdout):
        self.filename = filename
        self.options = options
        self.stdout = stdout
        self.wb = None
        self.columns = None
        self.color_style = color_style()
        self._error_cache = defaultdict(int)

    def print_error(self, msg, args, kwargs, suffix=u''):
        msg = msg.format(*args, **kwargs)
        msg = u'Error: {}'.format(msg)
        msg = self.color_style.WARNING(msg)
        if suffix:
            suffix = u' ({})'.format(suffix)
            msg += suffix
        self.stdout.write(msg)

    def error(self, msg, *args, **kwargs):
        code = kwargs.pop(u'code', None)

        if self.options[u'verbosity'] == u'1':
            if code:
                self._error_cache[code] += 1
                if self._error_cache[code] < 3:
                    self.print_error(msg, args, kwargs)
                elif self._error_cache[code] == 3:
                    self.print_error(msg, args, kwargs, u'skipping further similar errors')
            else:
                self.print_error(msg, args, kwargs)

        elif self.options[u'verbosity'] >= u'2':
            self.print_error(msg, args, kwargs)

    def validate_structure(self):
        errors = 0

        expected_sheets = set(STRUCTURE)
        found_sheets = {n for n in self.wb.get_sheet_names() if not n.startswith(u'#')}
        missing_sheets = expected_sheets - found_sheets
        superfluous_sheets = found_sheets - expected_sheets
        for sheet in missing_sheets:
            self.error(u'The file does not contain required sheet: {}', sheet)
            errors += 1
        for sheet in superfluous_sheets:
            self.error(u'The file contains unexpected sheet: {}', sheet)
            errors += 1

        self.columns = {}
        for sheet in expected_sheets & found_sheets:
            self.columns[sheet] = {}
            row = next(self.wb[sheet].rows, [])
            for idx, column in enumerate(row):
                if column.value is not None and not column.value.startswith(u'#'):
                    self.columns[sheet][column.value] = idx

        for sheet in expected_sheets & found_sheets:
            expected_columns = set(STRUCTURE[sheet])
            found_columns = set(self.columns[sheet])
            missing_columns = expected_columns - found_columns
            superfluous_columns = found_columns - expected_columns
            for column in missing_columns:
                self.error(u'Sheet "{}" does not contain required column: {}', sheet, column)
                errors += 1
            for column in superfluous_columns:
                self.error(u'Sheet "{}" contains unexpected column: {}', sheet, column)
                errors += 1

        if errors:
            raise RollingCommandError(errors)

    def cell_error(self, code, idx, sheet, column, msg):
        code = u'{}:{}:{}'.format(code, sheet, column)
        self.error(u'Invalid value in row {} of "{}.{}": {}', idx+1, sheet, column, msg, code=code)
        raise RollingCommandError

    def validate_type(self, value, idx, sheet, column, typ):
        if not isinstance(typ, tuple):
            typ = (typ,)
        if not isinstance(value, typ):
            exp = u', '.join(t.__name__ for t in typ)
            msg = u'Expecting {} but found {}'.format(exp, value.__class__.__name__)
            self.cell_error(u'type', idx, sheet, column, msg)
        return value

    def validate_min_value(self, value, idx, sheet, column, min_value):
        if value < min_value:
            msg = u'Expecting value not smaller than "{}" but found "{}"'.format(min_value, value)
            self.cell_error(u'min_value', idx, sheet, column, msg)
        return value

    def validate_max_value(self, value, idx, sheet, column, max_value):
        if value > max_value:
            msg = u'Expecting value not bigger than "{}" but found "{}"'.format(max_value, value)
            self.cell_error(u'max_value', idx, sheet, column, msg)
        return value

    def validate_nonempty(self, value, idx, sheet, column, nonempty):
        if nonempty and not value:
            msg = u'Expecting nonempty value but found "{}"'.format(value)
            self.cell_error(u'nonempty', idx, sheet, column, msg)
        return value

    def validate_choices(self, value, idx, sheet, column, choices):
        if value not in choices:
            exp = u', '.join(u'"{}"'.format(c) for c in choices)
            msg = u'Expecting one of {} but found "{}"'.format(exp, value)
            self.cell_error(u'choices', idx, sheet, column, msg)
        if isinstance(choices, dict):
            value = choices[value]
        return value

    def validate_regex(self, value, idx, sheet, column, regex):
        if not regex.match(value):
            msg = u'Expecting value matching "{}" but found "{}"'.format(regex.pattern, value)
            self.cell_error(u'regex', idx, sheet, column, msg)
        return value

    def validate_validators(self, value, idx, sheet, column, validators):
        if not isinstance(validators, (list, tuple)):
            validators = [validators]
        for validator in validators:
            try:
                validator(value)
            except ValidationError as e:
                code = u'validator:{}'.format(validator.__name__)
                msg = u'; '.join(e.messages)
                self.cell_error(code, idx, sheet, column, msg)
        return value

    def validate_cell(self, idx, row, sheet, column, default=None, typ=None,
                min_value=None, max_value=None, nonempty=None, choices=None, regex=None,
                validators=None):
        try:
            col_idx = self.columns[sheet][column]
        except KeyError:
            self.cell_error(u'missing', idx, sheet, column, u'Missing column')

        try:
            value = row[col_idx].value
        except IndexError:
            value = None
        if value is None:
            value = default

        if typ is not None:
            value = self.validate_type(value, idx, sheet, column, typ)
        if min_value is not None:
            value = self.validate_min_value(value, idx, sheet, column, min_value)
        if max_value is not None:
            value = self.validate_max_value(value, idx, sheet, column, max_value)
        if nonempty is not None:
            value = self.validate_nonempty(value, idx, sheet, column, nonempty)
        if choices is not None:
            value = self.validate_choices(value, idx, sheet, column, choices)
        if regex is not None:
            value = self.validate_regex(value, idx, sheet, column, regex)
        if validators is not None:
            value = self.validate_validators(value, idx, sheet, column, validators)
        return value

    def validate_row(self, idx, row, sheet):
        res = {}
        errors = 0
        for column, kwargs in STRUCTURE[sheet].items():
            try:
                res[column] = self.validate_cell(idx, row, sheet, column, **kwargs)
            except RollingCommandError as e:
                errors += e.count
        if errors:
            raise RollingCommandError(errors)
        return res

    def iterate_sheet(self, sheet):
        try:
            self.columns[sheet]
        except KeyError:
            self.error(u'Skipping sheet: {}', sheet)
            raise RollingCommandError

        errors = 0
        count = 0
        for idx, row in enumerate(self.wb[sheet].rows):
            if idx == 0 or all(c.value is None for c in row):
                continue
            try:
                yield self.validate_row(idx, row, sheet)
            except RollingCommandError as e:
                errors += e.count
            count += 1

        if errors:
            raise RollingCommandError(errors)

    def reset_model(self, model):
        count = model.objects.count()
        model.objects.all().delete()
        if self.options[u'verbosity'] >= u'1':
            self.stdout.write(u'Reset model {}: {} deleted'.format(model.__name__, count))

    def import_model(self, sheet, model, show, delete):
        created, changed, unchanged, deleted = 0, 0, 0, 0
        originals = {o.pk: o for o in model.objects.all()}
        for row in self.iterate_sheet(sheet):
            fields = {}
            yield row, fields

            # Save only if the instance is new or changed to prevent excessive change history
            original = originals.pop(fields[u'pk'], None)
            if not original or any(fields[f] != getattr(original, f) for f in fields):
                obj = model(**fields)
                obj.save()
                if original:
                    changed += 1
                else:
                    created += 1
                if self.options[u'verbosity'] >= u'2':
                    msg = u'Changed' if original else u'Created'
                    msg = u'{} {}: ID={} "{}"'.format(msg, model.__name__, obj.pk, fields[show])
                    self.stdout.write(msg)
            else:
                unchanged += 1

        # Delete omitted instances or add an error if delete is not permitted
        for obj in originals.values():
            if delete:
                obj.delete()
                deleted += 1
            else:
                code = u'omitted:{}'.format(sheet)
                self.error(u'Omitted {}: ID={} "{}"', model.__name__, obj.pk, getattr(obj, show), code=code)
        if originals:
            raise RollingCommandError(count=len(originals))

        if self.options[u'verbosity'] >= u'1':
            msg = u'Imported model {}: {} created, {} changed, {} unchanged and {} deleted'
            msg = msg.format(model.__name__, created, changed, unchanged, deleted)
            self.stdout.write(msg)

    def import_hierarchy(self):
        for row in self.iterate_sheet(SHEETS.hierarchy):
            pass

    def import_tags(self):
        for row in self.iterate_sheet(SHEETS.tags):
            pass

    def import_obligees(self):
        for row, fields in self.import_model(SHEETS.obligees, Obligee, show=u'name', delete=False):
            fields[u'pk'] = row[COLUMNS.obligees.pk]
            fields[u'name'] = row[COLUMNS.obligees.name]
            fields[u'street'] = row[COLUMNS.obligees.street]
            fields[u'city'] = row[COLUMNS.obligees.city]
            fields[u'zip'] = row[COLUMNS.obligees.zip]
            fields[u'emails'] = row[COLUMNS.obligees.emails]
            fields[u'status'] = row[COLUMNS.obligees.status]

            # Dummy emails for local and dev server modes
            if hasattr(settings, u'OBLIGEE_DUMMY_MAIL'):
                fields[u'emails'] = Obligee.dummy_email(fields[u'name'], settings.OBLIGEE_DUMMY_MAIL)

    def import_aliases(self):
        for row in self.iterate_sheet(SHEETS.aliases):
            pass

    @transaction.atomic
    def handle(self):
        errors = 0

        if self.options[u'dry_run']:
            self.stdout.write(u'Importing: {} (dry run)'.format(self.filename))
        else:
            self.stdout.write(u'Importing: {}'.format(self.filename))

        # Reset obligees if requested
        if self.options[u'force'] and not self.options[u'reset']:
            raise CommandError(u'Option --force may be used with --reset only')
        if self.options[u'reset']:
            if Inforequest.objects.exists() and not self.options[u'force']:
                raise CommandError(squeeze(u"""
                        Existing inforequests prevented us from discarting current obligees. Use
                        --force to discard inforequests as well.
                        """))
            self.reset_model(Obligee)
            self.reset_model(HistoricalObligee)
            self.reset_model(Inforequest)

        try:
            self.wb = load_workbook(self.filename, read_only=True)
        except Exception as e:
            raise CommandError(u'Could not read input file: {}'.format(e))

        try:
            self.validate_structure()
        except RollingCommandError as e:
            errors += e.count

        try:
            self.import_hierarchy()
        except RollingCommandError as e:
            errors += e.count

        try:
            self.import_tags()
        except RollingCommandError as e:
            errors += e.count

        try:
            self.import_obligees()
        except RollingCommandError as e:
            errors += e.count

        try:
            self.import_aliases()
        except RollingCommandError as e:
            errors += e.count

        if errors:
            raise RollingCommandError(errors)
        elif self.options[u'dry_run']:
            self.stdout.write(u'Rollbacked (dry run)')
            raise RollbackDryRun
        else:
            self.stdout.write(u'Done.')

class Command(BaseCommand):
    help = u'Loads .xlsx file with obligees'
    args = u'file'
    option_list = BaseCommand.option_list + (
        make_option(u'--dry-run', action=u'store_true', dest=u'dry_run', default=False,
            help=squeeze(u"""
                Just show if the file would be imported correctly. Rollback the database at the
                end.
                """)),
        make_option(u'--reset', action=u'store_true', dest=u'reset', default=False,
            help=squeeze(u"""
                Discard current obligees before imporing the file. The command will fail if there
                are any inforequests in the database because removing obligees would break them.
                Use --force to discard inforequests as well.
                """)),
        make_option(u'--force', action=u'store_true', dest=u'force', default=False,
            help=squeeze(u"""
                If used together with --reset, discard current obligees even if there are
                inforequests in the database. The inforequests will be discarted as well.
                """)),
        )

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError(u'Expecting exactly one argument')

        try:
            importer = Importer(args[0], options, self.stdout)
            importer.handle()
        except RollbackDryRun:
            pass
