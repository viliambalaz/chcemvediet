# vim: expandtab
# -*- coding: utf-8 -*-
from poleno.datasheets import Book, LoadSheetsCommand
from chcemvediet.apps.geounits.datasheets import RegionSheet, DistrictSheet, MunicipalitySheet
from chcemvediet.apps.geounits.datasheets import NeighbourhoodSheet
from chcemvediet.apps.obligees.datasheets import ObligeeTagSheet, ObligeeGroupSheet, ObligeeSheet
from chcemvediet.apps.obligees.datasheets import ObligeeAliasSheet


class DataBook(Book):
    sheets = [
            RegionSheet,
            DistrictSheet,
            MunicipalitySheet,
            NeighbourhoodSheet,
            ObligeeTagSheet,
            ObligeeGroupSheet,
            ObligeeSheet,
            ObligeeAliasSheet,
            ]

class Command(LoadSheetsCommand):
    book = DataBook
