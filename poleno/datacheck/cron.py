# vim: expandtab
# -*- coding: utf-8 -*-
from django.conf import settings

from poleno.cron import cron_job, cron_logger

from .datacheck import registry


@cron_job(run_at_times=settings.CRON_UNIMPORTANT_MAINTENANCE_TIMES)
def datacheck():
    issues = registry.run_checks(superficial=True)
    for issue in issues:
        cron_logger.log(issue.level, issue)
    cron_logger.info(u'Data check identified {} issues.'.format(len(issues)))
