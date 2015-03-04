# vim: expandtab
# -*- coding: utf-8 -*-
import random
import datetime
from testfixtures import TempDirectory

from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.test.utils import override_settings

from poleno.timewarp import timewarp
from poleno.utils.date import utc_now, utc_datetime_from_local, local_datetime_from_local

from ..models import Attachment

class AttachmentModelTest(TestCase):
    u"""
    Tests ``Attachment`` model.
    """

    def setUp(self):
        timewarp.enable()
        timewarp.reset()

        self.tempdir = TempDirectory()

        self.settings_override = override_settings(
            MEDIA_ROOT=self.tempdir.path,
            PASSWORD_HASHERS=(u'django.contrib.auth.hashers.MD5PasswordHasher',),
            )
        self.settings_override.enable()

        self.user = User.objects.create_user(u'john', u'lennon@thebeatles.com', u'johnpassword')
        self.user2 = User.objects.create_user(u'smith', u'agent@smith.com', u'big_secret')

    def tearDown(self):
        timewarp.reset()

        self.settings_override.disable()
        self.tempdir.cleanup()


    def _create_instance(self, **kwargs):
        omit = kwargs.pop(u'_omit', [])
        fields = {
                u'generic_object': self.user,
                u'file': ContentFile(u'content', name=u'filename.txt'),
                u'name': u'filename.txt',
                u'content_type': u'text/plain',
                }
        fields.update(kwargs)
        for key in omit:
            fields.pop(key, None)
        return Attachment.objects.create(**fields)


    def test_create_instance(self):
        obj = self._create_instance()
        self.assertIsNotNone(obj.pk)

    def test_generic_object_field(self):
        obj = self._create_instance(generic_object=self.user)
        self.assertEqual(obj.generic_type, ContentType.objects.get_for_model(User))
        self.assertEqual(obj.generic_id, self.user.pk)
        self.assertEqual(obj.generic_object, self.user)

    def test_generic_object_field_may_not_be_omitted(self):
        with self.assertRaisesMessage(IntegrityError, u'attachments_attachment.generic_type_id may not be NULL'):
            obj = self._create_instance(_omit=[u'generic_object'])

    def test_file_field(self):
        obj = self._create_instance(file=ContentFile(u'content'))
        self.assertRegexpMatches(obj.file.name, u'^attachments/[\w\d]+$')
        self.assertEqual(obj.file.size, 7)
        try:
            obj.file.open(u'rb')
            self.assertEqual(obj.file.read(), u'content')
        finally:
            obj.file.close()

    def test_file_field_may_not_be_omitted(self):
        with self.assertRaisesMessage(OSError, u'No such file or directory'):
            obj = self._create_instance(_omit=[u'file'])

    def test_file_field_name_overriden_when_creating_new_instance(self):
        u"""
        Checks that when creating a new attachment its file name is always autogenerated, even if
        it was set explicitly.
        """
        obj = self._create_instance(file=ContentFile(u'content', name=u'overriden'))
        self.assertNotIn(u'overriden', obj.file.name)

    def test_file_field_name_unchanged_when_saving_existing_instance(self):
        u"""
        Checks that when saving an already existing instance its file name is kept as it was when
        the instance was created.
        """
        obj = self._create_instance(file=ContentFile(u'content'))
        original_filename = obj.file.name
        obj.name = u'changed'
        obj.save()
        self.assertEqual(obj.name, u'changed')
        self.assertEqual(obj.file.name, original_filename)

    def test_name_and_content_type_fields(self):
        obj = self._create_instance(name=u'filename', content_type=u'text/plain')
        self.assertEqual(obj.name, u'filename')
        self.assertEqual(obj.content_type, u'text/plain')

    def test_name_and_content_type_fields_with_empty_values_if_omitted(self):
        obj = self._create_instance(_omit=[u'name', u'content_type'])
        self.assertEqual(obj.name, u'')
        self.assertEqual(obj.content_type, u'')

    def test_created_field_with_explicit_value(self):
        obj = self._create_instance(created=utc_datetime_from_local(u'2014-10-05 15:33:10'))
        self.assertEqual(obj.created, utc_datetime_from_local(u'2014-10-05 15:33:10'))

    def test_created_field_with_default_value_if_omitted(self):
        obj = self._create_instance(_omit=[u'created'])
        self.assertAlmostEqual(obj.created, utc_now(), delta=datetime.timedelta(seconds=10))

    def test_created_field_unchanged_when_saving_existing_instance(self):
        timewarp.jump(local_datetime_from_local(u'2014-10-05 15:33:10'))
        obj = self._create_instance()
        self.assertAlmostEqual(obj.created, utc_datetime_from_local(u'2014-10-05 15:33:10'), delta=datetime.timedelta(seconds=10))

        timewarp.jump(local_datetime_from_local(u'2014-10-07 20:23:11'))
        obj.name = u'changed'
        obj.save()
        self.assertAlmostEqual(obj.created, utc_datetime_from_local(u'2014-10-05 15:33:10'), delta=datetime.timedelta(seconds=10))

    def test_size_field_with_overriden_explicit_value(self):
        obj = self._create_instance(size=47)
        self.assertEqual(obj.size, 7)

    def test_size_field_with_default_value_if_omitted(self):
        obj = self._create_instance(_omit=['size'])
        self.assertEqual(obj.size, 7)

    def test_no_default_ordering(self):
        self.assertFalse(Attachment.objects.all().ordered)

    def test_content_property(self):
        obj = self._create_instance(file=ContentFile(u'content'))
        self.assertEqual(obj.content, u'content')

    def test_clone_method_clone_is_not_saved_automatically(self):
        obj = self._create_instance()
        new = obj.clone(obj.generic_object)
        self.assertIsNone(new.pk)

    def test_clone_method_fields_after_clone_saved(self):
        u"""
        Checks that all fields but ``file.name`` are copied to the clone.
        """
        obj = self._create_instance()
        new = obj.clone(obj.generic_object)
        new.save()
        self.assertIsNotNone(new.pk)
        self.assertEqual(new.generic_type, obj.generic_type)
        self.assertEqual(new.generic_id, obj.generic_id)
        self.assertEqual(new.generic_object, obj.generic_object)
        self.assertEqual(new.name, obj.name)
        self.assertEqual(new.content_type, obj.content_type)
        self.assertEqual(new.created, obj.created)
        self.assertEqual(new.size, obj.size)
        self.assertEqual(new.content, obj.content)

    def test_clone_method_clone_has_new_file_name(self):
        obj = self._create_instance()
        new = obj.clone(obj.generic_object)
        self.assertIsNone(new.file.name)
        new.save()
        self.assertNotEqual(new.file.name, obj.file.name)
        self.assertRegexpMatches(new.file.name, u'^attachments/[\w\d]+$')

    def test_clone_method_clone_has_old_created_value(self):
        timewarp.jump(local_datetime_from_local(u'2014-10-05 15:33:10'))
        obj = self._create_instance()
        self.assertAlmostEqual(obj.created, utc_datetime_from_local(u'2014-10-05 15:33:10'), delta=datetime.timedelta(seconds=10))

        timewarp.jump(local_datetime_from_local(u'2014-10-07 20:23:11'))
        new = obj.clone(obj.generic_object)
        new.save()
        self.assertAlmostEqual(new.created, utc_datetime_from_local(u'2014-10-05 15:33:10'), delta=datetime.timedelta(seconds=10))

    def test_clone_method_generic_object_argument(self):
        obj = self._create_instance(generic_object=self.user)
        new = obj.clone(self.user2)
        new.save()
        self.assertEqual(new.generic_type, ContentType.objects.get_for_model(User))
        self.assertEqual(new.generic_id, self.user2.pk)
        self.assertEqual(new.generic_object, self.user2)

    def test_repr(self):
        obj = self._create_instance()
        self.assertEqual(repr(obj), u'<Attachment: %s>' % obj.pk)

    def test_attached_to_query_method_with_queryset(self):
        obj1 = self._create_instance(generic_object=self.user)
        obj2 = self._create_instance(generic_object=self.user2)
        result = Attachment.objects.attached_to(User.objects.filter(pk=self.user2.pk))
        self.assertItemsEqual(result, [obj2])

    def test_attached_to_query_method_with_model_instance(self):
        obj1 = self._create_instance(generic_object=self.user)
        obj2 = self._create_instance(generic_object=self.user2)
        result = Attachment.objects.attached_to(self.user)
        self.assertItemsEqual(result, [obj1])

    def test_attached_to_query_method_with_model_class(self):
        obj1 = self._create_instance(generic_object=self.user)
        obj2 = self._create_instance(generic_object=self.user2)
        result = Attachment.objects.attached_to(User)
        self.assertItemsEqual(result, [obj1, obj2])

    def test_attached_to_query_method_with_multiple_arguments(self):
        obj1 = self._create_instance(generic_object=self.user)
        obj2 = self._create_instance(generic_object=self.user2)
        result = Attachment.objects.attached_to(User, self.user, User.objects.filter(pk=self.user2.pk), self.user2)
        self.assertItemsEqual(result, [obj1, obj2])

    def test_attached_to_query_method_with_invalid_argument(self):
        with self.assertRaisesMessage(TypeError, u'Expecting QuerySet, Model instance, or Model class.'):
            result = Attachment.objects.attached_to(object)
        with self.assertRaisesMessage(TypeError, u'Expecting QuerySet, Model instance, or Model class.'):
            result = Attachment.objects.attached_to(None)

    def test_order_by_pk_query_method(self):
        objs = [self._create_instance(generic_object=self.user) for i in range(20)]
        sample = random.sample(objs, 10)
        result = Attachment.objects.filter(pk__in=(d.pk for d in sample)).order_by_pk().reverse()
        self.assertEqual(list(result), sorted(sample, key=lambda d: -d.pk))
