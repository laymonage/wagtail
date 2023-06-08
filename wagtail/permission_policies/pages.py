from django.contrib.auth import get_user_model
from django.db.models import Q

from wagtail.models import GroupPagePermission, Page
from wagtail.permission_policies.base import BasePermissionPolicy


class PagePermissionPolicy(BasePermissionPolicy):
    perm_cache_name = "_page_perm_cache"

    def __init__(self, model=Page):
        super().__init__(model=model)

    def get_all_permissions_for_user(self, user):
        if not user.is_active or user.is_anonymous or user.is_superuser:
            return GroupPagePermission.objects.none()
        return GroupPagePermission.objects.filter(group__user=user).select_related(
            "page"
        )

    def _base_user_has_permission(self, user):
        if not user.is_active:
            return False
        if user.is_superuser:
            return True
        return None

    def _base_queryset_for_user(self, user):
        if not user.is_active:
            return self.model._default_manager.none()
        if user.is_superuser:
            return self.model._default_manager.all()
        return None

    def user_has_permission(self, user, action):
        return self.user_has_any_permission(user, {action})

    def user_has_any_permission(self, user, actions):
        base_permission = self._base_user_has_permission(user)
        if base_permission is not None:
            return base_permission
        permissions = {
            perm.permission_type for perm in self.get_cached_permissions_for_user(user)
        }
        return bool(set(actions) & permissions)

    def users_with_any_permission(self, actions, include_superusers=True):
        groups = GroupPagePermission.objects.filter(
            permission_type__in=actions
        ).values_list("group", flat=True)

        q = Q(groups__in=groups)
        if include_superusers:
            q |= Q(is_superuser=True)

        return (
            get_user_model()
            ._default_manager.filter(is_active=True)
            .filter(q)
            .distinct()
        )

    def users_with_permission(self, action, include_superusers=True):
        return self.users_with_any_permission({action}, include_superusers)

    def user_has_permission_for_instance(self, user, action, instance):
        return self.user_has_any_permission_for_instance(user, {action}, instance)

    def user_has_any_permission_for_instance(self, user, actions, instance):
        base_permission = self._base_user_has_permission(user)
        if base_permission is not None:
            return base_permission

        permissions = set()
        for perm in self.get_cached_permissions_for_user(user):
            if instance.pk == perm.page_id or instance.is_descendant_of(perm.page):
                permissions.add(perm.permission_type)
                if perm.permission_type == "add" and instance.owner_id == user.pk:
                    permissions.add("edit")

        return bool(set(actions) & permissions)

    def instances_user_has_any_permission_for(self, user, actions):
        base_queryset = self._base_queryset_for_user(user)
        if base_queryset is not None:
            return base_queryset

        pages = self.model._default_manager.none()
        for perm in self.get_cached_permissions_for_user(user):
            if (
                perm.permission_type == "add"
                and "add" not in actions
                and "edit" in actions
            ):
                pages |= self.model._default_manager.descendant_of(
                    perm.page, inclusive=True
                ).filter(owner=user)
            elif perm.permission_type in actions:
                pages |= self.model._default_manager.descendant_of(
                    perm.page, inclusive=True
                )
        return pages

    def users_with_any_permission_for_instance(
        self, actions, instance, include_superusers=True
    ):
        # Find permissions for all ancestors that match any of the actions
        ancestors = instance.get_ancestors(inclusive=True)
        groups = GroupPagePermission.objects.filter(
            permission_type__in=actions, page__in=ancestors
        ).values_list("group", flat=True)

        q = Q(groups__in=groups)

        if include_superusers:
            q |= Q(is_superuser=True)

        # If "edit" is in actions but "add" is not, then we need to check for
        # cases where the user has "add" permission on an ancestor, and is the
        # owner of the instance
        if "edit" in actions and "add" not in actions:
            add_groups = GroupPagePermission.objects.filter(
                permission_type="add", page__in=ancestors
            ).values_list("group", flat=True)

            q |= Q(groups__in=add_groups) & Q(pk=instance.owner_id)

        return (
            get_user_model()
            ._default_manager.filter(is_active=True)
            .filter(q)
            .distinct()
        )

    def users_with_permission_for_instance(
        self, action, instance, include_superusers=True
    ):
        return self.users_with_any_permission_for_instance(
            {action}, instance, include_superusers
        )

    def instances_with_direct_explore_permission(self, user):
        # Get all pages that the user has direct add/edit/publish/lock permission on
        if user.is_superuser:
            # superuser has implicit permission on the root node
            return Page.objects.filter(depth=1)
        else:
            return [
                perm.page
                for perm in self.get_cached_permissions_for_user(user)
                if perm.permission_type in {"add", "edit", "publish", "lock"}
            ]

    def explorable_root_instance(self, user):
        pages = self.instances_with_direct_explore_permission(user)
        try:
            root_page = Page.objects.first_common_ancestor_of(
                pages, include_self=True, strict=True
            )
        except Page.DoesNotExist:
            root_page = None
        return root_page

    def explorable_instances(self, user):
        base_queryset = self._base_queryset_for_user(user)
        if base_queryset is not None:
            return base_queryset

        explorable_pages = self.instances_user_has_any_permission_for(
            user, {"add", "edit", "publish", "lock"}
        )

        # For all pages with specific permissions, add their ancestors as
        # explorable. This will allow deeply nested pages to be accessed in the
        # explorer. For example, in the hierarchy A>B>C>D where the user has
        # 'edit' access on D, they will be able to navigate to D without having
        # explicit access to A, B or C.
        page_permissions = [
            perm.page for perm in self.get_cached_permissions_for_user(user)
        ]
        for page in page_permissions:
            explorable_pages |= page.get_ancestors()

        # Remove unnecessary top-level ancestors that the user has no access to
        fca_page = Page.objects.first_common_ancestor_of(page_permissions)
        explorable_pages = explorable_pages.filter(path__startswith=fca_page.path)
        return explorable_pages
