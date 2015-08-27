# vim: expandtab
# -*- coding: utf-8 -*-
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.http import HttpResponseNotFound, HttpResponseRedirect

from poleno.utils.urls import reverse
from poleno.utils.views import require_ajax, login_required
from chcemvediet.apps.wizards.views import wizard_view
from chcemvediet.apps.inforequests.forms import ExtendDeadlineForm
from chcemvediet.apps.inforequests.forms import AppealWizards, ClarificationResponseWizard, ObligeeActionWizard
from chcemvediet.apps.inforequests.models import Inforequest, Action

from .shortcuts import render_form, json_form, json_success


@require_http_methods([u'HEAD', u'GET', u'POST'])
@transaction.atomic
@login_required(raise_exception=True)
def obligee_action(request, inforequest_slug, inforequest_pk, step_idx=None):
    inforequest = Inforequest.objects.not_closed().owned_by(request.user).get_or_404(pk=inforequest_pk)
    inforequestemail = inforequest.inforequestemail_set.undecided().oldest().get_or_none()
    email = inforequestemail.email if inforequestemail is not None else None

    if inforequest_slug != inforequest.slug:
        return HttpResponseRedirect(reverse(u'inforequests:obligee_action',
                kwargs=dict(inforequest=inforequest, step_idx=step_idx)))

    def finish(wizard):
        result = wizard.values[u'result']
        if result == u'action':
            action = wizard.save_action()
            return action.get_absolute_url()
        if result == u'help':
            wizard.save_help()
            return inforequest.get_absolute_url()
        if result == u'unrelated':
            wizard.save_unrelated()
            return inforequest.get_absolute_url()
        raise ValueError

    return wizard_view(ObligeeActionWizard, request, step_idx, finish,
            inforequest, inforequestemail, email)

@require_http_methods([u'HEAD', u'GET', u'POST'])
@transaction.atomic
@login_required(raise_exception=True)
def clarification_response(request, inforequest_slug, inforequest_pk, branch_pk, step_idx=None):
    inforequest = Inforequest.objects.not_closed().owned_by(request.user).get_or_404(pk=inforequest_pk)
    branch = inforequest.branch_set.get_or_404(pk=branch_pk)

    if not branch.can_add_clarification_response:
        return HttpResponseNotFound()
    if inforequest_slug != inforequest.slug:
        return HttpResponseRedirect(reverse(u'inforequests:clarification_response',
                kwargs=dict(branch=branch, step_idx=step_idx)))

    def finish(wizard):
        action = wizard.save()
        action.save()
        action.send_by_email()
        return action.get_absolute_url()

    return wizard_view(ClarificationResponseWizard, request, step_idx, finish, branch)

@require_http_methods([u'HEAD', u'GET', u'POST'])
@transaction.atomic
@login_required(raise_exception=True)
def appeal(request, inforequest_slug, inforequest_pk, branch_pk, step_idx=None):
    inforequest = Inforequest.objects.not_closed().owned_by(request.user).get_or_404(pk=inforequest_pk)
    branch = inforequest.branch_set.get_or_404(pk=branch_pk)

    if not branch.can_add_appeal:
        return HttpResponseNotFound()
    if inforequest_slug != inforequest.slug:
        return HttpResponseRedirect(reverse(u'inforequests:appeal',
                kwargs=dict(branch=branch, step_idx=step_idx)))

    def finish(wizard):
        branch.add_expiration_if_expired()
        action = wizard.save()
        action.save()
        return action.get_absolute_url()

    return wizard_view(AppealWizards, request, step_idx, finish, branch)

@require_http_methods([u'HEAD', u'GET', u'POST'])
@require_ajax
@transaction.atomic
@login_required(raise_exception=True)
def extend_deadline(request, inforequest_slug, inforequest_pk, branch_pk, action_pk):
    inforequest = Inforequest.objects.not_closed().owned_by(request.user).get_or_404(pk=inforequest_pk)
    branch = inforequest.branch_set.get_or_404(pk=branch_pk)
    action = branch.last_action

    if action.pk != Action._meta.pk.to_python(action_pk):
        return HttpResponseNotFound()
    if not action.can_applicant_extend:
        return HttpResponseNotFound()
    if inforequest.has_undecided_emails:
        return HttpResponseNotFound()
    if inforequest_slug != inforequest.slug:
        return HttpResponseRedirect(reverse(u'inforequests:extend_deadline',
                kwargs=dict(action=action)))

    if request.method != u'POST':
        form = ExtendDeadlineForm(prefix=action.pk)
        return render_form(request, form, inforequest=inforequest, branch=branch, action=action)

    form = ExtendDeadlineForm(request.POST, prefix=action.pk)
    if not form.is_valid():
        return json_form(request, form, inforequest=inforequest, branch=branch, action=action)

    form.save(action)
    action.save(update_fields=[u'applicant_extension'])

    # The inforequest was changed, we need to refetch it
    inforequest = Inforequest.objects.prefetch_detail().get(pk=inforequest.pk)
    return json_success(request, inforequest)
