# vim: expandtab
# -*- coding: utf-8 -*-
import datetime

from django.utils.functional import cached_property

from poleno.workdays import workdays
from poleno.utils.date import local_today
from poleno.utils.misc import Bunch

class Deadline(object):

    TYPES = Bunch(
            OBLIGEE_DEADLINE = 1,
            APPLICANT_DEADLINE = 2,
            )

    UNITS = Bunch(
            CALENDAR_DAYS = 1,
            WORKDAYS = 2,
            )

    def __init__(self, type, base_date, value, unit, applicant_extension):
        self.type = type
        self.base_date = base_date
        self.value = value
        self.unit = unit
        self.applicant_extension = applicant_extension or 0
        self._today = local_today()

    @property
    def is_obligee_deadline(self):
        return self.type == self.TYPES.OBLIGEE_DEADLINE

    @property
    def is_applicant_deadline(self):
        return self.type == self.TYPES.APPLICANT_DEADLINE

    @property
    def is_in_calendar_days(self):
        return self.unit == self.UNITS.CALENDAR_DAYS

    @property
    def is_in_workdays(self):
        return self.unit == self.UNITS.WORKDAYS

    @cached_property
    def deadline_date(self):
        if self.is_in_calendar_days:
            return self.base_date + datetime.timedelta(days=self.value)
        else:
            return workdays.advance(self.base_date, self.value)

    @cached_property
    def extended_deadline_date(self):
        # Applicant extension is always in calendar days
        return self.deadline_date + datetime.timedelta(days=self.applicant_extension)

    @cached_property
    def calendar_days_passed(self):
        return self.calendar_days_passed_at(self._today)

    @cached_property
    def workdays_passed(self):
        return self.workdays_passed(self._today)

    @cached_property
    def calendar_days_remaining(self):
        return self.calendar_days_remaining_at(self._today)

    @cached_property
    def workdays_remaining(self):
        return self.workdays_remaining_at(self._today)

    @cached_property
    def extended_calendar_days_remaining(self):
        return self.extended_calendar_days_remaining_at(self._today)

    @cached_property
    def extended_workdays_remaining(self):
        return self.extended_workdays_remaining_at(self._today)

    @cached_property
    def is_deadline_missed(self):
        return self.is_deadline_missed_at(self._today)

    @cached_property
    def is_extended_deadline_missed(self):
        return self.is_extended_deadline_missed_at(self._today)

    def calendar_days_passed_at(self, at):
        return (at - self.base_date).days

    def workdays_passed_at(self, at):
        return workdays.between(self.base_date, at)

    def calendar_days_remaining_at(self, at):
        return (self.deadline_date - at).days

    def workdays_remaining_at(self, at):
        return workdays.between(at, self.deadline_date)

    def extended_calendar_days_remaining_at(self, at):
        return (self.extended_deadline_date - at).days

    def extended_workdays_remaining_at(self, at):
        return workdays.between(at, self.extended_deadline_date)

    def is_deadline_missed_at(self, at):
        return self.deadline_date < at

    def is_extended_deadline_missed_at(self, at):
        return self.extended_deadline_date < at

    def __unicode__(self):
        return u'<Deadline: {} {} for {} since {}{}>'.format(
                self.value,
                u'CD' if self.is_in_calendar_days else u'WD',
                u'Applicant' if self.is_obligee_deadline else u'Obligee',
                self.base_date,
                u' +{0} CD'.format(self.applicant_extension) if self.applicant_extension else u'',
                )
