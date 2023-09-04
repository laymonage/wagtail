from wagtail.admin.ui.side_panels import (
    BaseSidePanels,
    BaseStatusSidePanel,
    PreviewSidePanel,
)
from wagtail.models import PreviewableMixin


class SnippetStatusSidePanel(BaseStatusSidePanel):
    def get_context_data(self, parent_context):
        context = super().get_context_data(parent_context)
        inherit = [
            "view",
            "history_url",
            "workflow_history_url",
            "revisions_compare_url_name",
            "revision_enabled",
            "draftstate_enabled",
            "live_last_updated_info",
            "lock_url",
            "unlock_url",
            "user_can_lock",
            "user_can_unlock",
        ]
        context.update({k: parent_context.get(k) for k in inherit})

        context["status_templates"] = self.get_status_templates(context)
        return context


class SnippetSidePanels(BaseSidePanels):
    def __init__(
        self,
        request,
        object,
        view,
        *,
        show_schedule_publishing_toggle,
        live_object=None,
        scheduled_object=None,
    ):
        self.side_panels = []
        if object.pk or view.locale or show_schedule_publishing_toggle:
            self.side_panels += [
                SnippetStatusSidePanel(
                    object,
                    request,
                    show_schedule_publishing_toggle=show_schedule_publishing_toggle,
                    live_object=live_object,
                    scheduled_object=scheduled_object,
                ),
            ]

        if isinstance(object, PreviewableMixin) and object.is_previewable():
            self.side_panels += [
                PreviewSidePanel(object, request),
            ]
