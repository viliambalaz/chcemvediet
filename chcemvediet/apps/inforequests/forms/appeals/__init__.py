# vim: expandtab
# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from django import forms
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from poleno.workdays import workdays
from poleno.utils.views import reverse
from poleno.utils.date import local_today
from poleno.utils.misc import squeeze
from chcemvediet.apps.wizards import WizardStep, Wizard, WizardGroup
from chcemvediet.apps.wizards import WizardSectionStep, WizardDeadendStep, WizardPaperStep, WizardPrintStep
from chcemvediet.apps.wizards.forms import PaperDateField
from chcemvediet.apps.inforequests.models import Action


class AppealStep(WizardStep):
    template = u'inforequests/appeals/wizard.html'

class AppealSectionStep(AppealStep, WizardSectionStep):
    pass

class AppealDeadendStep(AppealStep, WizardDeadendStep):
    pass

class AppealPaperStep(AppealStep, WizardPaperStep):
    text_template = u'inforequests/appeals/texts/paper.html'
    subject_template = u'inforequests/appeals/papers/subject.txt'
    content_template = u'inforequests/appeals/papers/base.html'

    legal_date = PaperDateField(
            localize=True,
            initial=local_today,
            final_format=u'd.m.Y',
            widget=forms.DateInput(attrs={
                u'placeholder': _('inforequests:AppealPaperStep:legal_date:placeholder'),
                u'class': u'datepicker',
                }),
            )

    def clean(self):
        cleaned_data = super(AppealPaperStep, self).clean()

        branch = self.wizard.branch
        legal_date = cleaned_data.get(u'legal_date', None)
        if legal_date is not None:
            try:
                if legal_date < branch.last_action.legal_date:
                    raise ValidationError(_(u'inforequests:AppealPaperStep:legal_date:older_than_last_action_error'))
                if legal_date < local_today():
                    raise ValidationError(_(u'inforequests:AppealPaperStep:legal_date:from_past_error'))
                if legal_date > local_today() + relativedelta(days=5):
                    raise ValidationError(_(u'inforequests:AppealPaperStep:legal_date:too_far_from_future_error'))
            except ValidationError as e:
                self.add_error(u'legal_date', e)

        return cleaned_data

class AppealFinalStep(AppealStep, WizardPrintStep):
    text_template = u'inforequests/appeals/texts/final.html'

    def clean(self):
        cleaned_data = super(AppealFinalStep, self).clean()

        if self.wizard.branch.inforequest.has_undecided_emails:
                msg = squeeze(render_to_string(u'inforequests/appeals/messages/undecided_emails.txt', {
                        u'inforequest': self.wizard.branch.inforequest,
                        }))
                raise forms.ValidationError(msg, code=u'undecided_emails')

        return cleaned_data

    def context(self, extra=None):
        res = super(AppealFinalStep, self).context(extra)

        last_action = self.wizard.branch.last_action
        legal_date = self.wizard.values[u'legal_date']
        if last_action.deadline and last_action.deadline.is_applicant_deadline:
            res.update({
                    u'is_deadline_missed_at_today': last_action.deadline.is_deadline_missed,
                    u'calendar_days_remaining_at_today': last_action.deadline.calendar_days_remaining,
                    u'is_deadline_missed_at_legal_date': last_action.deadline.is_deadline_missed_at(legal_date),
                    u'calendar_days_remaining_at_legal_date': last_action.deadline.calendar_days_remaining_at(legal_date),
                    })

        return res


class AppealWizard(Wizard):

    def __init__(self, request, branch):
        super(AppealWizard, self).__init__(request)
        self.instance_id = u'%s-%s' % (self.__class__.__name__, branch.last_action.pk)
        self.branch = branch

    def get_step_url(self, step, anchor=u''):
        return reverse(u'inforequests:appeal', kwargs=dict(
            inforequest_slug=self.branch.inforequest.slug,
            inforequest_pk=self.branch.inforequest.pk,
            branch_pk=self.branch.pk,
            step_idx=step.index,
            )) + anchor

    def context(self, extra=None):
        res = super(AppealWizard, self).context(extra)
        res.update({
                u'inforequest': self.branch.inforequest,
                u'branch': self.branch,
                u'last_action': self.branch.last_action,
                u'rozklad': u'ministerstvo' in self.branch.obligee.name.lower(),
                u'fiktivne': self.branch.last_action.type != Action.TYPES.REFUSAL,
                u'not_at_all': self.branch.last_action.disclosure_level not in [
                    Action.DISCLOSURE_LEVELS.PARTIAL, Action.DISCLOSURE_LEVELS.FULL],
                })
        return res

    def _retrospection(self, last_action, recursive=False):
        res = []
        branch = last_action.branch
        obligee = branch.historicalobligee if recursive else None

        def clause(key, **kwargs):
            res.append(dict(key=key, obligee=obligee, **kwargs))

        if branch.is_main:
            clause(u'request', inforequest=branch.inforequest)
        else:
            res.extend(self._retrospection(branch.advanced_by, recursive=True))

        start_index = 0
        while True:
            actions = {t: [] for t in Action.TYPES._inverse}
            for index, action in enumerate(branch.actions[start_index:]):
                actions[action.type].append((start_index+index, action))
                if action == last_action or action.type == Action.TYPES.APPEAL:
                    break

            if actions[Action.TYPES.REMANDMENT] and start_index > 0:
                clause(u'remandment', remandment=actions[Action.TYPES.REMANDMENT][0][1])
            if actions[Action.TYPES.CONFIRMATION]:
                clause(u'confirmation', confirmation=actions[Action.TYPES.CONFIRMATION][0][1])
            if actions[Action.TYPES.CLARIFICATION_REQUEST]:
                requests = [a for i, a in actions[Action.TYPES.CLARIFICATION_REQUEST]]
                responses = [a for i, a in actions[Action.TYPES.CLARIFICATION_RESPONSE]]
                clause(u'clarification', clarification_requests=requests, clarification_responses=responses)
            if actions[Action.TYPES.EXTENSION]:
                extensions = [a for i, a in actions[Action.TYPES.EXTENSION]]
                clause(u'extension', extensions=extensions)
            if actions[Action.TYPES.APPEAL]:
                index, appeal = actions[Action.TYPES.APPEAL][0]
                previous = branch.actions[index-1] if index else None
                not_at_all = previous.disclosure_level not in [Action.DISCLOSURE_LEVELS.PARTIAL, Action.DISCLOSURE_LEVELS.FULL]
                if previous.type == Action.TYPES.ADVANCEMENT:
                    clause(u'advancement-appeal', advancement=previous, appeal=appeal, not_at_all=not_at_all)
                elif previous.type == Action.TYPES.DISCLOSURE:
                    clause(u'disclosure-appeal', disclosure=previous, appeal=appeal, not_at_all=not_at_all)
                elif previous.type == Action.TYPES.REFUSAL:
                    clause(u'refusal-appeal', refusal=previous, appeal=appeal)
                elif previous.type == Action.TYPES.EXPIRATION:
                    clause(u'expiration-appeal', expiration=previous, appeal=appeal)
                else:
                    clause(u'wild-appeal', appeal=appeal)
                start_index = index + 1
            else:
                break

        if recursive:
            clause(u'advancement', advancement=last_action)

        return res

    def retrospection(self):
        return self._retrospection(self.branch.last_action)

    def save(self, appeal):
        appeal.branch = self.branch
        appeal.subject = self.values[u'subject']
        appeal.content = self.values[u'content']
        appeal.content_type = Action.CONTENT_TYPES.HTML
        appeal.sent_date = self.values[u'legal_date']
        appeal.legal_date = self.values[u'legal_date']


# Must be after ``AppealWizard`` to break cyclic dependency
from .disclosure import DisclosureAppealWizard
from .refusal import RefusalAppealWizard
from .refusal_no_reason import RefusalNoReasonAppealWizard
from .advancement import AdvancementAppealWizard
from .expiration import ExpirationAppealWizard
from .fallback import FallbackAppealWizard

class AppealWizards(WizardGroup):
    wizard_classes = [
            DisclosureAppealWizard,
            RefusalAppealWizard,
            RefusalNoReasonAppealWizard,
            AdvancementAppealWizard,
            ExpirationAppealWizard,
            FallbackAppealWizard,
            ]
