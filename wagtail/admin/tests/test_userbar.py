import json

from bs4 import BeautifulSoup
from django.contrib.auth.models import AnonymousUser
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse

from wagtail.coreutils import get_dummy_request
from wagtail.models import PAGE_TEMPLATE_VAR, Page
from wagtail.test.testapp.models import BusinessChild, BusinessIndex
from wagtail.test.utils import WagtailTestUtils


class TestUserbarTag(WagtailTestUtils, TestCase):
    def setUp(self):
        self.user = self.create_superuser(
            username="test", email="test@email.com", password="password"
        )
        self.homepage = Page.objects.get(id=2)

    def dummy_request(
        self,
        user=None,
        *,
        is_preview=False,
        in_preview_panel=False,
        revision_id=None,
        is_editing=False,
    ):
        request = get_dummy_request()
        request.user = user or AnonymousUser()
        request.is_preview = is_preview
        request.is_editing = is_editing
        request.in_preview_panel = in_preview_panel
        if revision_id:
            request.revision_id = revision_id
        return request

    def test_userbar_tag(self):
        template = Template("{% load wagtailuserbar %}{% wagtailuserbar %}")
        context = Context(
            {
                PAGE_TEMPLATE_VAR: self.homepage,
                "request": self.dummy_request(self.user),
            }
        )
        with self.assertNumQueries(5):
            content = template.render(context)

        self.assertIn("<!-- Wagtail user bar embed code -->", content)

    def test_userbar_tag_revision(self):
        self.homepage.save_revision(user=self.user, submitted_for_moderation=True)
        revision = self.homepage.get_latest_revision()
        template = Template("{% load wagtailuserbar %}{% wagtailuserbar %}")
        context = Context(
            {
                PAGE_TEMPLATE_VAR: self.homepage,
                "request": self.dummy_request(self.user, revision_id=revision.id),
            }
        )
        with self.assertNumQueries(7):
            content = template.render(context)

        self.assertIn("<!-- Wagtail user bar embed code -->", content)
        self.assertIn("Approve", content)

    def test_userbar_does_not_break_without_request(self):
        template = Template("{% load wagtailuserbar %}{% wagtailuserbar %}boom")
        content = template.render(Context({}))

        self.assertEqual("boom", content)

    def test_userbar_tag_self(self):
        """
        Ensure the userbar renders with `self` instead of `PAGE_TEMPLATE_VAR`
        """
        template = Template("{% load wagtailuserbar %}{% wagtailuserbar %}")
        content = template.render(
            Context(
                {
                    "self": self.homepage,
                    "request": self.dummy_request(self.user),
                }
            )
        )

        self.assertIn("<!-- Wagtail user bar embed code -->", content)

    def test_userbar_tag_anonymous_user(self):
        template = Template("{% load wagtailuserbar %}{% wagtailuserbar %}")
        content = template.render(
            Context(
                {
                    PAGE_TEMPLATE_VAR: self.homepage,
                    "request": self.dummy_request(),
                }
            )
        )

        # Make sure nothing was rendered
        self.assertEqual(content, "")

    def test_userbar_tag_no_page(self):
        template = Template("{% load wagtailuserbar %}{% wagtailuserbar %}")
        content = template.render(
            Context(
                {
                    "request": self.dummy_request(self.user),
                }
            )
        )

        self.assertIn("<!-- Wagtail user bar embed code -->", content)

    def test_edit_link(self):
        template = Template("{% load wagtailuserbar %}{% wagtailuserbar %}")
        content = template.render(
            Context(
                {
                    PAGE_TEMPLATE_VAR: self.homepage,
                    "request": self.dummy_request(self.user, is_preview=False),
                }
            )
        )
        self.assertIn("<!-- Wagtail user bar embed code -->", content)
        self.assertIn("Edit this page", content)

    def test_userbar_edit_menu_in_previews(self):
        # The edit link should be visible on draft, revision, and workflow previews.
        # https://github.com/wagtail/wagtail/issues/10002
        template = Template("{% load wagtailuserbar %}{% wagtailuserbar %}")
        content = template.render(
            Context(
                {
                    PAGE_TEMPLATE_VAR: self.homepage,
                    "request": self.dummy_request(self.user, is_preview=True),
                }
            )
        )
        self.assertIn("<!-- Wagtail user bar embed code -->", content)
        self.assertIn("Edit this page", content)
        self.assertIn(
            reverse("wagtailadmin_pages:edit", args=(self.homepage.id,)), content
        )

    def test_userbar_edit_menu_not_in_preview(self):
        # The edit link should not be visible on PreviewOnEdit/Create views.
        # https://github.com/wagtail/wagtail/issues/8765
        template = Template("{% load wagtailuserbar %}{% wagtailuserbar %}")
        content = template.render(
            Context(
                {
                    PAGE_TEMPLATE_VAR: self.homepage,
                    "request": self.dummy_request(
                        self.user, is_preview=True, is_editing=True
                    ),
                }
            )
        )
        self.assertIn("<!-- Wagtail user bar embed code -->", content)
        self.assertNotIn("Edit this page", content)
        self.assertNotIn(
            reverse("wagtailadmin_pages:edit", args=(self.homepage.id,)), content
        )

    def test_userbar_not_in_preview_panel(self):
        template = Template("{% load wagtailuserbar %}{% wagtailuserbar %}")
        content = template.render(
            Context(
                {
                    PAGE_TEMPLATE_VAR: self.homepage,
                    "request": self.dummy_request(
                        self.user, is_preview=True, in_preview_panel=True
                    ),
                }
            )
        )

        # Make sure nothing was rendered
        self.assertEqual(content, "")


class TestAccessibilityCheckerConfig(WagtailTestUtils, TestCase):
    def setUp(self):
        self.user = self.login()
        self.request = get_dummy_request()
        self.request.user = self.user

    def get_script(self):
        template = Template("{% load wagtailuserbar %}{% wagtailuserbar %}")
        content = template.render(Context({"request": self.request}))
        soup = BeautifulSoup(content, "html.parser")

        # Should include the configuration as a JSON script with the specific id
        return soup.find("script", id="accessibility-axe-configuration")

    def get_config(self):
        return json.loads(self.get_script().string)

    def test_config_json(self):
        script = self.get_script()
        # The configuration should be a valid non-empty JSON script
        self.assertIsNotNone(script)
        self.assertEqual(script.attrs["type"], "application/json")
        config_string = script.string.strip()
        self.assertGreater(len(config_string), 0)
        config = json.loads(config_string)
        self.assertIsInstance(config, dict)
        self.assertGreater(len(config.keys()), 0)

    def test_messages(self):
        # Should include the Wagtail's error messages
        config = self.get_config()
        self.assertIsInstance(config.get("messages"), dict)
        self.assertEqual(
            config["messages"]["empty-heading"],
            "Empty heading found. Use meaningful text for screen reader users.",
        )


class TestUserbarFrontend(WagtailTestUtils, TestCase):
    def setUp(self):
        self.login()
        self.homepage = Page.objects.get(id=2)

    def test_userbar_frontend(self):
        response = self.client.get(
            reverse("wagtailadmin_userbar_frontend", args=(self.homepage.id,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wagtailadmin/userbar/base.html")

    def test_userbar_frontend_anonymous_user_cannot_see(self):
        # Logout
        self.client.logout()

        response = self.client.get(
            reverse("wagtailadmin_userbar_frontend", args=(self.homepage.id,))
        )

        # Check that the user received a forbidden message
        self.assertEqual(response.status_code, 403)


class TestUserbarAddLink(WagtailTestUtils, TestCase):
    fixtures = ["test.json"]

    def setUp(self):
        self.login()
        self.homepage = Page.objects.get(url_path="/home/")
        self.event_index = Page.objects.get(url_path="/home/events/")

        self.business_index = BusinessIndex(title="Business", live=True)
        self.homepage.add_child(instance=self.business_index)

        self.business_child = BusinessChild(title="Business Child", live=True)
        self.business_index.add_child(instance=self.business_child)

    def test_page_allowing_subpages(self):
        response = self.client.get(
            reverse("wagtailadmin_userbar_frontend", args=(self.event_index.id,))
        )

        # page allows subpages, so the 'add page' button should show
        expected_url = reverse(
            "wagtailadmin_pages:add_subpage", args=(self.event_index.id,)
        )
        needle = f"""
            <a href="{expected_url}" target="_parent" role="menuitem">
                <svg class="icon icon-plus w-action-icon" aria-hidden="true">
                    <use href="#icon-plus"></use>
                </svg>
                Add a child page
            </a>
            """
        self.assertTagInHTML(needle, str(response.content))

    def test_page_disallowing_subpages(self):
        response = self.client.get(
            reverse("wagtailadmin_userbar_frontend", args=(self.business_child.id,))
        )

        # page disallows subpages, so the 'add page' button shouldn't show
        expected_url = reverse(
            "wagtailadmin_pages:add_subpage", args=(self.business_index.id,)
        )
        expected_link = (
            '<a href="%s" target="_parent">Add a child page</a>' % expected_url
        )
        self.assertNotContains(response, expected_link)


class TestUserbarModeration(WagtailTestUtils, TestCase):
    def setUp(self):
        self.login()
        self.homepage = Page.objects.get(id=2)
        self.homepage.save_revision(submitted_for_moderation=True)
        self.revision = self.homepage.get_latest_revision()

    def test_userbar_moderation(self):
        response = self.client.get(
            reverse("wagtailadmin_userbar_moderation", args=(self.revision.id,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wagtailadmin/userbar/base.html")

        expected_approve_html = """
            <form action="/admin/pages/moderation/{}/approve/" target="_parent" method="post">
                <input type="hidden" name="csrfmiddlewaretoken">
                <div class="w-action">
                    <input type="submit" value="Approve" class="button" />
                </div>
            </form>
        """.format(
            self.revision.id
        )
        self.assertTagInHTML(expected_approve_html, str(response.content))

        expected_reject_html = """
            <form action="/admin/pages/moderation/{}/reject/" target="_parent" method="post">
                <input type="hidden" name="csrfmiddlewaretoken">
                <div class="w-action">
                    <input type="submit" value="Reject" class="button" />
                </div>
            </form>
        """.format(
            self.revision.id
        )
        self.assertTagInHTML(expected_reject_html, str(response.content))

    def test_userbar_moderation_anonymous_user_cannot_see(self):
        # Logout
        self.client.logout()

        response = self.client.get(
            reverse("wagtailadmin_userbar_moderation", args=(self.revision.id,))
        )

        # Check that the user received a forbidden message
        self.assertEqual(response.status_code, 403)
