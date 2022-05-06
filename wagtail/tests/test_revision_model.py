from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from wagtail.models import Page, Revision, get_default_page_content_type

from wagtail.test.testapp.models import (
    RevisionGrandChildModel,
    RevisionModel,
    SimplePage,
)


class TestRevisionModel(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.instance = RevisionModel.objects.create(text="foo")
        cls.content_type = ContentType.objects.get_for_model(RevisionModel)

    def test_can_save_revision(self):
        self.instance.text = "updated"
        revision = self.instance.save_revision()
        revision_from_db = self.instance.revisions.first()
        self.instance.refresh_from_db()

        self.assertEqual(revision, revision_from_db)
        # The revision should have the updated data
        self.assertEqual(revision_from_db.content["text"], "updated")
        # Only saving a revision should not update the instance itself
        self.assertEqual(self.instance.text, "foo")

    def test_get_latest_revision(self):
        self.instance.text = "updated"
        revision = self.instance.save_revision()
        self.instance.text = "updated twice"
        revision = self.instance.save_revision()
        revision_from_db = self.instance.get_latest_revision()

        self.assertEqual(revision, revision_from_db)
        self.assertEqual(revision_from_db.content["text"], "updated twice")

    def test_content_type_without_inheritance(self):
        self.instance.text = "updated"
        revision = self.instance.save_revision()

        revision_from_db = Revision.objects.filter(
            base_content_type=self.content_type,
            content_type=self.content_type,
            object_id=self.instance.pk,
        ).first()

        self.assertEqual(revision, revision_from_db)
        self.assertEqual(self.instance.get_base_content_type(), self.content_type)
        self.assertEqual(self.instance.get_content_type(), self.content_type)

    def test_content_type_with_inheritance(self):
        instance = RevisionGrandChildModel.objects.create(text="test")
        instance.text = "test updated"
        revision = instance.save_revision()

        base_content_type = self.content_type
        content_type = ContentType.objects.get_for_model(RevisionGrandChildModel)
        revision_from_db = Revision.objects.filter(
            base_content_type=base_content_type,
            content_type=content_type,
            object_id=instance.pk,
        ).first()

        self.assertEqual(revision, revision_from_db)
        self.assertEqual(instance.get_base_content_type(), base_content_type)
        self.assertEqual(instance.get_content_type(), content_type)

    def test_content_type_for_page_model(self):
        homepage = Page.objects.get(url_path="/home/")
        hello_page = SimplePage(
            title="Hello world", slug="hello-world", content="hello"
        )
        homepage.add_child(instance=hello_page)
        hello_page.content = "Updated world"
        revision = hello_page.save_revision()

        base_content_type = get_default_page_content_type()
        content_type = ContentType.objects.get_for_model(SimplePage)
        revision_from_db = Revision.objects.filter(
            base_content_type=base_content_type,
            content_type=content_type,
            object_id=hello_page.pk,
        ).first()

        self.assertEqual(revision, revision_from_db)
        self.assertEqual(hello_page.get_base_content_type(), base_content_type)
        self.assertEqual(hello_page.get_content_type(), content_type)
