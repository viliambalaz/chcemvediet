# vim: expandtab
# -*- coding: utf-8 -*-
from django.core.exceptions import ObjectDoesNotExist

from poleno.utils.misc import ensure_tuple

from .datasheets import common_repr, RollingError


class Field(object):
    is_related = False

    def __init__(self, confirm_changed=None, confirm_unchanged_if_changed=None):
        self.name = None
        self.column = None
        self.confirm_changed = confirm_changed
        self.confirm_unchanged_if_changed = confirm_unchanged_if_changed

    def do_confirm_changed(self, sheet, row_idx, value, original):
        if not self.confirm_changed:
            return
        if original and self.has_changed(original, value):
            inputed = sheet.importer.input_yes_no(
                    u'{} in row {} changed {}:\n\t{} -> {}',
                    u'Is it correct?',
                    sheet.obj_repr(original), row_idx, self.name,
                    self.value_repr(self.value_from_obj(original)),
                    self.value_repr(value),
                    default=u'Y')
            if inputed != u'Y':
                raise RollingError

    def do_confirm_unchanged_if_changed(self, sheet, row_idx, value, values, original):
        if not self.confirm_unchanged_if_changed:
            return
        if original and not self.has_changed(original, value):
            for other_name in ensure_tuple(self.confirm_unchanged_if_changed):
                other_field = sheet.columns.__dict__[other_name].field
                other_value = other_field.value_from_dict(values)
                if other_field.has_changed(original, other_value):
                    inputed = sheet.importer.input_yes_no(
                            u'{} in row {} changed {}:\n\t{} -> {}\nBut not {}:\n\t{}',
                            u'Is it correct?',
                            sheet.obj_repr(original), row_idx, other_field.name,
                            other_field.value_repr(other_field.value_from_obj(original)),
                            other_field.value_repr(other_value),
                            self.name, self.value_repr(value),
                            default=u'Y')
                    if inputed != u'Y':
                        raise RollingError
                    return

    def do_import(self, sheet, row_idx, values, original):
        value = self.value_from_dict(values)
        self.do_confirm_changed(sheet, row_idx, value, original)
        self.do_confirm_unchanged_if_changed(sheet, row_idx, value, values, original)
        return value

    def value_from_obj(self, obj):
        return getattr(obj, self.name)

    def value_from_dict(self, values):
        return values[self.column.label]

    def value_repr(self, value):
        return common_repr(value)

    def has_changed(self, obj, value):
        return getattr(obj, self.name) != value

    def save(self, obj, value):
        setattr(obj, self.name, value)

class FieldChoicesField(Field):

    def __init__(self, field_choices, **kwargs):
        super(FieldChoicesField, self).__init__(**kwargs)
        self.field_choices = field_choices

    def value_repr(self, value):
        return self.field_choices._inverse[value]

class ForeignKeyField(Field):
    is_related = False

    def value_from_obj(self, obj):
        try:
            return getattr(obj, self.name)
        except ObjectDoesNotExist:
            return None

    def has_changed(self, obj, value):
        try:
            return getattr(obj, self.name) != value
        except ObjectDoesNotExist:
            return True

class ManyToManyField(Field):
    is_related = True

    def value_from_obj(self, obj):
        return list(getattr(obj, self.name).all())

    def has_changed(self, obj, value):
        return set(getattr(obj, self.name).all()) != set(value)
