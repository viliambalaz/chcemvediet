# vim: expandtab
# -*- coding: utf-8 -*-
from django.contrib import admin
from adminplus.sites import AdminSitePlus


# Imported from ``urls.py`` to initialize the project after all included apps were initialized.

admin.site = AdminSitePlus()
admin.autodiscover()
