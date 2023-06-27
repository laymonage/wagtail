from django.conf import settings
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import ListView

from wagtail import hooks
from wagtail.admin.ui.side_panels import PageSidePanels
from wagtail.admin.views.generic.permissions import PermissionCheckedMixin
from wagtail.permission_policies.pages import Page, PagePermissionPolicy


class IndexView(PermissionCheckedMixin, ListView):
    template_name = "wagtailadmin/pages/index.html"
    permission_policy = PagePermissionPolicy()
    any_permission_required = {
        "add",
        "change",
        "publish",
        "bulk_delete",
        "lock",
        "unlock",
    }
    context_object_name = "pages"
    page_kwarg = "p"
    paginate_by = 50

    def get(self, request, parent_page_id=None):
        if parent_page_id:
            self.parent_page = get_object_or_404(Page, id=parent_page_id)
        else:
            self.parent_page = Page.get_first_root_node()

        # This will always succeed because of the check performed by PermissionCheckedMixin.
        root_page = self.permission_policy.explorable_root_instance(request.user)

        # If this page isn't a descendant of the user's explorable root page,
        # then redirect to that explorable root page instead.
        if not (
            self.parent_page.pk == root_page.pk
            or self.parent_page.is_descendant_of(root_page)
        ):
            return redirect("wagtailadmin_explore", root_page.pk)

        self.parent_page = self.parent_page.specific

        return super().get(request)

    def get_ordering(self):
        ordering = self.request.GET.get("ordering", "-latest_revision_created_at")
        if ordering not in [
            "title",
            "-title",
            "content_type",
            "-content_type",
            "live",
            "-live",
            "latest_revision_created_at",
            "-latest_revision_created_at",
            "ord",
        ]:
            ordering = "-latest_revision_created_at"

        return ordering

    def get_queryset(self):
        pages = self.parent_page.get_children().prefetch_related(
            "content_type", "sites_rooted_here"
        ) & self.permission_policy.explorable_instances(self.request.user)

        self.ordering = self.get_ordering()

        if self.ordering == "ord":
            # preserve the native ordering from get_children()
            pass
        elif self.ordering == "latest_revision_created_at":
            # order by oldest revision first.
            # Special case NULL entries - these should go at the top of the list.
            # Do this by annotating with Count('latest_revision_created_at'),
            # which returns 0 for these
            pages = pages.annotate(
                null_position=Count("latest_revision_created_at")
            ).order_by("null_position", "latest_revision_created_at")
        elif self.ordering == "-latest_revision_created_at":
            # order by oldest revision first.
            # Special case NULL entries - these should go at the end of the list.
            pages = pages.annotate(
                null_position=Count("latest_revision_created_at")
            ).order_by("-null_position", "-latest_revision_created_at")
        else:
            pages = pages.order_by(self.ordering)

        # We want specific page instances, but do not need streamfield values here
        pages = pages.defer_streamfields().specific()

        # allow hooks defer_streamfieldsyset
        for hook in hooks.get_hooks("construct_explorer_page_queryset"):
            pages = hook(self.parent_page, pages, self.request)

        # Annotate queryset with various states to be used later for performance optimisations
        if getattr(settings, "WAGTAIL_WORKFLOW_ENABLED", True):
            pages = pages.prefetch_workflow_states()

        pages = pages.annotate_site_root_state().annotate_approved_schedule()

        return pages

    def get_paginate_by(self, queryset):
        if self.ordering == "ord":
            # Don't paginate if sorting by page order - all pages must be shown to
            # allow drag-and-drop reordering
            return None
        else:
            return self.paginate_by

    def paginate_queryset(self, queryset, page_size):
        return super().paginate_queryset(queryset, page_size)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        show_ordering_column = self.ordering == "ord"

        side_panels = PageSidePanels(
            self.request,
            self.parent_page.get_latest_revision_as_object(),
            show_schedule_publishing_toggle=False,
            live_page=self.parent_page,
            scheduled_page=self.parent_page.get_scheduled_revision_as_object(),
            in_explorer=True,
            preview_enabled=False,
            comments_enabled=False,
        )

        context.update(
            {
                "parent_page": self.parent_page,
                "ordering": self.ordering,
                "side_panels": side_panels,
                "do_paginate": context["is_paginated"],
                "locale": None,
                "translations": [],
                "show_ordering_column": show_ordering_column,
                "show_bulk_actions": not show_ordering_column,
                "show_locale_labels": False,
            }
        )

        if getattr(settings, "WAGTAIL_I18N_ENABLED", False):
            if not self.parent_page.is_root():
                context.update(
                    {
                        "locale": self.parent_page.locale,
                        "translations": [
                            {
                                "locale": translation.locale,
                                "url": reverse(
                                    "wagtailadmin_explore", args=[translation.id]
                                ),
                            }
                            for translation in self.parent_page.get_translations()
                            .only("id", "locale")
                            .select_related("locale")
                        ],
                    }
                )
            else:
                context["show_locale_labels"] = True

        return context
