# vim: expandtab
# -*- coding: utf-8 -*-
from poleno.utils.urls import reverse
from chcemvediet.apps.wizards import WizardWIP
from chcemvediet.apps.inforequests.models import Action

from .common import AppealStep
from .refusal import RefusalAppeal
from .refusal_no_reason import RefusalNoReasonAppeal
from .disclosure import DisclosureAppeal
from .advancement import AdvancementAppeal
from .expiration import ExpirationAppeal
from .fallback import FallbackAppeal

class Dispatcher(AppealStep):

    def pre_transition(self):
        res = super(Dispatcher, self).pre_transition()
        last_action = self.wizard.last_action

        if (last_action.type == Action.TYPES.REFUSAL
                and last_action.refusal_reason
                and set(last_action.refusal_reason) <= RefusalAppeal.covered_reasons()):
            res.next = RefusalAppeal

        elif (last_action.type == Action.TYPES.REFUSAL
                and not last_action.refusal_reason):
            res.next = RefusalNoReasonAppeal

        elif (last_action.type == Action.TYPES.DISCLOSURE
                and last_action.disclosure_level != Action.DISCLOSURE_LEVELS.FULL):
            res.next = DisclosureAppeal

        elif last_action.type == Action.TYPES.ADVANCEMENT:
            res.next = AdvancementAppeal

        elif (last_action.type == Action.TYPES.EXPIRATION
                or last_action.has_obligee_deadline_missed):
            res.next = ExpirationAppeal

        else:
            res.next = FallbackAppeal

        return res

class AppealWizard(WizardWIP):
    first_step_class = Dispatcher

    def __init__(self, request, index, branch):
        self.inforequest = branch.inforequest
        self.branch = branch
        self.last_action = branch.last_action
        super(AppealWizard, self).__init__(request, index)

    def get_instance_id(self):
        return u'%s-%s' % (self.__class__.__name__, self.last_action.pk)

    def get_step_url(self, step, anchor=u''):
        return reverse(u'inforequests:appeal',
                kwargs=dict(branch=self.branch, step=step)) + anchor

    def context(self, extra=None):
        res = super(AppealWizard, self).context(extra)
        res.update({
                u'inforequest': self.inforequest,
                u'branch': self.branch,
                u'last_action': self.last_action,
                u'rozklad': u'ministerstvo' in self.branch.obligee.name.lower(),
                u'fiktivne': self.last_action.type != Action.TYPES.REFUSAL,
                u'not_at_all': self.last_action.disclosure_level not in [
                    Action.DISCLOSURE_LEVELS.PARTIAL, Action.DISCLOSURE_LEVELS.FULL],
                })
        return res

    def finish(self):
        self.branch.add_expiration_if_expired()

        action = Action.create(
                branch=self.branch,
                type=Action.TYPES.APPEAL,
                subject=self.values[u'subject'],
                content=self.values[u'content'],
                content_type=Action.CONTENT_TYPES.HTML,
                sent_date=self.values[u'legal_date'],
                legal_date=self.values[u'legal_date'],
                )
        action.save()

        return action.get_absolute_url()

    def retrospection(self, last_action=None, recursive=False):
        res = []
        last_action = last_action if last_action else self.last_action
        branch = last_action.branch
        obligee = branch.historicalobligee if recursive else None

        def clause(key, **kwargs):
            res.append(dict(key=key, obligee=obligee, **kwargs))

        if branch.is_main:
            clause(u'request', inforequest=branch.inforequest)
        else:
            res.extend(self.retrospection(branch.advanced_by, recursive=True))

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
