# vim: expandtab
# -*- coding: utf-8 -*-
import traceback

from django.db import transaction
from django.conf import settings

from poleno.cron import cron_job, cron_logger
from poleno.workdays import workdays
from poleno.utils.translation import translation
from poleno.utils.date import local_date, local_today
from poleno.utils.misc import nop

from .models import Inforequest, Branch, Action

@cron_job(run_at_times=settings.CRON_USER_INTERACTION_TIMES)
@transaction.atomic
def undecided_email_reminder():
    with translation(settings.LANGUAGE_CODE):
        inforequests = (Inforequest.objects
                .not_closed()
                .with_undecided_email()
                .prefetch_related(Inforequest.prefetch_newest_undecided_email())
                )

        filtered = []
        for inforequest in inforequests:
            try:
                email = inforequest.newest_undecided_email
                last = inforequest.last_undecided_email_reminder
                if last and last > email.processed:
                    continue
                days = workdays.between(local_date(email.processed), local_today())
                if days < 5:
                    continue
                filtered.append(inforequest)
            except Exception:
                msg = u'Checking if undecided email reminder should be sent failed: %r\n%s'
                cron_logger.error(msg % (inforequest, traceback.format_exc()))

        if not filtered:
            return

        filtered = (Inforequest.objects
                .select_related(u'applicant')
                .select_undecided_emails_count()
                .prefetch_related(Inforequest.prefetch_main_branch(None,
                    Branch.objects.select_related(u'historicalobligee')))
                .prefetch_related(Inforequest.prefetch_newest_undecided_email())
                .filter(pk__in=(o.pk for o in filtered))
                )
        for inforequest in filtered:
            try:
                with transaction.atomic():
                    inforequest.send_undecided_email_reminder()
                    cron_logger.info(u'Sent undecided email reminder: %r' % inforequest)
            except Exception:
                msg = u'Sending undecided email reminder failed: %r\n%s'
                cron_logger.error(msg % (inforequest, traceback.format_exc()))

@cron_job(run_at_times=settings.CRON_USER_INTERACTION_TIMES)
@transaction.atomic
def obligee_deadline_reminder():
    with translation(settings.LANGUAGE_CODE):
        inforequests = (Inforequest.objects
                .not_closed()
                .without_undecided_email()
                .prefetch_related(Inforequest.prefetch_branches())
                .prefetch_related(Branch.prefetch_last_action(u'branches'))
                )

        filtered = []
        for inforequest in inforequests:
            for branch in inforequest.branches:
                action = branch.last_action
                try:
                    if not action.has_obligee_extended_deadline_missed:
                        continue
                    # The last reminder was sent after the deadline was extended for the last time
                    # iff the extended deadline was missed before the reminder was sent. We don't
                    # want to send any more reminders if the last reminder was sent after the
                    # deadline was extended for the last time.
                    last = action.last_deadline_reminder
                    last_date = local_date(last) if last else None
                    if last and action.deadline.is_extended_deadline_missed_at(last_date):
                        continue
                    filtered.append(branch)
                except Exception:
                    msg = u'Checking if obligee deadline reminder should be sent failed: %r\n%s'
                    cron_logger.error(msg % (action, traceback.format_exc()))

        if not filtered:
            return

        filtered = (Branch.objects
                .select_related(u'inforequest__applicant')
                .select_related(u'historicalobligee')
                .prefetch_related(Branch.prefetch_last_action())
                .filter(pk__in=(o.pk for o in filtered))
                )
        for branch in filtered:
            try:
                with transaction.atomic():
                    branch.inforequest.send_obligee_deadline_reminder(branch.last_action)
                    cron_logger.info(u'Sent obligee deadline reminder: %r' % branch.last_action)
            except Exception:
                msg = u'Sending obligee deadline reminder failed: %r\n%s'
                cron_logger.error(msg % (branch.last_action, traceback.format_exc()))

@cron_job(run_at_times=settings.CRON_USER_INTERACTION_TIMES)
@transaction.atomic
def applicant_deadline_reminder():
    with translation(settings.LANGUAGE_CODE):
        inforequests = (Inforequest.objects
                .not_closed()
                .without_undecided_email()
                .prefetch_related(Inforequest.prefetch_branches())
                .prefetch_related(Branch.prefetch_last_action(u'branches'))
                )

        filtered = []
        for inforequest in inforequests:
            for branch in inforequest.branches:
                action = branch.last_action
                try:
                    if not action.has_applicant_deadline:
                        continue
                    # The reminder is sent 2 CD before the deadline is missed.
                    if action.deadline.calendar_days_remaining > 2:
                        continue
                    # Applicant deadlines may not be extended, so we send at most one applicant
                    # deadline reminder for the action.
                    if action.last_deadline_reminder:
                        continue
                    filtered.append(branch)
                except Exception:
                    msg = u'Checking if applicant deadline reminder should be sent failed: %r\n%s'
                    cron_logger.error(msg % (action, traceback.format_exc()))

        if not filtered:
            return

        filtered = (Branch.objects
                .select_related(u'inforequest__applicant')
                .prefetch_related(Branch.prefetch_last_action())
                .filter(pk__in=(o.pk for o in filtered))
                )
        for branch in filtered:
            try:
                with transaction.atomic():
                    branch.inforequest.send_applicant_deadline_reminder(branch.last_action)
                    cron_logger.info(u'Sent applicant deadline reminder: %r' % branch.last_action)
            except Exception:
                msg = u'Sending applicant deadline reminder failed: %r\n%s'
                cron_logger.error(msg % (branch.last_action, traceback.format_exc()))

@cron_job(run_at_times=settings.CRON_IMPORTANT_MAINTENANCE_TIMES)
@transaction.atomic
def close_inforequests():
    inforequests = (Inforequest.objects
            .not_closed()
            .prefetch_related(Inforequest.prefetch_branches())
            .prefetch_related(Branch.prefetch_last_action(u'branches'))
            )

    filtered = []
    for inforequest in inforequests:
        try:
            for branch in inforequest.branches:
                action = branch.last_action
                if action.deadline and action.deadline.extended_calendar_days_behind < 100:
                    break
            else:
                # Every branch that has a deadline have been missed for at least 100 WD.
                filtered.append(inforequest)
        except Exception:
            msg = u'Checking if inforequest should be closed failed: %r\n%s'
            cron_logger.error(msg % (inforequest, traceback.format_exc()))

    for inforequest in filtered:
        try:
            with transaction.atomic():
                for branch in inforequest.branches:
                    branch.add_expiration_if_expired()
                inforequest.closed = True
                inforequest.save(update_fields=[u'closed'])
                cron_logger.info(u'Closed inforequest: %r' % inforequest)
        except Exception:
            msg = u'Closing inforequest failed: %r\n%s'
            cron_logger.error(msg % (inforequest, traceback.format_exc()))

@cron_job(run_at_times=settings.CRON_IMPORTANT_MAINTENANCE_TIMES)
@transaction.atomic
def add_expirations():
    inforequests = (Inforequest.objects
            .not_closed()
            .without_undecided_email()
            .prefetch_related(Inforequest.prefetch_branches())
            .prefetch_related(Branch.prefetch_last_action(u'branches'))
            )

    filtered = []
    for inforequest in inforequests:
        for branch in inforequest.branches:
            try:
                action = branch.last_action
                if not action.has_obligee_extended_deadline_missed:
                    continue
                if action.deadline.calendar_days_behind <= 8:
                    continue
                # The last action obligee deadline was missed more than 8 calendar days ago. The
                # applicant may extend the obligee deadline by 8 calendar days at most. So it's
                # safe to add expiration now. The expiration action has 15 calendar days deadline
                # of which about half is still left.
                filtered.append(branch)
            except Exception:
                msg = u'Checking if expiration action should be added failed: %r\n%s'
                cron_logger.error(msg % (branch, traceback.format_exc()))

    for branch in filtered:
        try:
            with transaction.atomic():
                branch.add_expiration_if_expired()
                cron_logger.info(u'Added expiration action: %r' % branch)
        except Exception:
            msg = u'Adding expiration action failed: %r\n%s'
            cron_logger.error(msg % (branch, traceback.format_exc()))
