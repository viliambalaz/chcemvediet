# vim: expandtab
# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User

from poleno.utils.misc import FormatMixin


class Profile(FormatMixin, models.Model):
    user = models.OneToOneField(User)
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    zip = models.CharField(max_length=10)

    # Backward relations added to other models:
    #
    #  -- User.profile
    #     Should NOT raise DoesNotExist

    # Indexes:
    #  -- user: OneToOneField

    def __unicode__(self):
        return format(self.pk)
