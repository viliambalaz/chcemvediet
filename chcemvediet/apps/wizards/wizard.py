# vim: expandtab
# -*- coding: utf-8 -*-
from collections import OrderedDict

from django import forms
from django.template import RequestContext
from django.template.loader import render_to_string
from django.shortcuts import render

from poleno.utils.misc import squeeze

from .models import WizardDraft


class WizzardRollback(Exception):
    def __init__(self, step):
        self.step = step


class WizardStep(forms.Form):
    base_template = u'wizards/wizard.html'
    template = None
    text_template = None
    form_template = None
    counted_step = True

    @classmethod
    def applicable(cls, wizard):
        return True

    def __init__(self, wizard, index, key, *args, **kwargs):
        super(WizardStep, self).__init__(*args, **kwargs)
        self.wizard = wizard
        self.index = index
        self.key = key

    def commit(self):
        for field_name in self.fields:
            self.wizard.draft.data[field_name] = self._raw_value(field_name)

    def add_prefix(self, field_name):
        return self.wizard.add_prefix(field_name)

    def next(self):
        return self.wizard.next_step(self)

    def prev(self):
        return self.wizard.prev_step(self)

    def is_last(self):
        return self.wizard.is_last_step(self)

    def is_first(self):
        return self.wizard.is_first_step(self)

    def step_number(self):
        return self.wizard.step_number(self)

    def context(self, extra=None):
        return dict(self.wizard.context(extra), step=self)

    def values(self):
        return {f: self.cleaned_data[f] for f in self.fields}

    def get_url(self, anchor=u''):
        return self.wizard.get_step_url(self, anchor)

    def render(self):
        return render(self.wizard.request, self.template or self.base_template, self.context())

    def render_to_string(self):
        return render_to_string(self.template or self.base_template,
                context_instance=RequestContext(self.wizard.request), dictionary=self.context())

class WizardDeadendStep(WizardStep):
    base_template = u'wizards/deadend.html'
    counted_step = False

    def clean(self):
        cleaned_data = super(WizardDeadendStep, self).clean()
        self.add_error(None, u'deadend')
        return cleaned_data

class WizardSectionStep(WizardStep):
    base_template = u'wizards/section.html'
    section_template = None

    def paper_fields(self, step):
        pass

    def paper_context(self, extra=None):
        return dict(extra or {})

    def section_is_empty(self):
        return False

class WizardPaperStep(WizardStep):
    base_template = u'wizards/paper.html'
    subject_template = None
    content_template = None
    subject_value_name = u'subject'
    content_value_name = u'content'

    def __init__(self, *args, **kwargs):
        super(WizardPaperStep, self).__init__(*args, **kwargs)
        for step in self.wizard.steps.values():
            if isinstance(step, WizardSectionStep):
                step.paper_fields(self)

    def context(self, extra=None):
        res = super(WizardPaperStep, self).context(extra)
        for step in self.wizard.steps.values():
            if isinstance(step, WizardSectionStep):
                res.update(step.paper_context())
        return res

    def values(self):
        res = super(WizardPaperStep, self).values()

        subject = squeeze(render_to_string(self.subject_template, self.context(dict(finalize=True))))
        content = render_to_string(self.content_template, self.context(dict(finalize=True)))
        res.update({
                self.subject_value_name: subject,
                self.content_value_name: content,
                })

        return res

class WizardPrintStep(WizardStep):
    base_template = u'wizards/print.html'
    print_value_name = u'content'

    def print_content(self):
        return self.wizard.values[self.print_value_name]


class Wizard(object):
    step_classes = None

    @classmethod
    def applicable(cls):
        raise NotImplementedError

    def __init__(self, request):
        self.request = request
        self.instance_id = None
        self.current_step = None
        self.steps = None
        self.draft = None
        self.values = None

    def step(self, index=None):
        try:
            self.draft = WizardDraft.objects.owned_by(self.request.user).get(pk=self.instance_id)
        except WizardDraft.DoesNotExist:
            self.draft = WizardDraft(id=self.instance_id, owner=self.request.user, data={})

        try:
            current_index = int(index)
        except (TypeError, ValueError):
            current_index = -1

        self.steps = OrderedDict([(k, None) for k in self.step_classes])
        self.values = {}
        self.current_step = None

        prefixed_data = {self.add_prefix(f): v for f, v in self.draft.data.items()}
        for step_index, (step_key, step_class) in enumerate(self.step_classes.items()):
            if step_class.applicable(self):
                if step_index < current_index:
                    post = dict(prefixed_data)
                    step = step_class(self, step_index, step_key, data=post)
                    self.steps[step_key] = step
                    if not step.is_valid():
                        raise WizzardRollback(step)
                    self.values.update(step.values())
                elif step_index == current_index:
                    initial = dict(self.draft.data)
                    post = self.request.POST if self.request.method == u'POST' else None
                    step = step_class(self, step_index, step_key, initial=initial, data=post)
                    self.steps[step_key] = step
                    self.current_step = step
                    if not step.is_valid():
                        continue
                    self.values.update(step.values())
                else:
                    initial = dict(self.draft.data)
                    step = step_class(self, step_index, step_key, initial=initial)
                    self.steps[step_key] = step

        if self.current_step is None:
            for step in self.steps.values():
                if step is not None:
                    raise WizzardRollback(step)
            raise ValueError(u'The wizard has no applicable steps')

    def commit(self):
        self.current_step.commit()
        self.draft.step = self.current_step.key
        self.draft.save()

    def reset(self):
        self.draft.delete()

    def add_prefix(self, field_name):
        return u'%s-%s' % (self.instance_id, field_name)

    def next_step(self, step=None):
        if step is None:
            step = self.current_step
        for next_step in self.steps.values()[step.index+1:]:
            if next_step is not None:
                return next_step
        return None

    def prev_step(self, step=None):
        if step is None:
            step = self.current_step
        for prev_step in reversed(self.steps.values()[:step.index]):
            if prev_step is not None:
                return prev_step
        return None

    def is_last_step(self, step=None):
        return self.next_step(step) is None

    def is_first_step(self, step=None):
        return self.prev_step(step) is None

    def number_of_steps(self):
        return sum(1 for x in self.steps.values() if x and x.counted_step)

    def step_number(self, step=None):
        if step is None:
            step = self.current_step
        return sum(1 for x in self.steps.values()[:step.index] if x and x.counted_step) + 1

    def get_step_url(self, step, anchor=u''):
        raise NotImplementedError

    def context(self, extra=None):
        return dict(extra or {}, wizard=self)


class WizardGroup(object):
    wizard_classes = []

    @classmethod
    def find_applicable(cls, request, *args, **kwargs):
        for wizard_class in cls.wizard_classes:
            if wizard_class.applicable(*args, **kwargs):
                return wizard_class(request, *args, **kwargs)
        raise ValueError

#########################

class Bottom(object):
    pass

class Transition(object):
    def __init__(self):
        self.values = {}
        self.globals = {}
        self.next = None

class StepWIP(forms.Form):
    base_template = u'wizards/wizardwip.html'
    template = None
    text_template = None
    form_template = None
    global_fields = []
    pre_step_class = None
    post_step_class = Bottom

    def __init__(self, wizard, index, accessible, *args, **kwargs):
        super(StepWIP, self).__init__(*args, **kwargs)
        self.wizard = wizard
        self.index = index
        self.key = self.__class__.__name__
        self.accessible = accessible
        self.values = None

        # Make sure there are no step name conflicts
        assert self.key != u'global'
        assert self.key not in [s.key for s in wizard.steps]

    def commit(self):
        global_fields = self.get_global_fields()
        for field_name in self.fields:
            group = u'global' if field_name in global_fields else self.key
            dest = self.wizard.draft.data.setdefault(group, {})
            dest[field_name] = self._raw_value(field_name)

    def add_prefix(self, field_name):
        return self.wizard.add_prefix(field_name)

    def next(self):
        return self.wizard.next_step(self)

    def prev(self):
        return self.wizard.prev_step(self)

    def is_last(self):
        return self.wizard.is_last_step(self)

    def is_first(self):
        return self.wizard.is_first_step(self)

    def add_fields(self):
        pass

    def get_global_fields(self):
        return self.global_fields

    def context(self, extra=None):
        return dict(self.wizard.context(extra), step=self)

    def get_url(self, anchor=u''):
        return self.wizard.get_step_url(self, anchor)

    def render(self):
        return render(self.wizard.request, self.template or self.base_template, self.context())

    def render_to_string(self):
        return render_to_string(self.template or self.base_template,
                context_instance=RequestContext(self.wizard.request), dictionary=self.context())

    def pre_transition(self):
        res = Transition()
        res.next = self.pre_step_class
        return res

    def post_transition(self):
        res = Transition()
        if self.is_valid():
            global_fields = self.get_global_fields()
            for field_name in self.fields:
                if field_name in global_fields:
                    res.globals[field_name] = self.cleaned_data[field_name]
                else:
                    res.values[field_name] = self.cleaned_data[field_name]
        res.next = self.post_step_class
        return res

class SectionStepWIP(StepWIP):
    base_template = u'wizards/sectionwip.html'
    section_template = None

    def paper_fields(self, paper):
        pass

    def paper_context(self, extra=None):
        return dict(extra or {})

    def section_is_empty(self):
        return False

class DeadendStepWIP(StepWIP):
    base_template = u'wizards/deadendwip.html'

    def clean(self):
        cleaned_data = super(DeadendStepWIP, self).clean()
        self.add_error(None, u'deadend')
        return cleaned_data

class PaperStepWIP(StepWIP):
    base_template = u'wizards/paperwip.html'
    subject_template = None
    content_template = None
    subject_value_name = u'subject'
    content_value_name = u'content'

    def add_fields(self):
        super(PaperStepWIP, self).add_fields()
        for step in self.wizard.steps:
            if isinstance(step, SectionStepWIP):
                step.paper_fields(self)

    def get_global_fields(self):
        res = []
        res.extend(super(PaperStepWIP, self).get_global_fields())
        for step in self.wizard.steps:
            if isinstance(step, SectionStepWIP):
                res.extend(step.get_global_fields())
        return res

    def context(self, extra=None):
        res = super(PaperStepWIP, self).context(extra)
        for step in self.wizard.steps:
            if isinstance(step, SectionStepWIP):
                res.update(step.paper_context())
        return res

    def post_transition(self):
        res = super(PaperStepWIP, self).post_transition()

        if self.is_valid():
            context = self.context(dict(finalize=True))
            subject = squeeze(render_to_string(self.subject_template, context))
            content = render_to_string(self.content_template, context)
            res.globals[self.subject_value_name] = subject
            res.globals[self.content_value_name] = content

        return res

class PrintStepWIP(StepWIP):
    base_template = u'wizards/printwip.html'
    print_value_name = u'content'

    def print_content(self):
        return self.wizard.values[self.print_value_name]

class WizardWIP(object):
    first_step_class = None

    def _step_data(self, step, prefixed=False):
        res = {}
        for field, value in self.draft.data.get(step.key, {}).items():
            res[field] = value
        for field in step.get_global_fields():
            res[field] = self.draft.data.get(u'global', {}).get(field, None)
        if prefixed:
            res = {self.add_prefix(f): v for f, v in res.items()}
        return res

    def __init__(self, request, index=None):
        self.request = request
        self.steps = []
        self.values = {}
        self.instance_id = self.get_instance_id()

        try:
            self.draft = WizardDraft.objects.owned_by(request.user).get(pk=self.instance_id)
        except WizardDraft.DoesNotExist:
            self.draft = WizardDraft(id=self.instance_id, owner=request.user, data={})

        try:
            current_index = int(index)
        except (TypeError, ValueError):
            current_index = -1

        accessible = True
        step_class = self.first_step_class
        while step_class and step_class is not Bottom:
            step = step_class(self, len(self.steps), accessible)

            transition = step.pre_transition()
            step.values = dict(transition.values if accessible else {})
            self.values.update(transition.globals if accessible else {})
            step_class = transition.next
            if step_class:
                continue

            if accessible:
                step.add_fields()
                step.initial = self._step_data(step)
                if len(self.steps) < current_index:
                    step.data = self._step_data(step, prefixed=True)
                    step.is_bound = True
                if len(self.steps) == current_index and request.method == u'POST':
                    step.data = request.POST
                    step.is_bound = True
                if not step.is_valid():
                    accessible = False
            self.steps.append(step)

            transition = step.post_transition()
            step.values.update(transition.values if accessible else {})
            self.values.update(transition.globals if accessible else {})
            step_class = transition.next

        assert len(self.steps) > 0
        current_index = max(0, min(current_index, len(self.steps)-1))
        while current_index > 0 and not self.steps[current_index].accessible:
            current_index -= 1
        if u'%d' % current_index != index:
            raise WizzardRollback(self.steps[current_index])
        self.current_step = self.steps[current_index]

    def add_prefix(self, field_name):
        return u'%s-%s' % (self.instance_id, field_name)

    def commit(self):
        self.current_step.commit()
        self.draft.step = self.current_step.key
        self.draft.save()

    def reset(self):
        self.draft.delete()

    def next_step(self, step=None):
        if step is None:
            step = self.current_step
        if step.index+1 < len(self.steps):
            return self.steps[step.index+1]
        else:
            return None

    def prev_step(self, step=None):
        if step is None:
            step = self.current_step
        if step.index > 0:
            return self.steps[step.index-1]
        else:
            return None

    def is_last_step(self, step=None):
        return self.next_step(step) is None

    def is_first_step(self, step=None):
        return self.prev_step(step) is None

    def get_instance_id(self):
        raise NotImplementedError

    def get_step_url(self, step, anchor=u''):
        raise NotImplementedError

    def context(self, extra=None):
        return dict(extra or {}, wizard=self)

    def finish(self):
        raise NotImplementedError
