from django.contrib.auth.models import AnonymousUser, Group
from django.test import TestCase

from wagtail.models import Page, GroupPagePermission
from wagtail.permission_policies.pages import PagePermissionPolicy
from wagtail.test.utils import WagtailTestUtils
from wagtail.tests.test_permission_policies import PermissionPolicyTestUtils


class PermissionPolicyTestCase(PermissionPolicyTestUtils, WagtailTestUtils, TestCase):
    def setUp(self):
        self.root_page = Page.objects.get(id=2)

        self.reports_page = self.root_page.add_child(
            instance=Page(
                title="Reports",
                slug="reports",
            )
        )

        root_editors_group = Group.objects.create(name="Root editors")
        GroupPagePermission.objects.create(
            group=root_editors_group,
            page=self.root_page,
            permission_type="edit",
        )

        report_editors_group = Group.objects.create(name="Report editors")
        GroupPagePermission.objects.create(
            group=report_editors_group,
            page=self.reports_page,
            permission_type="edit",
        )

        report_adders_group = Group.objects.create(name="Report adders")
        GroupPagePermission.objects.create(
            group=report_adders_group,
            page=self.reports_page,
            permission_type="add",
        )

        # Users
        self.superuser = self.create_superuser(
            "superuser", "superuser@example.com", "password"
        )
        self.inactive_superuser = self.create_superuser(
            "inactivesuperuser", "inactivesuperuser@example.com", "password"
        )
        self.inactive_superuser.is_active = False
        self.inactive_superuser.save()

        # a user with edit permission through the root_editors_group
        self.root_editor = self.create_user(
            "rooteditor", "rooteditor@example.com", "password"
        )
        self.root_editor.groups.add(root_editors_group)

        # a user that has edit permission, but is inactive
        self.inactive_root_editor = self.create_user(
            "inactiverooteditor", "inactiverooteditor@example.com", "password"
        )
        self.inactive_root_editor.groups.add(root_editors_group)
        self.inactive_root_editor.is_active = False
        self.inactive_root_editor.save()

        # a user with edit permission on reports via the report_editors_group
        self.report_editor = self.create_user(
            "reporteditor", "reporteditor@example.com", "password"
        )
        self.report_editor.groups.add(report_editors_group)

        # a user with add permission on reports via the report_adders_group
        self.report_adder = self.create_user(
            "reportadder", "reportadder@example.com", "password"
        )
        self.report_adder.groups.add(report_adders_group)

        # a user with no permissions
        self.useless_user = self.create_user(
            "uselessuser", "uselessuser@example.com", "password"
        )

        self.anonymous_user = AnonymousUser()

        # a page in the root owned by 'reporteditor'
        self.editor_page = self.root_page.add_child(
            instance=Page(
                title="reporteditor's page",
                slug="reporteditor-page",
                owner=self.report_editor,
            )
        )

        # a page in reports owned by 'reporteditor'
        self.editor_report = self.reports_page.add_child(
            instance=Page(
                title="reporteditor's report",
                slug="reporteditor-report",
                owner=self.report_editor,
            )
        )

        # a page in reports owned by 'reportadder'
        self.adder_report = self.reports_page.add_child(
            instance=Page(
                title="reportadder's report",
                slug="reportadder-report",
                owner=self.report_adder,
            )
        )

        # a page in reports owned by 'uselessuser'
        self.useless_report = self.reports_page.add_child(
            instance=Page(
                title="uselessuser's report",
                slug="uselessuser-report",
                owner=self.useless_user,
            )
        )

        # a page in reports with no owner
        self.anonymous_report = self.reports_page.add_child(
            instance=Page(
                title="anonymous report",
                slug="anonymous-report",
            )
        )


class TestPagePermissionPolicy(PermissionPolicyTestCase):
    def setUp(self):
        super().setUp()
        self.policy = PagePermissionPolicy()

    def test_user_has_permission(self):
        self.assertUserPermissionMatrix(
            [
                (self.superuser, True, True, True, True),
                (self.inactive_superuser, False, False, False, False),
                (self.root_editor, False, True, False, False),
                (self.inactive_root_editor, False, False, False, False),
                (self.report_editor, False, True, False, False),
                (self.report_adder, True, False, False, False),
                (self.useless_user, False, False, False, False),
                (self.anonymous_user, False, False, False, False),
            ],
            ["add", "edit", "delete", "frobnicate"],
        )

    def test_user_has_any_permission(self):
        self.assertTrue(
            self.policy.user_has_any_permission(self.superuser, ["add", "edit"])
        )
        self.assertFalse(
            self.policy.user_has_any_permission(
                self.inactive_superuser, ["add", "edit"]
            )
        )
        self.assertTrue(
            self.policy.user_has_any_permission(self.report_editor, ["add", "edit"])
        )
        self.assertTrue(
            self.policy.user_has_any_permission(self.report_adder, ["add", "edit"])
        )
        self.assertFalse(
            self.policy.user_has_any_permission(self.anonymous_user, ["add", "edit"])
        )

    def test_users_with_any_permission(self):
        users_with_add_or_change_permission = self.policy.users_with_any_permission(
            ["add", "edit"]
        )

        self.assertResultSetEqual(
            users_with_add_or_change_permission,
            [
                self.superuser,
                self.root_editor,
                self.report_editor,
                self.report_adder,
            ],
        )

    def test_users_with_permission(self):
        users_with_change_permission = self.policy.users_with_permission("edit")

        self.assertResultSetEqual(
            users_with_change_permission,
            [
                self.superuser,
                self.root_editor,
                self.report_editor,
            ],
        )

        users_with_custom_permission = self.policy.users_with_permission("frobnicate")

        self.assertResultSetEqual(
            users_with_custom_permission,
            [
                self.superuser,
            ],
        )

    def test_user_has_permission_for_instance(self):
        # page in the root is only editable by users with permissions
        # on the root page
        self.assertUserInstancePermissionMatrix(
            self.editor_page,
            [
                (self.superuser, True, True, True),
                (self.inactive_superuser, False, False, False),
                (self.root_editor, True, False, False),
                (self.inactive_root_editor, False, False, False),
                (self.report_editor, False, False, False),
                (self.report_adder, False, False, False),
                (self.useless_user, False, False, False),
                (self.anonymous_user, False, False, False),
            ],
            ["edit", "delete", "frobnicate"],
        )

        # page in 'reports' is editable by users with permissions
        # on 'reports' or the root page
        self.assertUserInstancePermissionMatrix(
            self.useless_report,
            [
                (self.superuser, True, True, True),
                (self.inactive_superuser, False, False, False),
                (self.root_editor, True, False, False),
                (self.inactive_root_editor, False, False, False),
                (self.report_editor, True, False, False),
                (self.report_adder, False, False, False),
                (self.useless_user, False, False, False),
                (self.anonymous_user, False, False, False),
            ],
            ["edit", "delete", "frobnicate"],
        )

    def test_user_has_any_permission_for_instance(self):
        self.assertTrue(
            self.policy.user_has_any_permission_for_instance(
                self.report_editor, ["edit", "delete"], self.useless_report
            )
        )

        self.assertFalse(
            self.policy.user_has_any_permission_for_instance(
                self.report_editor, ["edit", "delete"], self.editor_page
            )
        )

        self.assertFalse(
            self.policy.user_has_any_permission_for_instance(
                self.anonymous_user, ["edit", "delete"], self.editor_page
            )
        )

    def test_instances_user_has_permission_for(self):
        self.assertResultSetEqual(
            self.policy.instances_user_has_permission_for(
                self.superuser,
                "edit",
            ),
            Page.objects.all(),
        )

        self.assertResultSetEqual(
            self.policy.instances_user_has_permission_for(
                self.inactive_superuser,
                "edit",
            ),
            [],
        )

        self.assertResultSetEqual(
            self.policy.instances_user_has_permission_for(
                self.root_editor,
                "edit",
            ),
            [
                self.root_page,
                self.reports_page,
                self.editor_page,
                self.editor_report,
                self.adder_report,
                self.useless_report,
                self.anonymous_report,
            ],
        )

        self.assertResultSetEqual(
            self.policy.instances_user_has_permission_for(
                self.report_editor,
                "edit",
            ),
            [
                self.reports_page,
                self.editor_report,
                self.useless_report,
                self.adder_report,
                self.anonymous_report,
            ],
        )

        self.assertResultSetEqual(
            self.policy.instances_user_has_permission_for(
                self.useless_user,
                "edit",
            ),
            [],
        )

        self.assertResultSetEqual(
            self.policy.instances_user_has_permission_for(
                self.anonymous_user,
                "edit",
            ),
            [],
        )

    def test_instances_user_has_any_permission_for(self):
        self.assertResultSetEqual(
            self.policy.instances_user_has_any_permission_for(
                self.superuser, ["edit", "delete"]
            ),
            Page.objects.all(),
        )

        self.assertResultSetEqual(
            self.policy.instances_user_has_any_permission_for(
                self.inactive_superuser, ["edit", "delete"]
            ),
            [],
        )

        self.assertResultSetEqual(
            self.policy.instances_user_has_any_permission_for(
                self.root_editor, ["edit", "delete"]
            ),
            [
                self.root_page,
                self.reports_page,
                self.editor_page,
                self.editor_report,
                self.adder_report,
                self.useless_report,
                self.anonymous_report,
            ],
        )

        self.assertResultSetEqual(
            self.policy.instances_user_has_any_permission_for(
                self.report_editor, ["edit", "delete"]
            ),
            [
                self.reports_page,
                self.editor_report,
                self.adder_report,
                self.useless_report,
                self.anonymous_report,
            ],
        )

        self.assertResultSetEqual(
            self.policy.instances_user_has_any_permission_for(
                self.useless_user, ["edit", "delete"]
            ),
            [],
        )

        self.assertResultSetEqual(
            self.policy.instances_user_has_any_permission_for(
                self.anonymous_user, ["edit", "delete"]
            ),
            [],
        )

    def test_users_with_permission_for_instance(self):
        self.assertResultSetEqual(
            self.policy.users_with_permission_for_instance("edit", self.editor_page),
            [self.superuser, self.root_editor],
        )
        self.assertResultSetEqual(
            self.policy.users_with_permission_for_instance("edit", self.adder_report),
            [self.superuser, self.root_editor, self.report_editor, self.report_adder],
        )
        self.assertResultSetEqual(
            self.policy.users_with_permission_for_instance("edit", self.editor_report),
            [self.superuser, self.root_editor, self.report_editor],
        )
        self.assertResultSetEqual(
            self.policy.users_with_permission_for_instance("edit", self.useless_report),
            [self.superuser, self.root_editor, self.report_editor],
        )
        self.assertResultSetEqual(
            self.policy.users_with_permission_for_instance(
                "edit", self.anonymous_report
            ),
            [self.superuser, self.root_editor, self.report_editor],
        )

    def test_users_with_any_permission_for_instance(self):
        self.assertResultSetEqual(
            self.policy.users_with_any_permission_for_instance(
                ["edit", "delete"], self.editor_page
            ),
            [self.superuser, self.root_editor],
        )
        self.assertResultSetEqual(
            self.policy.users_with_any_permission_for_instance(
                ["edit", "delete"], self.adder_report
            ),
            [self.superuser, self.root_editor, self.report_editor, self.report_adder],
        )
        self.assertResultSetEqual(
            self.policy.users_with_any_permission_for_instance(
                ["edit", "delete"], self.useless_report
            ),
            [self.superuser, self.root_editor, self.report_editor],
        )
        self.assertResultSetEqual(
            self.policy.users_with_any_permission_for_instance(
                ["delete", "frobnicate"], self.useless_report
            ),
            [self.superuser],
        )
