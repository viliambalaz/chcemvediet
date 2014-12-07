# vim: expandtab
# -*- coding: utf-8 -*-
from itertools import chain
from email.utils import formataddr, getaddresses

from django import forms
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.forms.util import flatatt
from django.utils.translation import ugettext_lazy as _
from django.utils.html import format_html

def clean_button(post, clean_values, default_value=None, key=u'button'):
    u"""
    Djago forms do not care about buttons. To distinguish which submit button was pressed, we need
    to give them names and values. This function filters ``request.POST`` values set by submit
    buttons for allowed values. Default button name is "button".

    Example:
        <button type="submit" name="button" value="email">...</button>
        <button type="submit" name="button" value="print">...</button>

        button = clean_button(request.POST, ['email', 'print'], default_value='email')
    """
    if key not in post:
        return default_value
    if post[key] not in clean_values:
        return default_value
    return post[key]

class AutoSuppressedSelect(forms.Select):
    u"""
    Selectbox that replaces itself with a static text if there is only one choice available. Actual
    selection of this only choice is made by a hidden input box. If using with ``ChoiceField``,
    make sure its ``empty_label`` is ``None``, otherwise the empty choice counts. Besides arguments
    supported by ``forms.Select`` the constructor of ``AutoSuppressedSelect`` takes one more
    keyword argument ``suppressed_attrs`` specifying widget's attributes when the selectbox is
    suppressed.

    Example:
        class MyForm(forms.Form)
            book = forms.ModelChoiceField(
                    queryset=Books.objects.all(),
                    empty_label=None,
                    widget=AutoSuppressedSelect(attrs={
                        'class': 'class-for-selectbox',
                        }, suppressed_attrs={
                        'class': 'class-for-plain-text',
                        }),
                    )

        If there are many books, you get:
            <select class="class-for-selectbox" name="...">...</select>
        If there is ony one book, you get:
            <span class="class-for-plain-text"><input type="hidden" name="..." value="...">...</span>
    """
    def __init__(self, *args, **kwargs):
        self.suppressed_attrs = kwargs.pop(u'suppressed_attrs', {})
        super(AutoSuppressedSelect, self).__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, choices=()):
        all_choices = list(chain(self.choices, choices))
        if len(all_choices) == 1:
            option_value, option_label = all_choices[0]
            if not isinstance(option_label, (list, tuple)): # The choice is not a group
                return format_html(u'<span{0}><input type="hidden" name="{1}" value="{2}">{3}</span>',
                        flatatt(self.suppressed_attrs), name, option_value, option_label)
        return super(AutoSuppressedSelect, self).render(name, value, attrs, choices)

class PrefixedForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(PrefixedForm, self).__init__(*args, **kwargs)
        self.prefix = u'%s%s%s' % (self.prefix or u'', u'-' if self.prefix else u'', self.__class__.__name__.lower())

def validate_comma_separated_emails(value):
    parsed = getaddresses([value])
    for name, address in parsed:
        try:
            validate_email(address)
        except ValidationError:
            raise ValidationError(_(u'"{0}" is not a valid email address.').format(address))

    formatted = u', '.join(formataddr((n, a)) for n, a in parsed)
    if formatted != value:
        raise ValidationError(_(u'Parsed value differs from the original. Parsed as: {0}').format(formatted))
