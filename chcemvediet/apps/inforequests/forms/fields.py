# vim: expandtab
# -*- coding: utf-8 -*-
from collections import defaultdict

from django import forms

class BranchChoiceField(forms.TypedChoiceField):

    def __init__(self, *args, **kwargs):
        inforequest = kwargs.pop(u'inforequest', None)
        super(BranchChoiceField, self).__init__(coerce=self.coerce, empty_value=None, *args, **kwargs)
        self.inforequest = inforequest

    @property
    def inforequest(self):
        return self._inforequest

    @inforequest.setter
    def inforequest(self, inforequest):
        self._inforequest = inforequest

        # Branches tree structure
        choices = [(None, u'')]
        tree = defaultdict(list)
        for branch in inforequest.branches:
            parent = None if branch.is_main else branch.advanced_by.branch
            tree[parent].append(branch)
        stack = [(0, b) for b in tree[None][::-1]]
        while stack:
            level, branch = stack.pop()
            prefix = u'  '*(level-1) + u' - ' if level > 0 else u''
            choices.append((branch.pk, prefix + branch.historicalobligee.name))
            stack.extend((level+1, b) for b in tree[branch][::-1])
        self.choices = choices

    def coerce(self, value):
        value = int(value)
        for branch in self.inforequest.branches:
            if value == branch.pk:
                return branch
        raise ValueError
