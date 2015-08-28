# vim: expandtab
# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from jsonfield import JSONField

from poleno.utils.models import QuerySet

class WizardDraftQuerySet(QuerySet):
    def owned_by(self, user):
        return self.filter(owner=user)

class WizardDraft(models.Model):
    # Primary key (Wizard.instance_id)
    id = models.CharField(max_length=255, primary_key=True)

    # May NOT be NULL
    owner = models.ForeignKey(User)

    # May be empty
    step = models.CharField(blank=True, max_length=255)

    # May NOT be empty
    data = JSONField()

    # May NOT be NULL; Automatically updated on every save
    modified = models.DateTimeField(auto_now=True)

    # May be empty; Backward generic relation
    attachment_set = generic.GenericRelation(u'attachments.Attachment', content_type_field=u'generic_type', object_id_field=u'generic_id')

    objects = WizardDraftQuerySet.as_manager()

    class Meta:
        index_together = [
                # [u'id'] -- Primary key defines unique index by default
                # [u'owner'] -- ForeignKey defines index by default
                ]
