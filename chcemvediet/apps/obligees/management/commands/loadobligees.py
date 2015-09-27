# vim: expandtab
# -*- coding: utf-8 -*-
import re
from openpyxl import load_workbook

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from chcemvediet.apps.obligees.models import Obligee

zip_regex = re.compile(r'^\d\d\d \d\d$')
tag_regex = re.compile(r'^[\w-]+$')
tags_regex = re.compile(r'^([\w-]+(\s+[\w-]+)*)?$') # 0 or more tags
hierarchy_regex = re.compile(r'^[\w-]+(/[\w-]+)*$')
hierarchies_regex = re.compile(r'^[\w-]+(/[\w-]+)*(\s+[\w-]+(/[\w-]+)*)*$') # 1 or more hierarchies

STRUCTURE = { # {{{
        u'Obligees': {
            u'Interne ID institucie':          dict(typ=int,     min_value=1), # FIXME: unique pk
            u'Oficialny nazov':                dict(typ=unicode, nonempty=True),
            u'Rozlisovaci nazov nominativ':    dict(typ=unicode, nonempty=True), # FIXME: unique slug
            u'Rozlisovaci nazov genitiv':      dict(typ=unicode, nonempty=True),
            u'Rozlisovaci nazov dativ':        dict(typ=unicode, nonempty=True),
            u'Rozlisovaci nazov akuzativ':     dict(typ=unicode, nonempty=True),
            u'Rozlisovaci nazov lokal':        dict(typ=unicode, nonempty=True),
            u'Rozlisovaci nazov instrumental': dict(typ=unicode, nonempty=True),
            u'Rod':                            dict(typ=unicode, choices=[u'muzsky', u'zensky', u'stredny', u'pomnozny']),
            u'ICO':                            dict(typ=unicode, default=u''),
            u'Hierarchia':                     dict(typ=unicode, regex=hierarchies_regex), # FIXME: foreign key
            u'Adresa: Ulica s cislom':         dict(typ=unicode, nonempty=True),
            u'Adresa: Obec':                   dict(typ=unicode, nonempty=True),
            u'Adresa: PSC':                    dict(typ=unicode, regex=zip_regex),
            u'Adresa: Email':                  dict(typ=unicode, default=u''), # FIXME: coerce=parse_emails
            u'Oficialny popis':                dict(typ=unicode, default=u''),
            u'Zrozumitelny popis':             dict(typ=unicode, default=u''),
            u'Stav':                           dict(typ=unicode, choices={u'aktivny': Obligee.STATUSES.PENDING, u'neaktivny': Obligee.STATUSES.DISSOLVED}),
            u'Typ':                            dict(typ=int,     choices=[1, 2, 3, 4]),
            u'Lat':                            dict(typ=float,   min_value=-90.0, max_value=90.0),
            u'Lon':                            dict(typ=float,   min_value=-180.0, max_value=180.0),
            u'ICZSJ':                          dict(typ=int,     min_value=1), # FIXME: foreign key
            u'Tagy':                           dict(typ=unicode, default=u'', regex=tags_regex), # FIXME: foreign key
            u'Poznamka':                       dict(typ=unicode, default=u''),
            },
        u'Hierarchia': {
            u'Interne ID hierarchie':          dict(typ=int,     min_value=1), # FIXME: unique pk
            u'Kod':                            dict(typ=unicode, regex=hierarchy_regex), # FIXME: unique slug
            u'Nazov v hierarchii':             dict(typ=unicode, nonempty=True),
            u'Popis':                          dict(typ=unicode, default=u''),
            },
        u'Aliasy': {
            u'Interne ID aliasu':              dict(typ=int,     min_value=1), # FIXME: unique pk
            u'ID institucie':                  dict(typ=int,     min_value=1), # FIXME: foreign key
            u'Rozlisovaci nazov institucie':   dict(typ=unicode, nonempty=True), # FIXME: overit vzhladom na ID institucie
            u'Alternativny nazov':             dict(typ=unicode, nonempty=True), # FIXME: unique slug
            u'Vysvetlenie':                    dict(typ=unicode, default=u''),
            u'Poznamka':                       dict(typ=unicode, default=u''),
            },
        u'Tagy': {
            u'Interne ID tagu':                dict(typ=int,     min_value=1), # FIXME: unique pk
            u'Kod':                            dict(typ=unicode, regex=tag_regex), # FIXME: unique slug
            u'Nazov':                          dict(typ=unicode, nonempty=True),
            },
        } # }}}

class MultipleCommandErrors(CommandError):
    def __init__(self, errors):
        msgs = []
        for error in errors:
            if isinstance(error, MultipleCommandErrors):
                msgs.append(u'%s' % error)
            else:
                msgs.append(u'\n -- %s' % error)
        super(CommandError, self).__init__(u''.join(msgs))

class Command(BaseCommand):
    help = u'Loads .xlsx file with obligees'
    args = u'file'

    def _load_file(self, filename):
        try:
            return load_workbook(filename, read_only=True)
        except Exception as e:
            raise CommandError(u'Could not read input file: {}'.format(e))

    def _get_columns(self, wb, sheet):
        try:
            row = next(wb[sheet].rows)
        except StopIteration:
            return {}
        res = {}
        for idx, column in enumerate(row):
            if column.value is not None and not column.value.startswith(u'#'):
                res[column.value] = idx
        return res

    def _validate_structure(self, wb):
        errors = []

        expected_sheets = set(STRUCTURE)
        found_sheets = {n for n in wb.get_sheet_names() if not n.startswith(u'#')}
        missing_sheets = expected_sheets - found_sheets
        superfluous_sheets = found_sheets - expected_sheets
        for sheet in missing_sheets:
            msg = u'The file does not contain required sheet: {}'.format(sheet)
            errors.append(CommandError(msg))
        for sheet in superfluous_sheets:
            msg = u'The file contains unexpected sheet: {}'.format(sheet)
            errors.append(CommandError(msg))

        self._columns = {}
        for sheet in expected_sheets & found_sheets:
            self._columns[sheet] = self._get_columns(wb, sheet)
            expected_columns = set(STRUCTURE[sheet])
            found_columns = set(self._columns[sheet])
            missing_columns = expected_columns - found_columns
            superfluous_columns = found_columns - expected_columns
            for column in missing_columns:
                msg = u'Sheet "{}" does not contain required column: {}'.format(sheet, column)
                errors.append(CommandError(msg))
            for column in superfluous_columns:
                msg = u'Sheet "{}" contains unexpected column: {}'.format(sheet, column)
                errors.append(CommandError(msg))

        if errors:
            raise MultipleCommandErrors(errors)

    def _cell_error(self, idx, sheet, column, msg):
        raise CommandError(u'Invalid value in row {} of "{}.{}": {}'.format(idx+1, sheet, column, msg))

    def _validate_type(self, value, idx, sheet, column):
        try:
            typ = STRUCTURE[sheet][column][u'typ']
        except KeyError:
            return value
        if not isinstance(typ, tuple):
            typ = (typ,)
        if not isinstance(value, typ):
            exp = u', '.join(t.__name__ for t in typ)
            msg = u'Expecting {} but found {}'.format(exp, value.__class__.__name__)
            self._cell_error(idx, sheet, column, msg)
        return value

    def _validate_min_value(self, value, idx, sheet, column):
        try:
            min_value = STRUCTURE[sheet][column][u'min_value']
        except KeyError:
            return value
        if value < min_value:
            msg = u'Expecting value not smaller than "{}" but found "{}"'.format(min_value, value)
            self._cell_error(idx, sheet, column, msg)
        return value

    def _validate_max_value(self, value, idx, sheet, column):
        try:
            max_value = STRUCTURE[sheet][column][u'max_value']
        except KeyError:
            return value
        if value > max_value:
            msg = u'Expecting value not bigger than "{}" but found "{}"'.format(max_value, value)
            self._cell_error(idx, sheet, column, msg)
        return value

    def _validate_nonempty(self, value, idx, sheet, column):
        try:
            nonempty = STRUCTURE[sheet][column][u'nonempty']
        except KeyError:
            return value
        if nonempty and not value:
            msg = u'Expecting nonempty value but found "{}"'.format(value)
            self._cell_error(idx, sheet, column, msg)
        return value

    def _validate_choices(self, value, idx, sheet, column):
        try:
            choices = STRUCTURE[sheet][column][u'choices']
        except KeyError:
            return value
        if value not in choices:
            exp = u', '.join(u'"{}"'.format(c) for c in choices)
            msg = u'Expecting one of {} but found "{}"'.format(exp, value)
            self._cell_error(idx, sheet, column, msg)
        if isinstance(choices, dict):
            value = choices[value]
        return value

    def _validate_regex(self, value, idx, sheet, column):
        try:
            regex = STRUCTURE[sheet][column][u'regex']
        except KeyError:
            return value
        if not regex.match(value):
            msg = u'Expecting value matching "{}" but found "{}"'.format(regex.pattern, value)
            self._cell_error(idx, sheet, column, msg)
        return value

    def _validate_cell(self, idx, row, sheet, column):
        try:
            value = row[self._columns[sheet][column]].value
        except IndexError:
            value = None
        if value is None:
            value = STRUCTURE[sheet][column].get(u'default', None)
        value = self._validate_type(value, idx, sheet, column)
        value = self._validate_min_value(value, idx, sheet, column)
        value = self._validate_max_value(value, idx, sheet, column)
        value = self._validate_nonempty(value, idx, sheet, column)
        value = self._validate_choices(value, idx, sheet, column)
        value = self._validate_regex(value, idx, sheet, column)
        return value

    def _validate_row(self, idx, row, sheet):
        res = {}
        errors = []
        for column in STRUCTURE[sheet]:
            try:
                res[column] = self._validate_cell(idx, row, sheet, column)
            except CommandError as e:
                errors.append(e)
        if errors:
            raise MultipleCommandErrors(errors)
        return res

    def _iterate_sheet(self, wb, sheet):
        errors = []
        ws = wb[sheet]
        for idx, row in enumerate(ws.rows):
            if idx == 0 or not row:
                continue
            try:
                yield self._validate_row(idx, row, sheet)
            except CommandError as e:
                errors.append(e)
        if errors:
            raise MultipleCommandErrors(errors)

    @transaction.atomic
    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError(u'Expecting exactly one argument')

        wb = self._load_file(args[0])
        self._validate_structure(wb)

        for row in self._iterate_sheet(wb, u'Hierarchia'):
            pass

        for row in self._iterate_sheet(wb, u'Aliasy'):
            pass

        for row in self._iterate_sheet(wb, u'Tagy'):
            pass

        Obligee.objects.all().delete()
        for row in self._iterate_sheet(wb, u'Obligees'):
            obligee = Obligee(
                    pk=row[u'Interne ID institucie'],
                    name=row[u'Rozlisovaci nazov nominativ'],
                    street=row[u'Adresa: Ulica s cislom'],
                    city=row[u'Adresa: Obec'],
                    zip=row[u'Adresa: PSC'],
                    emails=row[u'Adresa: Email'],
                    status=row[u'Stav'],
                    )
            obligee.save()

        self.stdout.write(u'Imported.')
