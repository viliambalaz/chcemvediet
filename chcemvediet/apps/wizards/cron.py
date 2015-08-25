# vim: expandtab
# -*- coding: utf-8 -*-
import datetime

from django.db import transaction
from django.conf import settings

from poleno.cron import cron_job
from poleno.utils.date import utc_now

from .models import WizardDraft

@cron_job(run_at_times=settings.CRON_UNIMPORTANT_MAINTENANCE_TIMES)
@transaction.atomic
def delete_old_drafts():
    threshold = utc_now() - datetime.timedelta(days=15)
    WizardDraft.objects.filter(modified__lt=threshold).delete()
