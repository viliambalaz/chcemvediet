# vim: expandtab
# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from django import forms
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from django.contrib.sessions.models import Session

from poleno.attachments.forms import AttachmentsField
from poleno.utils.models import after_saved
from poleno.utils.urls import reverse
from poleno.utils.date import local_date, local_today
from chcemvediet.apps.wizards import Bottom, Step, Wizard
from chcemvediet.apps.obligees.forms import MultipleObligeeWidget, MultipleObligeeField
from chcemvediet.apps.inforequests.models import Action, InforequestEmail
from chcemvediet.apps.inforequests.forms import BranchField, RefusalReasonField

class ObligeeActionStep(Step):
    template = u'inforequests/obligee_action/wizard.html'
    form_template = u'main/snippets/form_horizontal.html'

# Epilogue

class NotCategorized(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/not_categorized.html'
    global_fields = [u'help_request']
    post_step_class = Bottom

    def add_fields(self):
        super(NotCategorized, self).add_fields()

        self.fields[u'wants_help'] = forms.TypedChoiceField(
                label=u' ',
                coerce=int,
                choices=(
                    (1, _(u'inforequests:obligee_action:NotCategorized:help')),
                    (0, _(u'inforequests:obligee_action:NotCategorized:unrelated')),
                    ),
                widget=forms.RadioSelect(attrs={
                    u'class': u'toggle-changed',
                    u'data-container': u'form',
                    u'data-target-1': u'.control-group:has(.visible-if-wants-help)',
                    }),
                )

        self.fields[u'help_request'] = forms.CharField(
                label=_(u'inforequests:obligee_action:NotCategorized:help_request:label'),
                required=False,
                widget=forms.Textarea(attrs={
                    u'placeholder': _(u'inforequests:obligee_action:NotCategorized:help_request:placeholder'),
                    u'class': u'input-block-level visible-if-wants-help',
                    }),
                )

    def clean(self):
        cleaned_data = super(NotCategorized, self).clean()

        wants_help = cleaned_data.get(u'wants_help', None)
        help_request = cleaned_data.get(u'help_request', None)
        if wants_help and not help_request:
            msg = self.fields[u'help_request'].error_messages[u'required']
            self.add_error(u'help_request', msg)

        return cleaned_data

    def post_transition(self):
        res = super(NotCategorized, self).post_transition()

        if self.is_valid() and self.cleaned_data[u'wants_help']:
            res.globals[u'result'] = u'help'
        else:
            res.globals[u'result'] = u'unrelated'

        return res

class Categorized(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/categorized.html'
    global_fields = [u'legal_date', u'file_number', u'last_action_dd']
    post_step_class = Bottom

    def add_fields(self):
        super(Categorized, self).add_fields()

        self.fields[u'legal_date'] = forms.DateField(
                label=_(u'inforequests:obligee_action:Categorized:legal_date:label'),
                help_text=render_to_string(u'inforequests/obligee_action/texts/categorized_legal_date_help.txt', self.context()),
                localize=True,
                widget=forms.DateInput(attrs={
                    u'placeholder': _('inforequests:obligee_action:Categorized:legal_date:placeholder'),
                    u'class': u'datepicker',
                    }),
                )

        self.fields[u'file_number'] = forms.CharField(
                label=_(u'inforequests:obligee_action:Categorized:file_number:label'),
                max_length=255,
                required=False,
                widget=forms.TextInput(attrs={
                    u'placeholder': _(u'inforequests:obligee_action:Categorized:file_number:placeholder'),
                    u'class': u'span5',
                    }),
                )

        branch = self.wizard.values[u'branch']
        if branch.last_action.delivered_date is None and branch.last_action.type in [
                Action.TYPES.REQUEST, Action.TYPES.CLARIFICATION_RESPONSE, Action.TYPES.APPEAL, Action.TYPES.ADVANCED_REQUEST]:
            self.fields[u'last_action_dd'] = forms.DateField(
                    label=render_to_string(u'inforequests/obligee_action/texts/categorized_last_action_dd_label.txt', self.context()),
                    help_text=render_to_string(u'inforequests/obligee_action/texts/categorized_last_action_dd_help.txt', self.context()),
                    localize=True,
                    required=False,
                    widget=forms.DateInput(attrs={
                        u'placeholder': _('inforequests:obligee_action:Categorized:last_action_dd:placeholder'),
                        u'class': u'datepicker',
                        }),
                    )

    def clean(self):
        cleaned_data = super(Categorized, self).clean()

        branch = self.wizard.values[u'branch']
        delivered_date = self.wizard.values[u'delivered_date']
        legal_date = cleaned_data.get(u'legal_date', None)
        last_action_dd = cleaned_data.get(u'last_action_dd', None)

        if legal_date is not None:
            try:
                if legal_date > delivered_date:
                    raise ValidationError(_(u'inforequests:obligee_action:Categorized:legal_date:error:newer_than_delivered_date'))
                if legal_date < branch.last_action.legal_date:
                    raise ValidationError(_(u'inforequests:obligee_action:Categorized:legal_date:error:older_than_previous'))
                if legal_date > local_today():
                    raise ValidationError(_(u'inforequests:obligee_action:Categorized:legal_date:error:from_future'))
                if legal_date < local_today() - relativedelta(months=1):
                    raise ValidationError(_(u'inforequests:obligee_action:Categorized:legal_date:error:older_than_month'))
            except ValidationError as e:
                self.add_error(u'legal_date', e)

        if last_action_dd is not None:
            try:
                if legal_date and last_action_dd > legal_date:
                    raise ValidationError(_(u'inforequests:obligee_action:Categorized:last_action_dd:error:newer_than_legal_date'))
                if last_action_dd < branch.last_action.legal_date:
                    raise ValidationError(_(u'inforequests:obligee_action:Categorized:last_action_dd:error:older_than_last_action_legal_date'))
                if last_action_dd > local_today():
                    raise ValidationError(_(u'inforequests:obligee_action:Categorized:last_action_dd:error:from_future'))
                pass
            except ValidationError as e:
                self.add_error(u'last_action_dd', e)

        return cleaned_data

# Post Appeal

class InvalidReversion(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/invalid_reversion.html'
    global_fields = [u'help_request']
    post_step_class = Bottom

    def add_fields(self):
        super(InvalidReversion, self).add_fields()

        self.fields[u'help_request'] = forms.CharField(
                label=_(u'inforequests:obligee_action:InvalidReversion:help_request:label'),
                widget=forms.Textarea(attrs={
                    u'placeholder': _(u'inforequests:obligee_action:InvalidReversion:help_request:placeholder'),
                    u'class': u'input-block-level',
                    }),
                )

    def post_transition(self):
        res = super(InvalidReversion, self).post_transition()

        res.globals[u'result'] = u'help'

        return res

class ReversionReasons(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/reversion_reasons.html'
    global_fields = [u'refusal_reason']

    def add_fields(self):
        super(ReversionReasons, self).add_fields()
        self.fields[u'refusal_reason'] = RefusalReasonField()

    def post_transition(self):
        res = super(ReversionReasons, self).post_transition()

        res.globals[u'result'] = u'action'
        res.globals[u'action'] = Action.TYPES.REVERSION
        res.next = Categorized

        return res

class DisclosureLevelFork(ObligeeActionStep):

    def pre_transition(self):
        res = super(DisclosureLevelFork, self).pre_transition()
        disclosure_level = self.wizard.values.get(u'disclosure_level', None)

        if disclosure_level == Action.DISCLOSURE_LEVELS.FULL:
            res.globals[u'result'] = u'action'
            res.globals[u'action'] = Action.TYPES.REVERSION
            res.next = Categorized
        elif disclosure_level == Action.DISCLOSURE_LEVELS.PARTIAL:
            res.next = ReversionReasons
        elif disclosure_level == Action.DISCLOSURE_LEVELS.NONE:
            res.next = InvalidReversion
        else:
            res.next = ReversionReasons

        return res

class WasItReturned(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/was_returned.html'

    def add_fields(self):
        super(WasItReturned, self).add_fields()

        self.fields[u'was_returned'] = forms.TypedChoiceField(
                label=u' ',
                coerce=int,
                choices=(
                    (1, _(u'inforequests:obligee_action:WasItReturned:yes')),
                    (0, _(u'inforequests:obligee_action:WasItReturned:no')),
                    ),
                widget=forms.RadioSelect(),
            )

    def post_transition(self):
        res = super(WasItReturned, self).post_transition()

        if not self.is_valid():
            res.next = DisclosureLevelFork
        elif self.cleaned_data[u'was_returned']:
            res.globals[u'result'] = u'action'
            res.globals[u'action'] = Action.TYPES.REMANDMENT
            res.next = Categorized
        else:
            res.next = DisclosureLevelFork

        return res

class WasItAccepted(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/was_accepted.html'

    def add_fields(self):
        super(WasItAccepted, self).add_fields()

        self.fields[u'was_accepted'] = forms.ChoiceField(
                label=u' ',
                choices=(
                    (u'all', _(u'inforequests:obligee_action:WasItAccepted:all')),
                    (u'some', _(u'inforequests:obligee_action:WasItAccepted:some')),
                    (u'none', _(u'inforequests:obligee_action:WasItAccepted:none')),
                    ),
                widget=forms.RadioSelect(),
                )

    def post_transition(self):
        res = super(WasItAccepted, self).post_transition()

        if not self.is_valid():
            res.next = WasItReturned
        elif self.cleaned_data[u'was_accepted'] == u'none':
            res.globals[u'result'] = u'action'
            res.globals[u'action'] = Action.TYPES.AFFIRMATION
            res.next = Categorized
        else:
            res.next = WasItReturned

        return res

class ContainsAppealInfo(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/contains_appeal_info.html'
    global_fields = [u'disclosure_level']
    post_step_class = WasItAccepted

    def add_fields(self):
        super(ContainsAppealInfo, self).add_fields()

        self.fields[u'disclosure_level'] = forms.TypedChoiceField(
                label=u' ',
                coerce=int,
                choices=(
                    (Action.DISCLOSURE_LEVELS.FULL, _(u'inforequests:obligee_action:ContainsAppealInfo:full')),
                    (Action.DISCLOSURE_LEVELS.PARTIAL, _(u'inforequests:obligee_action:ContainsAppealInfo:partial')),
                    (Action.DISCLOSURE_LEVELS.NONE, _(u'inforequests:obligee_action:ContainsAppealInfo:none')),
                    ),
                widget=forms.RadioSelect(),
                )

class IsItAppealDecision(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/is_appeal_decision.html'

    def add_fields(self):
        super(IsItAppealDecision, self).add_fields()

        self.fields[u'is_decision'] = forms.TypedChoiceField(
                label=u' ',
                coerce=int,
                choices=(
                    (1, _(u'inforequests:obligee_action:IsItAppealDecision:yes')),
                    (0, _(u'inforequests:obligee_action:IsItAppealDecision:no')),
                    ),
                widget=forms.RadioSelect(),
                )

    def post_transition(self):
        res = super(IsItAppealDecision, self).post_transition()

        if not self.is_valid():
            res.next = ContainsAppealInfo
        elif self.cleaned_data[u'is_decision']:
            res.next = ContainsAppealInfo
        else:
            res.next = NotCategorized

        return res

class CanAddAppealDecision(ObligeeActionStep):

    def pre_transition(self):
        res = super(CanAddAppealDecision, self).pre_transition()
        branch = self.wizard.values.get(u'branch', None)

        if self.wizard.email:
            res.next = NotCategorized
        elif not branch:
            res.next = IsItAppealDecision
        elif branch.can_add_remandment:
            res.next = IsItAppealDecision
        else:
            res.next = NotCategorized

        return res

# Pre Appeal

class DisclosureReasons(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/disclosure_reasons.html'
    global_fields = [u'refusal_reason']

    def add_fields(self):
        super(DisclosureReasons, self).add_fields()
        self.fields[u'refusal_reason'] = RefusalReasonField()

    def post_transition(self):
        res = super(DisclosureReasons, self).post_transition()

        res.globals[u'result'] = u'action'
        res.globals[u'action'] = Action.TYPES.DISCLOSURE
        res.next = Categorized

        return res

class IsItExtension(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/is_extension.html'
    global_fields = [u'extension']

    def add_fields(self):
        super(IsItExtension, self).add_fields()

        self.fields[u'is_extension'] = forms.TypedChoiceField(
                label=u' ',
                coerce=int,
                choices=(
                    (1, _(u'inforequests:obligee_action:IsItExtension:yes')),
                    (0, _(u'inforequests:obligee_action:IsItExtension:no')),
                    ),
                widget=forms.RadioSelect(attrs={
                    u'class': u'toggle-changed',
                    u'data-container': u'form',
                    u'data-target-1': u'.control-group:has(.visible-if-extension)',
                    }),
                )

        self.fields[u'extension'] = forms.IntegerField(
                label=_(u'inforequests:obligee_action:IsItExtension:extension:label'),
                help_text=_(u'inforequests:obligee_action:IsItExtension:extension:help_text'),
                initial=8,
                min_value=2,
                max_value=15,
                required=False,
                widget=forms.NumberInput(attrs={
                    u'placeholder': _(u'inforequests:obligee_action:IsItExtension:extension:placeholder'),
                    u'class': u'visible-if-extension',
                    }),
                )

    def clean(self):
        cleaned_data = super(IsItExtension, self).clean()

        is_extension = cleaned_data.get(u'is_extension', None)
        extension = cleaned_data.get(u'extension', None)
        if is_extension and not extension:
            msg = self.fields[u'extension'].error_messages[u'required']
            self.add_error(u'extension', msg)

        return cleaned_data

    def post_transition(self):
        res = super(IsItExtension, self).post_transition()

        if not self.is_valid():
            res.next = DisclosureReasons
        elif self.cleaned_data[u'is_extension']:
            res.globals[u'result'] = u'action'
            res.globals[u'action'] = Action.TYPES.EXTENSION
            res.next = Categorized
        else:
            res.next = DisclosureReasons

        return res

class CanAddExtension(ObligeeActionStep):

    def pre_transition(self):
        res = super(CanAddExtension, self).pre_transition()
        branch = self.wizard.values.get(u'branch', None)

        if not branch:
            res.next = DisclosureReasons
        elif branch.can_add_extension:
            res.next = IsItExtension
        else:
            res.next = DisclosureReasons

        return res

class IsItAdvancement(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/is_advancement.html'
    global_fields = [u'advanced_to']

    def add_fields(self):
        super(IsItAdvancement, self).add_fields()

        self.fields[u'is_advancement'] = forms.TypedChoiceField(
                label=u' ',
                coerce=int,
                choices=(
                    (1, _(u'inforequests:obligee_action:IsItAdvancement:yes')),
                    (0, _(u'inforequests:obligee_action:IsItAdvancement:no')),
                    ),
                widget=forms.RadioSelect(attrs={
                    u'class': u'toggle-changed',
                    u'data-container': u'form',
                    u'data-target-1': u'.control-group:has(.visible-if-advancement)',
                    }),
                )

        self.fields[u'advanced_to'] = MultipleObligeeField(
                label=_(u'inforequests:obligee_action:IsItAdvancement:advanced_to:label'),
                help_text=_(u'inforequests:obligee_action:IsItAdvancement:advanced_to:help_text'),
                required=False,
                widget=MultipleObligeeWidget(input_attrs={
                    u'class': u'span5 visible-if-advancement',
                    u'placeholder': _(u'inforequests:obligee_action:IsItAdvancement:advanced_to:placeholder'),
                    }),
                )

    def clean(self):
        cleaned_data = super(IsItAdvancement, self).clean()

        is_advancement = cleaned_data.get(u'is_advancement', None)
        advanced_to = cleaned_data.get(u'advanced_to', None)
        branch = self.wizard.values[u'branch']
        if is_advancement:
            try:
                if not advanced_to:
                    raise ValidationError(self.fields[u'advanced_to'].error_messages[u'required'])
                for obligee in advanced_to:
                    if obligee == branch.obligee:
                        raise ValidationError(_(u'inforequests:obligee_action:IsItAdvancement:error:same_obligee'))
                if len(advanced_to) != len(set(advanced_to)):
                    raise ValidationError(_(u'inforequests:obligee_action:IsItAdvancement:error:duplicate_obligee'))
            except ValidationError as e:
                self.add_error(u'advanced_to', e)

        return cleaned_data

    def post_transition(self):
        res = super(IsItAdvancement, self).post_transition()

        if not self.is_valid():
            res.next = CanAddExtension
        elif self.cleaned_data[u'is_advancement']:
            res.globals[u'result'] = u'action'
            res.globals[u'action'] = Action.TYPES.ADVANCEMENT
            res.next = Categorized
        else:
            res.next = CanAddExtension

        return res

class CanAddAdvancement(ObligeeActionStep):

    def pre_transition(self):
        res = super(CanAddAdvancement, self).pre_transition()
        branch = self.wizard.values.get(u'branch', None)

        if not branch:
            res.next = CanAddExtension
        elif branch.can_add_advancement:
            res.next = IsItAdvancement
        else:
            res.next = CanAddExtension

        return res

class RefusalReasons(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/refusal_reasons.html'
    global_fields = [u'refusal_reason']

    def add_fields(self):
        super(RefusalReasons, self).add_fields()
        self.fields[u'refusal_reason'] = RefusalReasonField()

    def post_transition(self):
        res = super(RefusalReasons, self).post_transition()

        res.globals[u'result'] = u'action'
        res.globals[u'action'] = Action.TYPES.REFUSAL
        res.next = Categorized

        return res

class IsItDecision(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/is_decision.html'

    def add_fields(self):
        super(IsItDecision, self).add_fields()

        self.fields[u'is_decision'] = forms.TypedChoiceField(
                label=u' ',
                coerce=int,
                choices=(
                    (1, _(u'inforequests:obligee_action:IsItDecision:yes')),
                    (0, _(u'inforequests:obligee_action:IsItDecision:no')),
                    ),
                widget=forms.RadioSelect(),
                )

    def post_transition(self):
        res = super(IsItDecision, self).post_transition()

        if not self.is_valid():
            res.next = CanAddAdvancement
        elif self.cleaned_data[u'is_decision']:
            res.next = RefusalReasons
        else:
            res.next = CanAddAdvancement

        return res

class ContainsInfo(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/contains_info.html'
    global_fields = [u'disclosure_level']

    def add_fields(self):
        super(ContainsInfo, self).add_fields()

        self.fields[u'disclosure_level'] = forms.TypedChoiceField(
                label=u' ',
                coerce=int,
                choices=(
                    (Action.DISCLOSURE_LEVELS.FULL, _(u'inforequests:obligee_action:ContainsInfo:full')),
                    (Action.DISCLOSURE_LEVELS.PARTIAL, _(u'inforequests:obligee_action:ContainsInfo:partial')),
                    (Action.DISCLOSURE_LEVELS.NONE, _(u'inforequests:obligee_action:ContainsInfo:none')),
                    ),
                widget=forms.RadioSelect(),
                )

    def post_transition(self):
        res = super(ContainsInfo, self).post_transition()

        if not self.is_valid():
            res.next = IsItDecision
        elif self.cleaned_data[u'disclosure_level'] == Action.DISCLOSURE_LEVELS.FULL:
            res.globals[u'result'] = u'action'
            res.globals[u'action'] = Action.TYPES.DISCLOSURE
            res.next = Categorized
        else:
            res.next = IsItDecision

        return res

class IsOnTopic(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/is_on_topic.html'

    def add_fields(self):
        super(IsOnTopic, self).add_fields()

        self.fields[u'is_on_topic'] = forms.TypedChoiceField(
                label=u' ',
                coerce=int,
                choices=(
                    (1, _(u'inforequests:obligee_action:IsOnTopic:yes')),
                    (0, _(u'inforequests:obligee_action:IsOnTopic:no')),
                    ),
                widget=forms.RadioSelect(),
                )

    def post_transition(self):
        res = super(IsOnTopic, self).post_transition()

        if not self.is_valid():
            res.next = ContainsInfo
        elif self.cleaned_data[u'is_on_topic']:
            res.next = ContainsInfo
        else:
            res.next = NotCategorized

        return res

class CanAddDecision(ObligeeActionStep):

    def pre_transition(self):
        res = super(CanAddDecision, self).pre_transition()
        branch = self.wizard.values.get(u'branch', None)

        if not branch:
            res.next = IsOnTopic
        elif branch.can_add_refusal: # equivalent to ``can_add_disclosure``
            res.next = IsOnTopic
        else:
            res.next = CanAddAppealDecision

        return res

class IsItConfirmation(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/is_confirmation.html'

    def add_fields(self):
        super(IsItConfirmation, self).add_fields()

        self.fields[u'is_confirmation'] = forms.TypedChoiceField(
                label=u' ',
                coerce=int,
                choices=(
                    (1, _(u'inforequests:obligee_action:IsItConfirmation:yes')),
                    (0, _(u'inforequests:obligee_action:IsItConfirmation:no')),
                    ),
                widget=forms.RadioSelect(),
                )

    def post_transition(self):
        res = super(IsItConfirmation, self).post_transition()

        if not self.is_valid():
            res.next = CanAddDecision
        elif self.cleaned_data[u'is_confirmation']:
            res.globals[u'result'] = u'action'
            res.globals[u'action'] = Action.TYPES.CONFIRMATION
            res.next = Categorized
        else:
            res.next = CanAddDecision

        return res

class CanAddConfirmation(ObligeeActionStep):

    def pre_transition(self):
        res = super(CanAddConfirmation, self).pre_transition()
        branch = self.wizard.values.get(u'branch', None)

        if not branch:
            res.next = CanAddDecision
        elif branch.can_add_confirmation:
            res.next = IsItConfirmation
        else:
            res.next = CanAddDecision

        return res

class IsItQuestion(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/is_question.html'

    def add_fields(self):
        super(IsItQuestion, self).add_fields()

        self.fields[u'is_question'] = forms.TypedChoiceField(
                label=u' ',
                coerce=int,
                choices=(
                    (1, _(u'inforequests:obligee_action:IsItQuestion:yes')),
                    (0, _(u'inforequests:obligee_action:IsItQuestion:no')),
                    ),
                widget=forms.RadioSelect(),
                )

    def post_transition(self):
        res = super(IsItQuestion, self).post_transition()

        if not self.is_valid():
            res.next = CanAddConfirmation
        elif self.cleaned_data[u'is_question']:
            res.globals[u'result'] = u'action'
            res.globals[u'action'] = Action.TYPES.CLARIFICATION_REQUEST
            res.next = Categorized
        else:
            res.next = CanAddConfirmation

        return res

class CanAddClarificationRequest(ObligeeActionStep):

    def pre_transition(self):
        res = super(CanAddClarificationRequest, self).pre_transition()
        branch = self.wizard.values.get(u'branch', None)

        if not branch:
            res.next = CanAddConfirmation
        elif branch.can_add_clarification_request:
            res.next = IsItQuestion
        else:
            res.next = CanAddConfirmation

        return res

# Prologue

class InputBasics(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/basics.html'
    global_fields = [u'delivered_date', u'attachments']
    post_step_class = CanAddClarificationRequest

    def add_fields(self):
        super(InputBasics, self).add_fields()

        self.fields[u'delivered_date'] = forms.DateField(
                label=_(u'inforequests:obligee_action:InputBasics:delivered_date:label'),
                localize=True,
                widget=forms.DateInput(attrs={
                    u'placeholder': _('inforequests:obligee_action:InputBasics:delivered_date:placeholder'),
                    u'class': u'datepicker',
                    }),
                )

        self.fields[u'attachments'] = AttachmentsField(
                label=_(u'inforequests:obligee_action:InputBasics:attachments:label'),
                upload_url_func=(lambda: reverse(u'inforequests:upload_attachment')),
                download_url_func=(lambda a: reverse(u'inforequests:download_attachment', args=[a.pk])),
                attached_to=(
                    self.wizard.draft,
                    Session.objects.get(session_key=self.wizard.request.session.session_key),
                    ),
                )

    def clean(self):
        cleaned_data = super(InputBasics, self).clean()

        branch = self.wizard.values[u'branch']
        delivered_date = cleaned_data.get(u'delivered_date', None)
        if delivered_date is not None:
            try:
                if delivered_date < branch.last_action.legal_date:
                    raise ValidationError(_(u'inforequests:obligee_action:InputBasics:delivered_date:error:older_than_previous'))
                if delivered_date > local_today():
                    raise ValidationError(_(u'inforequests:obligee_action:InputBasics:delivered_date:error:from_future'))
                if delivered_date < local_today() - relativedelta(months=1):
                    raise ValidationError(_(u'inforequests:obligee_action:InputBasics:delivered_date:error:older_than_month'))
            except ValidationError as e:
                self.add_error(u'delivered_date', e)

        return cleaned_data

    def commit(self):
        super(InputBasics, self).commit()

        @after_saved(self.wizard.draft)
        def deferred(draft):
            for attachment in self.cleaned_data.get(u'attachments', []):
                attachment.generic_object = draft
                attachment.save()

class IsByEmail(ObligeeActionStep):

    def pre_transition(self):
        res = super(IsByEmail, self).pre_transition()

        if self.wizard.email:
            res.globals[u'delivered_date'] = local_date(self.wizard.email.processed)
            res.globals[u'attachments'] = None
            res.next = CanAddClarificationRequest
        else:
            res.next = InputBasics

        return res

class SelectBranch(ObligeeActionStep):
    text_template = u'inforequests/obligee_action/texts/branch.html'
    global_fields = [u'branch']
    post_step_class = IsByEmail

    def add_fields(self):
        super(SelectBranch, self).add_fields()

        self.fields[u'branch'] = BranchField(
                label=_(u'inforequests:obligee_action:SelectBranch:branch:label'),
                inforequest=self.wizard.inforequest,
                )

class HasSingeBranch(ObligeeActionStep):

    def pre_transition(self):
        res = super(HasSingeBranch, self).pre_transition()

        if len(self.wizard.inforequest.branches) == 1:
            res.globals[u'branch'] = self.wizard.inforequest.branches[0]
            res.next = IsByEmail
        else:
            res.next = SelectBranch

        return res

# Wizard

class ObligeeActionWizard(Wizard):
    first_step_class = HasSingeBranch

    def __init__(self, request, index, inforequest, inforequestemail, email):
        self.inforequest = inforequest
        self.inforequestemail = inforequestemail
        self.email = email
        super(ObligeeActionWizard, self).__init__(request, index)

    def get_instance_id(self):
        return u'%s-%s' % (self.__class__.__name__, self.inforequest.pk)

    def get_step_url(self, step, anchor=u''):
        return reverse(u'inforequests:obligee_action',
                kwargs=dict(inforequest=self.inforequest, step=step)) + anchor

    def context(self, extra=None):
        res = super(ObligeeActionWizard, self).context(extra)
        res.update({
                u'inforequest': self.inforequest,
                u'email': self.email,
                u'ACTION_TYPES': Action.TYPES,
                u'DISCLOSURE_LEVELS': Action.DISCLOSURE_LEVELS,
                })
        return res

    def finish(self):
        result = self.values[u'result']
        if result == u'action':
            return self.finish_action()
        if result == u'help':
            return self.finish_help()
        if result == u'unrelated':
            return self.finish_unrelated()
        raise ValueError

    def finish_action(self):
        assert self.values[u'action'] in Action.OBLIGEE_ACTION_TYPES
        assert not self.email or self.values[u'action'] in Action.OBLIGEE_EMAIL_ACTION_TYPES
        assert self.values[u'branch'].can_add_action(self.values[u'action'])

        last_action_dd = self.values.get(u'last_action_dd', None)
        if last_action_dd and not self.values[u'branch'].last_action.delivered_date:
            self.values[u'branch'].last_action.delivered_date = last_action_dd
            self.values[u'branch'].last_action.save(update_fields=[u'delivered_date'])

        action = Action.create(
                branch=self.values[u'branch'],
                type=self.values[u'action'],
                email=self.email if self.email else None,
                subject=self.email.subject if self.email else u'',
                content=self.email.text if self.email else u'',
                file_number=self.values[u'file_number'],
                delivered_date=self.values[u'delivered_date'],
                legal_date=self.values[u'legal_date'],
                extension=self.values.get(u'extension', None),
                disclosure_level=self.values.get(u'disclosure_level', None),
                refusal_reason=self.values.get(u'refusal_reason', None),
                advanced_to=self.values.get(u'advanced_to', None),
                attachments=self.email.attachments if self.email else self.values[u'attachments'],
                )
        action.save()

        if self.email:
            self.inforequestemail.type = InforequestEmail.TYPES.OBLIGEE_ACTION
            self.inforequestemail.save(update_fields=[u'type'])

        return action.get_absolute_url()

    def finish_help(self):
        # FIXME: use wizard.values[u'help_request'] to create a ticket

        if self.email:
            self.inforequestemail.type = InforequestEmail.TYPES.UNKNOWN
            self.inforequestemail.save(update_fields=[u'type'])

        return self.inforequest.get_absolute_url()

    def finish_unrelated(self):
        if self.email:
            self.inforequestemail.type = InforequestEmail.TYPES.UNRELATED
            self.inforequestemail.save(update_fields=[u'type'])

        return self.inforequest.get_absolute_url()
