# vim: expandtab
# -*- coding: utf-8 -*-
from email.utils import formataddr

from django.core.urlresolvers import reverse
from django.core.mail import EmailMessage
from django.db import models, IntegrityError, transaction, connection
from django.db.models import Q, Prefetch
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.functional import cached_property
from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.sites.models import Site
from aggregate_if import Count
from jsonfield import JSONField

from poleno.attachments.models import Attachment
from poleno.mail.models import Message
from poleno.workdays import workdays
from poleno.utils.misc import Bunch, random_readable_string, squeeze
from poleno.utils.models import FieldChoices, QuerySet, join_lookup
from poleno.utils.mail import render_mail
from poleno.utils.date import utc_now, local_today
from chcemvediet.apps.obligees.models import Obligee

class InforequestDraftQuerySet(QuerySet):
    def owned_by(self, user):
        return self.filter(applicant=user)
    def order_by_pk(self):
        return self.order_by(u'pk')

class InforequestDraft(models.Model):
    # May NOT be NULL; For index see index_together
    applicant = models.ForeignKey(User, db_index=False,
            help_text=squeeze(u"""
                The draft owner, the future inforequest applicant.
                """))

    # May be NULL; For index see index_together
    obligee = models.ForeignKey(u'obligees.Obligee', blank=True, null=True, db_index=False,
            help_text=squeeze(u"""
                The obligee the inforequest will be sent to, if the user has already set it.
                """))

    # May be empty; Django migrations for MySQL backend are broken in ``default`` is mutable.
    subject = JSONField(blank=True, default=())
    content = JSONField(blank=True, default=())

    # May be empty
    attachment_set = generic.GenericRelation(u'attachments.Attachment', content_type_field=u'generic_type', object_id_field=u'generic_id')

    # Backward relations added to other models:
    #
    #  -- User.inforequestdraft_set
    #     May be empty
    #
    #  -- Obligee.inforequestdraft_set
    #     May be empty

    objects = InforequestDraftQuerySet.as_manager()

    class Meta:
        index_together = [
                [u'applicant'],
                [u'obligee'],
                ]

    @staticmethod
    def prefetch_attachments(path=None, queryset=None):
        u"""
        Use to prefetch ``InforequestDraft.attachments``
        """
        if queryset is None:
            queryset = Attachment.objects.get_queryset()
        queryset = queryset.order_by_pk()
        return Prefetch(join_lookup(path, u'attachment_set'), queryset, to_attr=u'attachments')

    @cached_property
    def attachments(self):
        u"""
        Cached list of all inforequest draft attachments ordered by ``pk``. May be prefetched with
        ``prefetch_related(InforequestDraft.prefetch_attachments())`` queryset method.
        """
        return list(self.attachment_set.order_by_pk())

    def __unicode__(self):
        return u'%s' % self.pk

class InforequestQuerySet(QuerySet):
    def owned_by(self, user):
        return self.filter(applicant=user)
    def closed(self):
        return self.filter(closed=True)
    def not_closed(self):
        return self.filter(closed=False)
    def with_undecided_email(self):
        return self.filter(inforequestemail__type=InforequestEmail.TYPES.UNDECIDED).distinct()
    def without_undecided_email(self):
        return self.exclude(inforequestemail__type=InforequestEmail.TYPES.UNDECIDED)
    def select_undecided_emails_count(self):
        u"""
        Use to select ``Inforequest.undecided_emails_count``. Redundant if
        ``prefetch_related(Inforequest.prefetch_undecided_emails())`` is already used.
        """
        return self.annotate(undecided_emails_count=Count(u'inforequestemail', only=Q(inforequestemail__type=InforequestEmail.TYPES.UNDECIDED)))
    def order_by_pk(self):
        return self.order_by(u'pk')
    def order_by_submission_date(self):
        return self.order_by(u'submission_date', u'pk')

class Inforequest(models.Model):
    # May NOT be NULL; For index see index_together
    applicant = models.ForeignKey(User, db_index=False,
            help_text=squeeze(u"""
                The inforequest owner, the user who submitted it.
                """))

    # May be empty; m2m through InforequestEmail
    email_set = models.ManyToManyField(u'mail.Message', through=u'InforequestEmail')

    # Should NOT be empty; Read-only; Frozen Applicant contact information at the time the
    # Inforequest was submitted, in case that the contact information changes in the future. The
    # information is automaticly frozen in save() when creating a new instance.
    applicant_name = models.CharField(max_length=255,
            help_text=squeeze(u"""
                Frozen applicant contact information for the case he changes it in the future. The
                information is frozen to its state at the moment the inforequest was
                submitted.
                """))
    applicant_street = models.CharField(max_length=255)
    applicant_city = models.CharField(max_length=255)
    applicant_zip = models.CharField(max_length=10)

    # May NOT be empty; Unique; Read-only; Automaticly computed in save() when creating a new
    # instance.
    unique_email = models.EmailField(max_length=255, unique=True,
            help_text=squeeze(u"""
                Unique email address used to identify which obligee email belongs to which
                inforequest. If the inforequest was advanced to other obligees, the same email
                address is used for communication with all such obligees, as there is no way to
                tell them to send their response to a different email address.
                """))

    # May NOT be NULL; Automaticly computed by Django when creating a new instance.
    submission_date = models.DateField(auto_now_add=True)

    # May NOT be NULL
    closed = models.BooleanField(default=False,
            help_text=squeeze(u"""
                True if the inforequest is closed and the applicant may not act on it any more.
                """))

    # May be NULL; Used by ``cron.undecided_email_reminder``
    last_undecided_email_reminder = models.DateTimeField(blank=True, null=True)

    # Backward relations:
    #
    #  -- branch_set: by Branch.inforequest
    #     May NOT be empty
    #
    #  -- actiondraft_set: by ActionDraft.inforequest
    #     May be empty; May contain at most one instance for every ActionDraft.TYPES
    #
    #  -- inforequestemail_set: by InforequestEmail.inforequest
    #     May be empty

    # Backward relations added to other models:
    #
    #  -- User.inforequest_set
    #     May be empty
    #
    #  -- Message.inforequest_set
    #     May be empty; Should NOT have more than one item

    objects = InforequestQuerySet.as_manager()

    class Meta:
        index_together = [
                [u'applicant'],
                [u'unique_email'],
                [u'submission_date', u'id'],
                ]

    @staticmethod
    def prefetch_branches(path=None, queryset=None):
        u"""
        Use to prefetch ``Inforequest.branches``
        """
        if queryset is None:
            queryset = Branch.objects.get_queryset()
        queryset = queryset.order_by_pk()
        return Prefetch(join_lookup(path, u'branch_set'), queryset, to_attr=u'branches')

    @cached_property
    def branches(self):
        u"""
        Cached list of all inforequest branches ordered by ``pk``. The list should not be empty.
        May be prefetched with ``prefetch_related(Inforequest.prefetch_branches())`` queryset
        method.
        """
        return list(self.branch_set.order_by_pk())

    @staticmethod
    def prefetch_main_branch(path=None, queryset=None):
        u"""
        Use to prefetch ``Inforequest.main_branch``. Redundant if ``prefetch_branches()`` is
        already used,
        """
        if queryset is None:
            queryset = Branch.objects.get_queryset()
        queryset = queryset.main()
        return Prefetch(join_lookup(path, u'branch_set'), queryset, to_attr=u'_main_branch')

    @cached_property
    def main_branch(self):
        u"""
        Cached inforequest main branch. The inforequest should have exactly one main branch. Raises
        Branch.DoesNotExist if the inforequest has no main branch and Branch.MultipleObjectsReturned
        if it has more than one main branch. May be prefetched with ``prefetch_related(Inforequest.prefetch_main_branch())``
        queryset method. Takes advantage of ``Inforequest.branches`` if it is already fetched.
        """
        if u'_main_branch' in self.__dict__:
            res = self._main_branch
        elif u'branches' in self.__dict__:
            res = list(b for b in self.branches if b.is_main)
        else:
            res = list(self.branch_set.main())

        if len(res) == 0:
            raise Branch.DoesNotExist(u'Inforequest has no main branch.')
        if len(res) > 1:
            raise Branch.MultipleObjectsReturned(u'Inforequest has more than one main branch.')
        return res[0]

    @property
    def undecided_emails_set(self):
        u"""
        Queryset of all undecided emails assigned to the inforequest.
        """
        return self.email_set.filter(inforequestemail__type=InforequestEmail.TYPES.UNDECIDED)

    @staticmethod
    def prefetch_undecided_emails(path=None, queryset=None):
        u"""
        Use to prefetch ``Inforequest.undecided_emails``.
        """
        if queryset is None:
            queryset = InforequestEmail.objects.get_queryset()
        queryset = queryset.filter(type=InforequestEmail.TYPES.UNDECIDED)
        queryset = queryset.order_by_email()
        queryset = queryset.select_related(u'email')
        return Prefetch(join_lookup(path, u'inforequestemail_set'), queryset, to_attr=u'_undecided_emails')

    @cached_property
    def undecided_emails(self):
        u"""
        Cached list of all undecided emails assigned to the inforequest ordered by ``processed``.
        May be prefetched with ``prefetch_related(Inforequest.prefetch_undecided_emails())``
        queryset method.
        """
        if u'_undecided_emails' in self.__dict__:
            return list(r.email for r in self._undecided_emails)
        else:
            return list(self.undecided_emails_set.order_by_processed())

    @cached_property
    def undecided_emails_count(self):
        u"""
        Cached number of undecided emails assigned to the inforequest. May be prefetched with
        ``select_undecided_emails_count()`` queryset method, Takes advantage of ``Inforequest.undecided_emails``
        if it is already fetched.
        """
        if u'undecided_emails' in self.__dict__:
            return len(self.undecided_emails)
        elif u'_undecided_emails' in self.__dict__:
            return len(self._undecided_emails)
        else:
            return self.undecided_emails_set.count()

    @cached_property
    def has_undecided_emails(self):
        u"""
        Cached flag if the inforequest has any undecided emails assigned. Takes advantage of
        ``Inforequest.undecided_emails_count`` or ``Inforequest.undecided_emails`` if either is
        already fetched.
        """
        if u'undecided_emails_count' in self.__dict__:
            return bool(self.undecided_emails_count)
        elif u'undecided_emails' in self.__dict__:
            return bool(self.undecided_emails)
        elif u'_undecided_emails' in self.__dict__:
            return bool(self._undecided_emails)
        else:
            return self.undecided_emails_set.exists()

    @cached_property
    def oldest_undecided_email(self):
        u"""
        Cached oldest undecided email assigned to the inforequest. Returns None if the inforequest
        has no undecided emails assigned. Takes advantage of ``Inforequest.undecided_emails`` if it
        is already fetched.
        """
        if u'undecided_emails' in self.__dict__:
            try:
                return self.undecided_emails[0]
            except IndexError:
                return None
        elif u'_undecided_emails' in self.__dict__:
            try:
                return self._undecided_emails[0].email
            except IndexError:
                return None
        else:
            return self.undecided_emails_set.order_by_processed().first()

    @staticmethod
    def prefetch_newest_undecided_email(path=None, queryset=None):
        u"""
        Use to prefetch ``Inforequest.newest_undecided_email``. Redundant if
        ``prefetch_undecided_emails()`` is already used.
        """
        if queryset is None:
            queryset = InforequestEmail.objects.get_queryset()
        quote_name = connection.ops.quote_name
        queryset = queryset.filter(type=InforequestEmail.TYPES.UNDECIDED)
        queryset = queryset.select_related(u'email')
        queryset = queryset.extra(where=[
            u'{through}.{through_pk} = ('
                u'SELECT p.{through_pk} '
                u'FROM {through} p '
                    u'INNER JOIN {message} m ON (m.{message_pk} = p.{through_email}) '
                u'WHERE p.{through_inforequest} = {through}.{through_inforequest} '
                u'ORDER BY m.{message_processed} DESC, m.{message_pk} DESC, p.{through_pk} DESC '
                u'LIMIT 1'
            u')'.format(
                through = quote_name(InforequestEmail._meta.db_table),
                through_pk = quote_name(InforequestEmail._meta.pk.column),
                through_inforequest = quote_name(InforequestEmail._meta.get_field(u'inforequest').column),
                through_email = quote_name(InforequestEmail._meta.get_field(u'email').column),
                message = quote_name(Message._meta.db_table),
                message_pk = quote_name(Message._meta.pk.column),
                message_processed = quote_name(Message._meta.get_field(u'processed').column),
                )
            ])
        return Prefetch(join_lookup(path, u'inforequestemail_set'), queryset, to_attr=u'_newest_undecided_email')

    @cached_property
    def newest_undecided_email(self):
        u"""
        Cached newest undecided email assigned to the inforequest. Returns None if the inforequest
        has no undecided emails assigned. Takes advantage of ``Inforequest.undecided_emails`` if it
        is already fetched.
        """
        if u'_newest_undecided_email' in self.__dict__:
            try:
                return self._newest_undecided_email[0].email
            except IndexError:
                return None
        elif u'undecided_emails' in self.__dict__:
            try:
                return self.undecided_emails[-1]
            except IndexError:
                return None
        elif u'_undecided_emails' in self.__dict__:
            try:
                return self._undecided_emails[-1].email
            except IndexError:
                return None
        else:
            return self.undecided_emails_set.order_by_processed().last()

    @cached_property
    def can_add_request(self):
        return self.can_add_action(Action.TYPES.REQUEST)

    @cached_property
    def can_add_clarification_response(self):
        return self.can_add_action(Action.TYPES.CLARIFICATION_RESPONSE)

    @cached_property
    def can_add_appeal(self):
        return self.can_add_action(Action.TYPES.APPEAL)

    @cached_property
    def can_add_confirmation(self):
        return self.can_add_action(Action.TYPES.CONFIRMATION)

    @cached_property
    def can_add_extension(self):
        return self.can_add_action(Action.TYPES.EXTENSION)

    @cached_property
    def can_add_advancement(self):
        return self.can_add_action(Action.TYPES.ADVANCEMENT)

    @cached_property
    def can_add_clarification_request(self):
        return self.can_add_action(Action.TYPES.CLARIFICATION_REQUEST)

    @cached_property
    def can_add_disclosure(self):
        return self.can_add_action(Action.TYPES.DISCLOSURE)

    @cached_property
    def can_add_refusal(self):
        return self.can_add_action(Action.TYPES.REFUSAL)

    @cached_property
    def can_add_affirmation(self):
        return self.can_add_action(Action.TYPES.AFFIRMATION)

    @cached_property
    def can_add_reversion(self):
        return self.can_add_action(Action.TYPES.REVERSION)

    @cached_property
    def can_add_remandment(self):
        return self.can_add_action(Action.TYPES.REMANDMENT)

    @cached_property
    def can_add_applicant_action(self):
        return self.can_add_action(*Action.APPLICANT_ACTION_TYPES)

    @cached_property
    def can_add_applicant_email_action(self):
        return self.can_add_action(*Action.APPLICANT_EMAIL_ACTION_TYPES)

    @cached_property
    def can_add_obligee_action(self):
        return self.can_add_action(*Action.OBLIGEE_ACTION_TYPES)

    @cached_property
    def can_add_obligee_email_action(self):
        return self.can_add_action(*Action.OBLIGEE_EMAIL_ACTION_TYPES)

    def can_add_action(self, *action_types):
        for branch in self.branches:
            if branch.can_add_action(*action_types):
                return True
        return False

    def branches_advanced_by(self, action):
        u"""
        Returns list of branches advanced by ``action``. Takes advantage of cached list of all
        inforequest branches stored in ``Inforequest.branches`` property.
        """
        return (b for b in self.branches if b.advanced_by_id == action.id)

    def branch_by_pk(self, pk):
        u"""
        Returns inforequest branch by its ``pk``. Takes advantage of cached list of all inforequest
        branches stored in ``Inforequest.branches`` property.
        """
        for branch in self.branches:
            if branch.pk == pk:
                return branch
        raise ValueError

    def save(self, *args, **kwargs):
        if self.pk is None: # Creating a new object

            # Freeze applicant contact information
            assert self.applicant_id is not None, u'%s.applicant is mandatory' % self.__class__.__name__
            assert self.applicant_name == u'', u'%s.applicant_name is read-only' % self.__class__.__name__
            assert self.applicant_street == u'', u'%s.applicant_street is read-only' % self.__class__.__name__
            assert self.applicant_city == u'', u'%s.applicant_city is read-only' % self.__class__.__name__
            assert self.applicant_zip == u'', u'%s.applicant_zip is read-only' % self.__class__.__name__
            self.applicant_name = self.applicant.get_full_name()
            self.applicant_street = self.applicant.profile.street
            self.applicant_city = self.applicant.profile.city
            self.applicant_zip = self.applicant.profile.zip

            # Generate unique random email
            assert self.unique_email == u'', u'%s.unique_email is read-only' % self.__class__.__name__
            length = 4
            while True:
                token = random_readable_string(length)
                self.unique_email = settings.INFOREQUEST_UNIQUE_EMAIL.format(token=token)
                try:
                    with transaction.atomic():
                        super(Inforequest, self).save(*args, **kwargs)
                except IntegrityError:
                    length += 1
                    if length <= 10:
                        continue
                    self.unique_email = None
                    raise # Give up
                return # object is already saved

        super(Inforequest, self).save(*args, **kwargs)

    def _send_notification(self, template, anchor, dictionary):
        site = Site.objects.get_current()
        url = u'http://{0}{1}#{2}'.format(site.domain, reverse(u'inforequests:detail', args=(self.pk,)), anchor)
        dictionary.update({
                u'inforequest': self,
                u'url': url,
                })
        msg = render_mail(template,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[self.applicant.email],
                dictionary=dictionary)
        msg.send()

    def send_received_email_notification(self, email):
        self._send_notification(u'inforequests/mails/received_email_notification', u'decide', {
                u'email': email,
                })

    def send_undecided_email_reminder(self):
        self._send_notification(u'inforequests/mails/undecided_email_reminder', u'decide', {
                })

        self.last_undecided_email_reminder = utc_now()
        self.save()

    def send_obligee_deadline_reminder(self, action):
        self._send_notification(u'inforequests/mails/obligee_deadline_reminder', u'action-%s' % action.pk, {
                u'action': action,
                })

        action.last_deadline_reminder = utc_now()
        action.save()

    def send_applicant_deadline_reminder(self, action):
        self._send_notification(u'inforequests/mails/applicant_deadline_reminder', u'action-%s' % action.pk, {
                u'action': action,
                })

        action.last_deadline_reminder = utc_now()
        action.save()

    def __unicode__(self):
        return u'%s' % self.pk

class InforequestEmailQuerySet(QuerySet):
    def undecided(self):
        return self.filter(type=InforequestEmail.TYPES.UNDECIDED)
    def order_by_pk(self):
        return self.order_by(u'pk')
    def order_by_email(self):
        return self.order_by(u'email__processed', u'email__pk', u'pk')
    def oldest(self):
        return self.order_by_email()[:1]
    def newest(self):
        return self.order_by_email().reverse()[:1]

class InforequestEmail(models.Model):
    # May NOT be NULL; m2m ends; For index see index_together
    inforequest = models.ForeignKey(u'Inforequest', db_index=False)
    email = models.ForeignKey(u'mail.Message', db_index=False)

    # May NOT be NULL
    TYPES = FieldChoices(
            # For outbound messages
            (u'APPLICANT_ACTION', 1, _(u'inforequests:InforequestEmail:type:APPLICANT_ACTION')),
            # For inbound messages
            (u'OBLIGEE_ACTION',   2, _(u'inforequests:InforequestEmail:type:OBLIGEE_ACTION')),
            (u'UNDECIDED',        3, _(u'inforequests:InforequestEmail:type:UNDECIDED')),
            (u'UNRELATED',        4, _(u'inforequests:InforequestEmail:type:UNRELATED')),
            (u'UNKNOWN',          5, _(u'inforequests:InforequestEmail:type:UNKNOWN')),
            )
    type = models.SmallIntegerField(choices=TYPES._choices,
            help_text=squeeze(u"""
                "Applicant Action": the email represents an applicant action;
                "Obligee Action": the email represents an obligee action;
                "Undecided": The email is waiting for applicant decision;
                "Unrelated": Marked as an unrelated email;
                "Unknown": Marked as an email the applicant didn't know how to decide.
                It must be "Applicant Action" for outbound mesages or one of the remaining values
                for inbound messages.
                """
                ))

    # Backward relations added to other models:
    #
    #  -- Inforequest.inforequestemail_set
    #
    #  -- Message.inforequestemail_set

    objects = InforequestEmailQuerySet.as_manager()

    class Meta:
        index_together = [
                [u'email', u'inforequest'],
                [u'inforequest', u'email'],
                [u'type', u'inforequest'],
                ]

    def __unicode__(self):
        return u'%s' % self.pk

class BranchQuerySet(QuerySet):
    def main(self):
        return self.filter(advanced_by__isnull=True)
    def advanced(self):
        return self.filter(advanced_by__isnull=False)
    def order_by_pk(self):
        return self.order_by(u'pk')

class Branch(models.Model):
    # May NOT be NULL; For index see index_together
    inforequest = models.ForeignKey(u'Inforequest', db_index=False)

    # May NOT be NULL; For index see index_together
    obligee = models.ForeignKey(u'obligees.Obligee', db_index=False,
            help_text=u'The obligee the inforequest was sent or advanced to.')

    # May NOT be NULL; Automaticly frozen in save() when creating a new object; For index see index_together
    historicalobligee = models.ForeignKey(u'obligees.HistoricalObligee', db_index=False,
            help_text=u'Frozen Obligee at the time the Inforequest was submitted or advanced to it.')

    # Advancement action that advanced the inforequest to this obligee; None if it's inforequest; For index see index_together
    # main branch. Inforequest must contain exactly one branch with ``advanced_by`` set to None.
    advanced_by = models.ForeignKey(u'Action', related_name=u'advanced_to_set', blank=True, null=True, db_index=False,
            help_text=squeeze(u"""
                NULL for main branches. The advancement action the inforequest was advanced by for
                advanced branches. Every Inforequest must contain exactly one main branch.
                """))

    # Backward relations:
    #
    #  -- action_set: by Action.branch
    #     May NOT be empty; The first action of every main branch must be REQUEST and the first
    #     action of every advanced branch ADVANCED_REQUEST.
    #
    #  -- actiondraft_set: by ActionDraft.branch
    #     May be empty

    # Backward relations added to other models:
    #
    #  -- Inforequest.branch_set
    #     Should NOT be empty
    #
    #  -- Obligee.branch_set
    #     May be empty
    #
    #  -- HistoricalObligee.branch_set
    #     May be empty
    #
    #  -- Action.advanced_to_set
    #     May be empty

    objects = BranchQuerySet.as_manager()

    class Meta:
        verbose_name_plural = u'Branches'
        index_together = [
                [u'inforequest', u'advanced_by'],
                [u'obligee'],
                [u'historicalobligee'],
                [u'advanced_by', u'inforequest'],
                ]

    @cached_property
    def is_main(self):
        return self.advanced_by_id is None

    @staticmethod
    def prefetch_actions(path=None, queryset=None):
        u"""
        Use to prefetch ``Branch.actions``.
        """
        if queryset is None:
            queryset = Action.objects.get_queryset()
        queryset = queryset.order_by_effective_date()
        return Prefetch(join_lookup(path, u'action_set'), queryset, to_attr=u'actions')

    @cached_property
    def actions(self):
        u"""
        Cached list of all branch actions ordered by ``effective_date``. The list should not be
        empty. May be prefetched with ``prefetch_related(Branch.prefetch_actions())`` queryset
        method.
        """
        return list(self.action_set.order_by_effective_date())

    @staticmethod
    def prefetch_actions_by_email(path=None, queryset=None):
        u"""
        Use to prefetch ``Branch.actions_by_email``.
        """
        if queryset is None:
            queryset = Action.objects.get_queryset()
        queryset = queryset.by_email()
        queryset = queryset.order_by_effective_date()
        return Prefetch(join_lookup(path, u'action_set'), queryset, to_attr=u'actions_by_email')

    @cached_property
    def actions_by_email(self):
        u"""
        Cached list of all branch actions sent by email ordered by ``effective_date``. May be
        prefetched with ``prefetch_related(Branch.prefetch_actions_by_email())`` queryset method.
        Takes advantage of ``Branch.actions`` if it is fetched already.
        """
        if u'actions' in self.__dict__:
            return list(a for a in self.actions if a.is_by_email)
        else:
            return list(self.action_set.by_email().order_by_effective_date())

    @staticmethod
    def prefetch_last_action(path=None, queryset=None):
        u"""
        Use to prefetch ``Branch.last_action``. Redundant if ``prefetch_actions()`` is already
        used.
        """
        if queryset is None:
            queryset = Action.objects.get_queryset()
        quote_name = connection.ops.quote_name
        queryset = queryset.extra(where=[
            u'{action}.{pk} = ('
                u'SELECT p.{pk} '
                u'FROM {action} p '
                u'WHERE p.{branch} = {action}.{branch} '
                u'ORDER BY p.{effective_date} DESC, p.{pk} DESC '
                u'LIMIT 1'
            u')'.format(
                action = quote_name(Action._meta.db_table),
                pk = quote_name(Action._meta.pk.column),
                branch = quote_name(Action._meta.get_field(u'branch').column),
                effective_date = quote_name(Action._meta.get_field(u'effective_date').column),
                )
            ])
        return Prefetch(join_lookup(path, u'action_set'), queryset, to_attr=u'_last_action')

    @cached_property
    def last_action(self):
        u"""
        Cached last branch action. Returns None if the branch has no actions. May be prefetched
        with ``prefetch_related(Branch.prefetch_last_action())`` queryset method. Takes advantage
        of ``Branch.actions`` if it is fetched already.
        """
        if u'_last_action' in self.__dict__:
            try:
                return self._last_action[0]
            except IndexError:
                return None
        elif u'actions' in self.__dict__:
            try:
                return self.actions[-1]
            except IndexError:
                return None
        else:
            return self.action_set.order_by_effective_date().last()

    @cached_property
    def can_add_request(self):
        return False

    @cached_property
    def can_add_clarification_response(self):
        return self.last_action.type == Action.TYPES.CLARIFICATION_REQUEST

    @cached_property
    def can_add_appeal(self):
        if self.last_action.type == Action.TYPES.DISCLOSURE:
            return self.last_action.disclosure_level != Action.DISCLOSURE_LEVELS.FULL
        if self.last_action.type in [
                Action.TYPES.REQUEST,
                Action.TYPES.CLARIFICATION_RESPONSE,
                Action.TYPES.CONFIRMATION,
                Action.TYPES.EXTENSION,
                Action.TYPES.REMANDMENT,
                Action.TYPES.ADVANCED_REQUEST,
                ]:
            return self.last_action.deadline_missed
        return self.last_action.type in [
                Action.TYPES.REFUSAL,
                Action.TYPES.ADVANCEMENT,
                Action.TYPES.EXPIRATION,
                ]

    @cached_property
    def can_add_confirmation(self):
        return self.last_action.type in [
                Action.TYPES.REQUEST,
                Action.TYPES.ADVANCED_REQUEST,
                ]

    @cached_property
    def can_add_extension(self):
        return self.last_action.type in [
                Action.TYPES.REQUEST,
                Action.TYPES.CONFIRMATION,
                Action.TYPES.CLARIFICATION_RESPONSE,
                Action.TYPES.REMANDMENT,
                Action.TYPES.ADVANCED_REQUEST,
                ]

    @cached_property
    def can_add_advancement(self):
        return self.last_action.type in [
                Action.TYPES.REQUEST,
                Action.TYPES.CLARIFICATION_RESPONSE,
                Action.TYPES.CONFIRMATION,
                Action.TYPES.ADVANCED_REQUEST,
                ]

    @cached_property
    def can_add_clarification_request(self):
        return self.last_action.type in [
                Action.TYPES.REQUEST,
                Action.TYPES.CLARIFICATION_RESPONSE,
                Action.TYPES.CONFIRMATION,
                Action.TYPES.CLARIFICATION_REQUEST,
                Action.TYPES.ADVANCED_REQUEST,
                ]

    @cached_property
    def can_add_disclosure(self):
        return self.last_action.type in [
                Action.TYPES.REQUEST,
                Action.TYPES.CLARIFICATION_RESPONSE,
                Action.TYPES.CONFIRMATION,
                Action.TYPES.EXTENSION,
                Action.TYPES.REMANDMENT,
                Action.TYPES.ADVANCED_REQUEST,
                ]

    @cached_property
    def can_add_refusal(self):
        return self.last_action.type in [
                Action.TYPES.REQUEST,
                Action.TYPES.CLARIFICATION_RESPONSE,
                Action.TYPES.CONFIRMATION,
                Action.TYPES.EXTENSION,
                Action.TYPES.REMANDMENT,
                Action.TYPES.ADVANCED_REQUEST,
                ]

    @cached_property
    def can_add_affirmation(self):
        return self.last_action.type == Action.TYPES.APPEAL

    @cached_property
    def can_add_reversion(self):
        return self.last_action.type == Action.TYPES.APPEAL

    @cached_property
    def can_add_remandment(self):
        return self.last_action.type == Action.TYPES.APPEAL

    @cached_property
    def can_add_applicant_action(self):
        return self.can_add_action(*Action.APPLICANT_ACTION_TYPES)

    @cached_property
    def can_add_applicant_email_action(self):
        return self.can_add_action(*Action.APPLICANT_EMAIL_ACTION_TYPES)

    @cached_property
    def can_add_obligee_action(self):
        return self.can_add_action(*Action.OBLIGEE_ACTION_TYPES)

    @cached_property
    def can_add_obligee_email_action(self):
        return self.can_add_action(*Action.OBLIGEE_EMAIL_ACTION_TYPES)

    def can_add_action(self, *action_types):
        for action_type in action_types:
            type_name = Action.TYPES._inverse[action_type]
            if getattr(self, u'can_add_%s' % type_name.lower()):
                return True
        return False

    def save(self, *args, **kwargs):
        if self.pk is None: # Creating a new object
            assert self.obligee_id is not None, u'%s.obligee is mandatory' % self.__class__.__name__
            assert self.historicalobligee_id is None, u'%s.historicalobligee is read-only' % self.__class__.__name__
            self.historicalobligee = self.obligee.history.first()

        super(Branch, self).save(*args, **kwargs)

    def add_expiration_if_expired(self):
        if self.last_action.has_obligee_deadline and self.last_action.deadline_missed:
            expiration = Action(
                    branch=self,
                    type=(Action.TYPES.APPEAL_EXPIRATION if self.last_action.type == Action.TYPES.APPEAL else Action.TYPES.EXPIRATION),
                    effective_date=local_today(),
                    )
            expiration.save()

    def collect_obligee_emails(self):
        res = {}
        for action in self.actions_by_email:
            if action.email.type == action.email.TYPES.INBOUND:
                res.update({action.email.from_mail: action.email.from_name})
            else: # OUTBOUND
                res.update({r.mail: r.name for r in action.email.recipients})
        # Current obligee emails
        res.update({mail: name for name, mail in self.obligee.emails_parsed})

        return ((name, mail) for mail, name in res.items())

    def __unicode__(self):
        return u'%s' % self.pk

class ActionQuerySet(QuerySet):
    # Applicant actions
    def applicant_actions(self):
        return self.filter(type__in=Action.APPLICANT_ACTION_TYPES)
    def requests(self):
        return self.filter(type=Action.TYPES.REQUEST)
    def clarification_responses(self):
        return self.filter(type=Action.TYPES.CLARIFICATION_RESPONSE)
    def appeals(self):
        return self.filter(type=Action.TYPES.APPEAL)

    # Obligee actions
    def obligee_actions(self):
        return self.filter(type__in=Action.OBLIGEE_ACTION_TYPES)
    def confirmations(self):
        return self.filter(type=Action.TYPES.CONFIRMATION)
    def extensions(self):
        return self.filter(type=Action.TYPES.EXTENSION)
    def advancements(self):
        return self.filter(type=Action.TYPES.ADVANCEMENT)
    def clarification_requests(self):
        return self.filter(type=Action.TYPES.CLARIFICATION_REQUEST)
    def disclosures(self):
        return self.filter(type=Action.TYPES.DISCLOSURE)
    def refusals(self):
        return self.filter(type=Action.TYPES.REFUSAL)
    def affirmations(self):
        return self.filter(type=Action.TYPES.AFFIRMATION)
    def reversions(self):
        return self.filter(type=Action.TYPES.REVERSION)
    def remandments(self):
        return self.filter(type=Action.TYPES.REMANDMENT)

    # Implicit actions
    def implicit_actions(self):
        return self.filter(type__in=Action.IMPLICIT_ACTION_TYPES)
    def advanced_requests(self):
        return self.filter(type=Action.TYPES.ADVANCED_REQUEST)
    def expirations(self):
        return self.filter(type=Action.TYPES.EXPIRATION)
    def appeal_expirations(self):
        return self.filter(type=Action.TYPES.APPEAL_EXPIRATION)

    # Other methods
    def by_email(self):
        return self.filter(email__isnull=False)
    def by_smail(self):
        return self.filter(email__isnull=True)
    def order_by_pk(self):
        return self.order_by(u'pk')
    def order_by_effective_date(self):
        return self.order_by(u'effective_date', u'pk')

class Action(models.Model):
    # May NOT be NULL; For index see index_together
    branch = models.ForeignKey(u'Branch', db_index=False)

    # NOT NULL for actions sent or received by email; NULL otherwise; For index see index_together
    email = models.OneToOneField(u'mail.Message', blank=True, null=True, db_index=False, on_delete=models.SET_NULL)

    # May NOT be NULL
    TYPES = FieldChoices(
            # Applicant actions
            (u'REQUEST',                 1, _(u'inforequests:Action:type:REQUEST')),
            (u'CLARIFICATION_RESPONSE', 12, _(u'inforequests:Action:type:CLARIFICATION_RESPONSE')),
            (u'APPEAL',                 13, _(u'inforequests:Action:type:APPEAL')),
            # Obligee actions
            (u'CONFIRMATION',            2, _(u'inforequests:Action:type:CONFIRMATION')),
            (u'EXTENSION',               3, _(u'inforequests:Action:type:EXTENSION')),
            (u'ADVANCEMENT',             4, _(u'inforequests:Action:type:ADVANCEMENT')),
            (u'CLARIFICATION_REQUEST',   5, _(u'inforequests:Action:type:CLARIFICATION_REQUEST')),
            (u'DISCLOSURE',              6, _(u'inforequests:Action:type:DISCLOSURE')),
            (u'REFUSAL',                 7, _(u'inforequests:Action:type:REFUSAL')),
            (u'AFFIRMATION',             8, _(u'inforequests:Action:type:AFFIRMATION')),
            (u'REVERSION',               9, _(u'inforequests:Action:type:REVERSION')),
            (u'REMANDMENT',             10, _(u'inforequests:Action:type:REMANDMENT')),
            # Implicit actions
            (u'ADVANCED_REQUEST',       11, _(u'inforequests:Action:type:ADVANCED_REQUEST')),
            (u'EXPIRATION',             14, _(u'inforequests:Action:type:EXPIRATION')),
            (u'APPEAL_EXPIRATION',      15, _(u'inforequests:Action:type:APPEAL_EXPIRATION')),
            )
    APPLICANT_ACTION_TYPES = (
            TYPES.REQUEST,
            TYPES.CLARIFICATION_RESPONSE,
            TYPES.APPEAL,
            )
    APPLICANT_EMAIL_ACTION_TYPES = (
            TYPES.REQUEST,
            TYPES.CLARIFICATION_RESPONSE,
            )
    OBLIGEE_ACTION_TYPES = (
            TYPES.CONFIRMATION,
            TYPES.EXTENSION,
            TYPES.ADVANCEMENT,
            TYPES.CLARIFICATION_REQUEST,
            TYPES.DISCLOSURE,
            TYPES.REFUSAL,
            TYPES.AFFIRMATION,
            TYPES.REVERSION,
            TYPES.REMANDMENT,
            )
    OBLIGEE_EMAIL_ACTION_TYPES = (
            TYPES.CONFIRMATION,
            TYPES.EXTENSION,
            TYPES.ADVANCEMENT,
            TYPES.CLARIFICATION_REQUEST,
            TYPES.DISCLOSURE,
            TYPES.REFUSAL,
            )
    IMPLICIT_ACTION_TYPES = (
            TYPES.ADVANCED_REQUEST,
            TYPES.EXPIRATION,
            TYPES.APPEAL_EXPIRATION,
            )
    type = models.SmallIntegerField(choices=TYPES._choices)

    # May be empty for implicit actions; Should NOT be empty for other actions
    subject = models.CharField(blank=True, max_length=255)
    content = models.TextField(blank=True)

    # May be empty
    attachment_set = generic.GenericRelation(u'attachments.Attachment', content_type_field=u'generic_type', object_id_field=u'generic_id')

    # May NOT be NULL
    effective_date = models.DateField(
            help_text=squeeze(u"""
                The date at which the action was sent or received. If the action was sent/received
                by e‑mail it's set automatically. If it was sent/received by s‑mail it's filled by
                the applicant.
                """))

    # May NOT be NULL for actions that set deadline; Must be NULL otherwise. Default value is
    # determined and automaticly set in save() when creating a new object. All actions that set
    # deadlines except CLARIFICATION_REQUEST, DISCLOSURE and REFUSAL set the deadline for the
    # obligee. CLARIFICATION_REQUEST, DISCLOSURE and REFUSAL set the deadline for the applicant.
    # DISCLOSURE sets the deadline only if not FULL.
    DEFAULT_DEADLINES = Bunch(
            # Applicant actions
            REQUEST=8,
            CLARIFICATION_RESPONSE=8,
            APPEAL=30,
            # Obligee actions
            CONFIRMATION=8,
            EXTENSION=10,
            ADVANCEMENT=None,
            CLARIFICATION_REQUEST=7, # Deadline for the applicant
            DISCLOSURE=(lambda a: 15 # Deadline for the applicant if not full disclosure
                    if a.disclosure_level != a.DISCLOSURE_LEVELS.FULL
                    else None),
            REFUSAL=15,              # Deadline for the applicant
            AFFIRMATION=None,
            REVERSION=None,
            REMANDMENT=13,
            # Implicit actions
            ADVANCED_REQUEST=13,
            EXPIRATION=None,
            APPEAL_EXPIRATION=None,
            )
    SETTING_APPLICANT_DEADLINE_TYPES = (
            # Applicant actions
            # Obligee actions
            TYPES.CLARIFICATION_REQUEST,
            TYPES.DISCLOSURE,
            TYPES.REFUSAL,
            # Implicit actions
            )
    SETTING_OBLIGEE_DEADLINE_TYPES = (
            # Applicant actions
            TYPES.REQUEST,
            TYPES.CLARIFICATION_RESPONSE,
            TYPES.APPEAL,
            # Obligee actions
            TYPES.CONFIRMATION,
            TYPES.EXTENSION,
            TYPES.REMANDMENT,
            # Implicit actions
            TYPES.ADVANCED_REQUEST,
            )
    deadline = models.IntegerField(blank=True, null=True,
            help_text=squeeze(u"""
                The deadline that apply after the action, if the action sets a deadline, NULL
                otherwise. The deadline is expressed in a number of working days (WD) counting
                since the effective date. It may apply to the applicant or to the obligee,
                depending on the action type.
                """))

    # May be NULL
    extension = models.IntegerField(blank=True, null=True,
            help_text=squeeze(u"""
                Applicant extension to the deadline, if the action sets an obligee deadline. The
                applicant may extend the deadline after it is missed in order to be patient and
                wait a little longer. He may extend it multiple times. Applicant deadlines may not
                be extended.
                """))

    # NOT NULL for ADVANCEMENT, DISCLOSURE, REVERSION and REMANDMENT; NULL otherwise
    DISCLOSURE_LEVELS = FieldChoices(
            (u'NONE',    1, _(u'inforequests:Action:disclosure_level:NONE')),
            (u'PARTIAL', 2, _(u'inforequests:Action:disclosure_level:PARTIAL')),
            (u'FULL',    3, _(u'inforequests:Action:disclosure_level:FULL')),
            )
    disclosure_level = models.SmallIntegerField(choices=DISCLOSURE_LEVELS._choices, blank=True, null=True,
            help_text=squeeze(u"""
                Mandatory choice for advancement, disclosure, reversion and remandment actions,
                NULL otherwise. Specifies if the obligee disclosed any requested information by
                this action.
                """))

    # NOT NULL for REFUSAL, AFFIRMATION; NULL otherwise
    REFUSAL_REASONS = FieldChoices(
            (u'DOES_NOT_HAVE',    3, _(u'inforequests:Action:refusal_reason:DOES_NOT_HAVE')),
            (u'DOES_NOT_PROVIDE', 4, _(u'inforequests:Action:refusal_reason:DOES_NOT_PROVIDE')),
            (u'DOES_NOT_CREATE',  5, _(u'inforequests:Action:refusal_reason:DOES_NOT_CREATE')),
            (u'COPYRIGHT',        6, _(u'inforequests:Action:refusal_reason:COPYRIGHT')),
            (u'BUSINESS_SECRET',  7, _(u'inforequests:Action:refusal_reason:BUSINESS_SECRET')),
            (u'PERSONAL',         8, _(u'inforequests:Action:refusal_reason:PERSONAL')),
            (u'CONFIDENTIAL',     9, _(u'inforequests:Action:refusal_reason:CONFIDENTIAL')),
            (u'NO_REASON',       -1, _(u'inforequests:Action:refusal_reason:NO_REASON')),
            (u'OTHER_REASON',    -2, _(u'inforequests:Action:refusal_reason:OTHER_REASON')),
            )
    refusal_reason = models.SmallIntegerField(choices=REFUSAL_REASONS._choices, blank=True, null=True,
            help_text=squeeze(u"""
                Mandatory choice for refusal and affirmation actions, NULL otherwise. Specifies the
                reason why the obligee refused to disclose the information.
                """))

    # May be NULL; Used by ``cron.obligee_deadline_reminder`` and ``cron.applicant_deadline_reminder``
    last_deadline_reminder = models.DateTimeField(blank=True, null=True)

    # Backward relations:
    #
    #  -- advanced_to_set: by Branch.advanced_by
    #     May NOT be empty for ADVANCEMENT; Must be empty otherwise

    # Backward relations added to other models:
    #
    #  -- Branch.action_set
    #     Should NOT be empty
    #
    #  -- Message.action
    #     May be undefined

    objects = ActionQuerySet.as_manager()

    class Meta:
        index_together = [
                [u'branch'],
                [u'email'],
                [u'effective_date', u'id'],
                ]

    @staticmethod
    def prefetch_attachments(path=None, queryset=None):
        u"""
        Use to prefetch ``Action.attachments``.
        """
        if queryset is None:
            queryset = Attachment.objects.get_queryset()
        queryset = queryset.order_by_pk()
        return Prefetch(join_lookup(path, u'attachment_set'), queryset, to_attr=u'attachments')

    @cached_property
    def attachments(self):
        u"""
        Cached list of all action attachments ordered by ``pk``. May be prefetched with
        ``prefetch_related(Action.prefetch_attachments())`` queryset method.
        """
        return list(self.attachment_set.order_by_pk())

    @cached_property
    def is_applicant_action(self):
        return self.type in self.APPLICANT_ACTION_TYPES

    @cached_property
    def is_obligee_action(self):
        return self.type in self.OBLIGEE_ACTION_TYPES

    @cached_property
    def is_implicit_action(self):
        return self.type in self.IMPLICIT_ACTION_TYPES

    @cached_property
    def is_by_email(self):
        return self.email_id is not None

    @cached_property
    def days_passed(self):
        return self.days_passed_at(local_today())

    @cached_property
    def deadline_remaining(self):
        return self.deadline_remaining_at(local_today())

    @cached_property
    def deadline_missed(self):
        return self.deadline_missed_at(local_today())

    @cached_property
    def has_deadline(self):
        return self.deadline is not None

    @cached_property
    def has_applicant_deadline(self):
        return self.deadline is not None and self.type in self.SETTING_APPLICANT_DEADLINE_TYPES

    @cached_property
    def has_obligee_deadline(self):
        return self.deadline is not None and self.type in self.SETTING_OBLIGEE_DEADLINE_TYPES

    def save(self, *args, **kwargs):
        if self.pk is None: # Creating a new object

            assert self.type is not None, u'%s.type is mandatory' % self.__class__.__name__
            if self.deadline is None:
                type_name = self.TYPES._inverse[self.type]
                deadline = getattr(self.DEFAULT_DEADLINES, type_name)
                self.deadline = deadline(self) if callable(deadline) else deadline

        super(Action, self).save(*args, **kwargs)

    def days_passed_at(self, at):
        return workdays.between(self.effective_date, at)

    def deadline_remaining_at(self, at):
        if self.deadline is None:
            return None
        deadline = self.deadline + (self.extension or 0)
        return deadline - self.days_passed_at(at)

    def deadline_missed_at(self, at):
        # self.deadline_remaining is 0 on the last day of deadline
        remaining = self.deadline_remaining_at(at)
        return remaining is not None and remaining < 0

    def send_by_email(self):
        if not self.is_applicant_action:
            raise TypeError(u'%s is not applicant action' % self.get_type_display())

        sender_name = self.branch.inforequest.applicant_name
        sender_address = self.branch.inforequest.unique_email
        sender_formatted = formataddr((squeeze(sender_name), sender_address))
        recipients = (formataddr(r) for r in self.branch.collect_obligee_emails())

        # FIXME: Attachment name and content type are set by client and not to be trusted. The name
        # must be sanitized and the content type white listed for known content types. Any unknown
        # content type should be replaced with 'application/octet-stream'.

        msg = EmailMessage(self.subject, self.content, sender_formatted, recipients)
        for attachment in self.attachments:
            msg.attach(attachment.name, attachment.content, attachment.content_type)
        msg.send()

        inforequestemail = InforequestEmail(
                inforequest=self.branch.inforequest,
                email=msg.instance,
                type=InforequestEmail.TYPES.APPLICANT_ACTION,
                )
        inforequestemail.save()

        self.email = msg.instance
        self.save()

    def __unicode__(self):
        return u'%s' % self.pk

class ActionDraftQuerySet(QuerySet):
    def order_by_pk(self):
        return self.order_by(u'pk')

class ActionDraft(models.Model):
    # May NOT be NULL; For index see index_together
    inforequest = models.ForeignKey(u'Inforequest', db_index=False)

    # May be NULL; Must be owned by the inforequest if set; For index see index_together
    branch = models.ForeignKey(u'Branch', blank=True, null=True, db_index=False,
            help_text=u'Must be owned by inforequest if set')

    # May NOT be NULL
    TYPES = Action.TYPES
    type = models.SmallIntegerField(choices=TYPES._choices)

    # May be empty
    subject = models.CharField(blank=True, max_length=255)
    content = models.TextField(blank=True)

    # May be empty
    attachment_set = generic.GenericRelation(u'attachments.Attachment', content_type_field=u'generic_type', object_id_field=u'generic_id')

    # May be NULL
    effective_date = models.DateField(blank=True, null=True)

    # May be NULL for EXTENSION; Must be NULL otherwise
    deadline = models.IntegerField(blank=True, null=True,
            help_text=u'Optional for extension actions. Must be NULL for all other actions.')

    # May be NULL for ADVANCEMENT, DISCLOSURE, REVERSION and REMANDMENT; Must be NULL otherwise
    DISCLOSURE_LEVELS = Action.DISCLOSURE_LEVELS
    disclosure_level = models.SmallIntegerField(choices=DISCLOSURE_LEVELS._choices, blank=True, null=True,
            help_text=u'Optional for advancement, disclosure, reversion and remandment actions. Must be NULL for all other actions.')

    # May be NULL for REFUSAL and AFFIRMATION; Must be NULL otherwise
    REFUSAL_REASONS = Action.REFUSAL_REASONS
    refusal_reason = models.SmallIntegerField(choices=REFUSAL_REASONS._choices, blank=True, null=True,
            help_text=u'Optional for refusal and affirmation actions. Must be NULL for all other actions.')

    # May be empty for ADVANCEMENT; Must be empty otherwise
    obligee_set = models.ManyToManyField(u'obligees.Obligee', blank=True,
            help_text=u'May be empty for advancement actions. Must be empty for all other actions.')

    # Backward relations added to other models:
    #
    #  -- Inforequest.actiondraft_set
    #
    #  -- Branch.actiondraft_set
    #
    #  -- Obligee.actiondraft_set

    objects = ActionDraftQuerySet.as_manager()

    class Meta:
        index_together = [
                [u'inforequest'],
                [u'branch'],
                ]

    @staticmethod
    def prefetch_attachments(path=None, queryset=None):
        u"""
        Use to prefetch ``ActionDraft.attachments``.
        """
        if queryset is None:
            queryset = Attachment.objects.get_queryset()
        queryset = queryset.order_by_pk()
        return Prefetch(join_lookup(path, u'attachment_set'), queryset, to_attr=u'attachments')

    @cached_property
    def attachments(self):
        u"""
        Cached list of all action draft attachments ordered by ``pk``. May be prefetched with
        ``prefetch_related(ActionDraft.prefetch_attachments())`` queryset method.
        """
        return list(self.attachment_set.order_by_pk())

    @staticmethod
    def prefetch_obligees(path=None, queryset=None):
        u"""
        Use to prefetch ``ActionDraft.obligees``.
        """
        if queryset is None:
            queryset = Obligee.objects.get_queryset()
        queryset = queryset.order_by_name()
        return Prefetch(join_lookup(path, u'obligee_set'), queryset, to_attr=u'obligees')

    @cached_property
    def obligees(self):
        u"""
        Cached list of all obligees the action draft advances to ordered by ``name``. May be
        prefetched with ``prefetch_related(ActionDraft.prefetch_obligees())`` queryset method.
        """
        return list(self.obligee_set.order_by_name())

    def __unicode__(self):
        return u'%s' % self.pk
