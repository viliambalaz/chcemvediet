# vim: expandtab
# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from django import forms
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from poleno.utils.date import local_today
from poleno.utils.misc import squeeze
from chcemvediet.apps.wizards import StepWIP, SectionStepWIP, DeadendStepWIP, PaperStepWIP, PrintStepWIP
from chcemvediet.apps.wizards.forms import PaperDateField

class AppealStep(StepWIP):
    template = u'inforequests/appeal/wizard.html'

class AppealSectionStep(AppealStep, SectionStepWIP):
    pass

class AppealDeadendStep(AppealStep, DeadendStepWIP):
    pass

class AppealFinalStep(AppealStep, PrintStepWIP):
    text_template = u'inforequests/appeal/texts/final.html'

    def clean(self):
        cleaned_data = super(AppealFinalStep, self).clean()

        if self.wizard.inforequest.has_undecided_emails:
            msg = squeeze(render_to_string(u'inforequests/appeal/messages/undecided_emails.txt', {
                    u'inforequest': self.wizard.inforequest,
                    }))
            self.add_error(None, msg)

        return cleaned_data

    def context(self, extra=None):
        res = super(AppealFinalStep, self).context(extra)

        last_action = self.wizard.last_action
        legal_date = self.wizard.values[u'legal_date']
        if last_action.has_applicant_deadline:
            res.update({
                    u'is_deadline_missed_at_today': last_action.deadline.is_deadline_missed,
                    u'calendar_days_behind_at_today': last_action.deadline.calendar_days_behind,
                    u'is_deadline_missed_at_legal_date': last_action.deadline.is_deadline_missed_at(legal_date),
                    u'calendar_days_behind_at_legal_date': last_action.deadline.calendar_days_behind_at(legal_date),
                    })

        return res

class AppealPaperStep(AppealStep, PaperStepWIP):
    text_template = u'inforequests/appeal/texts/paper.html'
    subject_template = u'inforequests/appeal/papers/subject.txt'
    content_template = u'inforequests/appeal/papers/base.html'
    global_fields = [u'legal_date']
    post_step_class = AppealFinalStep

    def add_fields(self):
        super(AppealPaperStep, self).add_fields()

        self.fields[u'legal_date'] = PaperDateField(
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
                    raise ValidationError(_(u'inforequests:AppealPaperStep:legal_date:error:older_than_last_action'))
                if legal_date < local_today():
                    raise ValidationError(_(u'inforequests:AppealPaperStep:legal_date:error:from_past'))
                if legal_date > local_today() + relativedelta(days=5):
                    raise ValidationError(_(u'inforequests:AppealPaperStep:legal_date:error:too_far_from_future'))
            except ValidationError as e:
                self.add_error(u'legal_date', e)

        return cleaned_data
