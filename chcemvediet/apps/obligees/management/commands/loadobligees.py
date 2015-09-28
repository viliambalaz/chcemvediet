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

from poleno.utils.forms import validate_comma_separated_emails
from poleno.utils.misc import Bunch
from chcemvediet.apps.obligees.models import Obligee

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
        SHEETS.obligees: {
            COLUMNS.obligees.pk:                   dict(typ=int,     min_value=1), # FIXME: unique pk
            COLUMNS.obligees.official_name:        dict(typ=unicode, nonempty=True),
            COLUMNS.obligees.name:                 dict(typ=unicode, nonempty=True), # FIXME: unique slug
            COLUMNS.obligees.name_genitive:        dict(typ=unicode, nonempty=True),
            COLUMNS.obligees.name_dative:          dict(typ=unicode, nonempty=True),
            COLUMNS.obligees.name_accusative:      dict(typ=unicode, nonempty=True),
            COLUMNS.obligees.name_locative:        dict(typ=unicode, nonempty=True),
            COLUMNS.obligees.name_instrumental:    dict(typ=unicode, nonempty=True),
            COLUMNS.obligees.name_gender:          dict(typ=unicode, choices=[u'muzsky', u'zensky', u'stredny', u'pomnozny']),
            COLUMNS.obligees.ico:                  dict(typ=unicode, default=u''),
            COLUMNS.obligees.hierarchy:            dict(typ=unicode, regex=hierarchies_regex_1), # FIXME: foreign key
            COLUMNS.obligees.street:               dict(typ=unicode, nonempty=True),
            COLUMNS.obligees.city:                 dict(typ=unicode, nonempty=True),
            COLUMNS.obligees.zip:                  dict(typ=unicode, regex=zip_regex),
            COLUMNS.obligees.emails:               dict(typ=unicode, default=u'', validators=validate_comma_separated_emails),
            COLUMNS.obligees.official_description: dict(typ=unicode, default=u''),
            COLUMNS.obligees.simple_description:   dict(typ=unicode, default=u''),
            COLUMNS.obligees.status:               dict(typ=unicode, choices={u'aktivny': Obligee.STATUSES.PENDING, u'neaktivny': Obligee.STATUSES.DISSOLVED}),
            COLUMNS.obligees.type:                 dict(typ=int,     choices=[1, 2, 3, 4]),
            COLUMNS.obligees.latitude:             dict(typ=float,   min_value=-90.0, max_value=90.0),
            COLUMNS.obligees.longitude:            dict(typ=float,   min_value=-180.0, max_value=180.0),
            COLUMNS.obligees.iczsj:                dict(typ=int,     min_value=1), # FIXME: foreign key
            COLUMNS.obligees.tags:                 dict(typ=unicode, default=u'', regex=tags_regex_0), # FIXME: foreign key
            COLUMNS.obligees.notes:                dict(typ=unicode, default=u''),
            },
        SHEETS.hierarchy: {
            COLUMNS.hierarchy.pk:                  dict(typ=int,     min_value=1), # FIXME: unique pk
            COLUMNS.hierarchy.key:                 dict(typ=unicode, regex=hierarchy_regex), # FIXME: unique slug
            COLUMNS.hierarchy.name:                dict(typ=unicode, nonempty=True),
            COLUMNS.hierarchy.description:         dict(typ=unicode, default=u''),
            },
        SHEETS.aliases: {
            COLUMNS.aliases.pk:                    dict(typ=int,     min_value=1), # FIXME: unique pk
            COLUMNS.aliases.obligee_pk:            dict(typ=int,     min_value=1), # FIXME: foreign key
            COLUMNS.aliases.obligee_name:          dict(typ=unicode, nonempty=True), # FIXME: overit vzhladom na ID institucie
            COLUMNS.aliases.alias:                 dict(typ=unicode, nonempty=True), # FIXME: unique slug
            COLUMNS.aliases.description:           dict(typ=unicode, default=u''),
            COLUMNS.aliases.notes:                 dict(typ=unicode, default=u''),
            },
        SHEETS.tags: {
            COLUMNS.tags.pk:                       dict(typ=int,     min_value=1), # FIXME: unique pk
            COLUMNS.tags.key:                      dict(typ=unicode, regex=tag_regex), # FIXME: unique slug
            COLUMNS.tags.name:                     dict(typ=unicode, nonempty=True),
            },
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
        self.verbosity = options[u'verbosity']
        self.dry_run = options[u'dry_run']
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

        if self.verbosity == u'1':
            if code:
                self._error_cache[code] += 1
                if self._error_cache[code] == 1:
                    self.print_error(msg, args, kwargs)
                elif self._error_cache[code] == 2:
                    self.print_error(msg, args, kwargs, u'skipping further similar errors')
            else:
                self.print_error(msg, args, kwargs)

        elif self.verbosity >= u'2':
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

    def apply_default(self, value, idx, sheet, column):
        try:
            default = STRUCTURE[sheet][column][u'default']
        except KeyError:
            return value
        if value is None:
            value = default
        return value

    def validate_type(self, value, idx, sheet, column):
        try:
            typ = STRUCTURE[sheet][column][u'typ']
        except KeyError:
            return value
        if not isinstance(typ, tuple):
            typ = (typ,)
        if not isinstance(value, typ):
            exp = u', '.join(t.__name__ for t in typ)
            msg = u'Expecting {} but found {}'.format(exp, value.__class__.__name__)
            self.cell_error(u'type', idx, sheet, column, msg)
        return value

    def validate_min_value(self, value, idx, sheet, column):
        try:
            min_value = STRUCTURE[sheet][column][u'min_value']
        except KeyError:
            return value
        if value < min_value:
            msg = u'Expecting value not smaller than "{}" but found "{}"'.format(min_value, value)
            self.cell_error(u'min_value', idx, sheet, column, msg)
        return value

    def validate_max_value(self, value, idx, sheet, column):
        try:
            max_value = STRUCTURE[sheet][column][u'max_value']
        except KeyError:
            return value
        if value > max_value:
            msg = u'Expecting value not bigger than "{}" but found "{}"'.format(max_value, value)
            self.cell_error(u'max_value', idx, sheet, column, msg)
        return value

    def validate_nonempty(self, value, idx, sheet, column):
        try:
            nonempty = STRUCTURE[sheet][column][u'nonempty']
        except KeyError:
            return value
        if nonempty and not value:
            msg = u'Expecting nonempty value but found "{}"'.format(value)
            self.cell_error(u'nonempty', idx, sheet, column, msg)
        return value

    def validate_choices(self, value, idx, sheet, column):
        try:
            choices = STRUCTURE[sheet][column][u'choices']
        except KeyError:
            return value
        if value not in choices:
            exp = u', '.join(u'"{}"'.format(c) for c in choices)
            msg = u'Expecting one of {} but found "{}"'.format(exp, value)
            self.cell_error(u'choices', idx, sheet, column, msg)
        if isinstance(choices, dict):
            value = choices[value]
        return value

    def validate_regex(self, value, idx, sheet, column):
        try:
            regex = STRUCTURE[sheet][column][u'regex']
        except KeyError:
            return value
        if not regex.match(value):
            msg = u'Expecting value matching "{}" but found "{}"'.format(regex.pattern, value)
            self.cell_error(u'regex', idx, sheet, column, msg)
        return value

    def validate_validators(self, value, idx, sheet, column):
        try:
            validators = STRUCTURE[sheet][column][u'validators']
        except KeyError:
            return value
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

    def validate_cell(self, idx, row, sheet, column):
        try:
            col_idx = self.columns[sheet][column]
        except KeyError:
            self.cell_error(u'missing', idx, sheet, column, u'Missing column')

        try:
            value = row[col_idx].value
        except IndexError:
            value = None

        value = self.apply_default(value, idx, sheet, column)
        value = self.validate_type(value, idx, sheet, column)
        value = self.validate_min_value(value, idx, sheet, column)
        value = self.validate_max_value(value, idx, sheet, column)
        value = self.validate_nonempty(value, idx, sheet, column)
        value = self.validate_choices(value, idx, sheet, column)
        value = self.validate_regex(value, idx, sheet, column)
        value = self.validate_validators(value, idx, sheet, column)
        return value

    def validate_row(self, idx, row, sheet):
        res = {}
        errors = 0
        for column in STRUCTURE[sheet]:
            try:
                res[column] = self.validate_cell(idx, row, sheet, column)
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
        elif self.verbosity >= u'1':
            self.stdout.write(u'Imported sheet: {} ({} entries)'.format(sheet, count))

    def import_hierarchy(self):
        for row in self.iterate_sheet(SHEETS.hierarchy):
            pass

    def import_tags(self):
        for row in self.iterate_sheet(SHEETS.tags):
            pass

    def import_obligees(self):
        Obligee.objects.all().delete()
        for row in self.iterate_sheet(SHEETS.obligees):
            obligee = Obligee(
                    pk=row[COLUMNS.obligees.pk],
                    name=row[COLUMNS.obligees.name],
                    street=row[COLUMNS.obligees.street],
                    city=row[COLUMNS.obligees.city],
                    zip=row[COLUMNS.obligees.zip],
                    emails=row[COLUMNS.obligees.emails],
                    status=row[COLUMNS.obligees.status],
                    )
            obligee.save()

    def import_aliases(self):
        for row in self.iterate_sheet(SHEETS.aliases):
            pass

    @transaction.atomic
    def handle(self):
        errors = 0

        try:
            self.wb = load_workbook(self.filename, read_only=True)
            if self.dry_run:
                self.stdout.write(u'Importing: {} (dry run)'.format(self.filename))
            else:
                self.stdout.write(u'Importing: {}'.format(self.filename))
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
            self.import_aliases()
        except RollingCommandError as e:
            errors += e.count

        try:
            self.import_obligees()
        except RollingCommandError as e:
            errors += e.count

        if errors:
            raise RollingCommandError(errors)
        elif self.dry_run:
            self.stdout.write(u'Rollbacked (dry run)')
            raise RollbackDryRun
        else:
            self.stdout.write(u'Done.')

class Command(BaseCommand):
    help = u'Loads .xlsx file with obligees'
    args = u'file'
    option_list = BaseCommand.option_list + (
        make_option(u'--dry-run', action=u'store_true', dest=u'dry_run', default=False,
            help=u'Just show if the file would be imported correctly. Rollback at the end.'),
        )

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError(u'Expecting exactly one argument')

        try:
            importer = Importer(args[0], options, self.stdout)
            importer.handle()
        except RollbackDryRun:
            pass
