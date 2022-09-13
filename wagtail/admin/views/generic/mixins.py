from django.conf import settings
from django.contrib.admin.utils import quote
from django.db import transaction
from django.forms import Media
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext as _

from wagtail import hooks
from wagtail.admin import messages
from wagtail.admin.templatetags.wagtailadmin_tags import user_display_name
from wagtail.log_actions import log
from wagtail.log_actions import registry as log_registry
from wagtail.models import DraftStateMixin, Locale, TranslatableMixin


class HookResponseMixin:
    """
    A mixin for class-based views to run hooks by `hook_name`.
    """

    def run_hook(self, hook_name, *args, **kwargs):
        """
        Run the named hook, passing args and kwargs to each function registered under that hook name.
        If any return an HttpResponse, stop processing and return that response
        """
        for fn in hooks.get_hooks(hook_name):
            result = fn(*args, **kwargs)
            if hasattr(result, "status_code"):
                return result
        return None


class LocaleMixin:
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.locale = self.get_locale()

    def get_locale(self):
        i18n_enabled = getattr(settings, "WAGTAIL_I18N_ENABLED", False)
        if hasattr(self, "model") and self.model:
            i18n_enabled = i18n_enabled and issubclass(self.model, TranslatableMixin)

        if not i18n_enabled:
            return None

        if hasattr(self, "object") and self.object:
            return self.object.locale

        selected_locale = self.request.GET.get("locale")
        if selected_locale:
            return get_object_or_404(Locale, language_code=selected_locale)
        return Locale.get_default()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.locale:
            return context

        context["locale"] = self.locale
        return context


class PanelMixin:
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.panel = self.get_panel()

    def get_panel(self):
        return None

    def get_bound_panel(self, form):
        if not self.panel:
            return None
        return self.panel.get_bound_panel(
            request=self.request, instance=form.instance, form=form
        )

    def get_form_class(self):
        if not self.panel:
            return super().get_form_class()
        return self.panel.get_form_class()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        form = context.get("form")
        panel = self.get_bound_panel(form)

        media = context.get("media", Media())
        if form:
            media += form.media
        if panel:
            media += panel.media

        context.update(
            {
                "panel": panel,
                "media": media,
            }
        )

        return context


class CreateViewDraftStateMixin:
    def get_available_actions(self):
        return [*super().get_available_actions(), "publish"]

    def save_instance(self):
        """
        Called after the form is successfully validated.

        Before saving the new object, the live field is set to False.
        A new revision is created.
        """
        instance = self.form.save(commit=False)
        instance.live = False
        instance.save()
        self.form.save_m2m()

        self.new_revision = instance.save_revision(user=self.request.user)

        log(
            instance=instance,
            action="wagtail.create",
            revision=self.new_revision,
            content_changed=True,
        )

        return instance

    def publish_action(self):
        hook_response = self.run_hook("before_publish", self.request, self.object)
        if hook_response is not None:
            return hook_response

        self.new_revision.publish(user=self.request.user)

        hook_response = self.run_hook("after_publish", self.request, self.object)
        if hook_response is not None:
            return hook_response

        return None

    def form_valid(self, form):
        self.form = form
        with transaction.atomic():
            self.object = self.save_instance()

        if self.action == "publish":
            response = self.publish_action()
            if response is not None:
                return response

        response = self.save_action()

        return response


class EditViewDraftStateMixin:
    def get_available_actions(self):
        return [*super().get_available_actions(), "publish"]

    def get_object(self, queryset=None):
        object = super().get_object(queryset)
        return object.get_latest_revision_as_object()

    def save_instance(self):
        """
        Called after the form is successfully validated.

        Instead of saving a new object, a new revision is created.
        """
        instance = self.form.save(commit=False)
        self.has_content_changes = self.form.has_changed()
        self.new_revision = instance.save_revision(
            user=self.request.user,
            changed=self.has_content_changes,
        )

        log(
            instance=instance,
            action="wagtail.edit",
            revision=self.new_revision,
            content_changed=self.has_content_changes,
        )

        return instance

    def publish_action(self):
        hook_response = self.run_hook("before_publish", self.request, self.object)
        if hook_response is not None:
            return hook_response

        self.new_revision.publish(user=self.request.user)

        hook_response = self.run_hook("after_publish", self.request, self.object)
        if hook_response is not None:
            return hook_response

        return None

    def get_success_message(self):
        if self.draftstate_enabled and self.action == "publish":
            if self.object.go_live_at and self.object.go_live_at > timezone.now():
                return _("'{0}' updated and scheduled for publishing.").format(
                    self.object
                )
            return _("'{0}' updated and published.").format(self.object)
        return super().get_success_message()

    def get_live_last_updated_info(self):
        if not self.object.live:
            return None

        revision = self.object.live_revision

        # No revision exists, fall back to latest log entry
        if not revision:
            return log_registry.get_logs_for_instance(self.object).first()

        return {
            "timestamp": revision.created_at,
            "user_display_name": user_display_name(revision.user),
        }

    def get_draft_last_updated_info(self):
        if not self.object.has_unpublished_changes:
            return None

        revision = self.object.latest_revision

        return {
            "timestamp": revision.created_at,
            "user_display_name": user_display_name(revision.user),
        }

    def form_valid(self, form):
        self.form = form
        with transaction.atomic():
            self.object = self.save_instance()

        if self.action == "publish":
            response = self.publish_action()
            if response is not None:
                return response

        response = self.save_action()

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["revision_enabled"] = True
        context["draftstate_enabled"] = True
        context["live_last_updated_info"] = self.get_live_last_updated_info()
        context["draft_last_updated_info"] = self.get_draft_last_updated_info()
        return context


class CreateViewRevisionMixin:
    def save_instance(self):
        """
        Called after the form is successfully validated.

        In addition to saving the object, a new revision is created.
        """
        instance = self.form.save()
        self.new_revision = instance.save_revision(user=self.request.user)

        log(
            instance=instance,
            action="wagtail.create",
            revision=self.new_revision,
            content_changed=True,
        )

        return instance


class EditViewRevisionMixin:
    def save_instance(self):
        """
        Called after the form is successfully validated.

        In addition to saving the object, a new revision is created.
        """
        instance = self.form.save()
        self.has_content_changes = self.form.has_changed()
        self.new_revision = instance.save_revision(
            user=self.request.user,
            changed=self.has_content_changes,
        )

        log(
            instance=instance,
            action="wagtail.edit",
            revision=self.new_revision,
            content_changed=self.has_content_changes,
        )

        return instance

    def get_live_last_updated_info(self):
        revision = self.object.latest_revision

        # No revision exists, fall back to latest log entry
        if not revision:
            return log_registry.get_logs_for_instance(self.object).first()

        return {
            "timestamp": revision.created_at,
            "user_display_name": user_display_name(revision.user),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["revision_enabled"] = True
        context["live_last_updated_info"] = self.get_live_last_updated_info()
        return context


class RevisionsRevertMixin:
    revision_id_kwarg = "revision_id"
    revisions_revert_url_name = None

    def setup(self, request, *args, **kwargs):
        self.revision_id = kwargs.get(self.revision_id_kwarg)
        super().setup(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self._add_warning_message()
        return super().get(request, *args, **kwargs)

    def get_revisions_revert_url(self):
        return reverse(
            self.revisions_revert_url_name,
            args=[quote(self.object.pk), self.revision_id],
        )

    def get_warning_message(self):
        user_avatar = render_to_string(
            "wagtailadmin/shared/user_avatar.html", {"user": self.revision.user}
        )
        message_string = _(
            "You are viewing a previous version of this %(model_name)s from <b>%(created_at)s</b> by %(user)s"
        )
        message_data = {
            "model_name": capfirst(self.model._meta.verbose_name),
            "created_at": self.revision.created_at.strftime("%d %b %Y %H:%M"),
            "user": user_avatar,
        }
        message = mark_safe(message_string % message_data)
        return message

    def _add_warning_message(self):
        messages.warning(self.request, self.get_warning_message())

    def get_object(self, queryset=None):
        object = super().get_object(queryset)
        self.revision = get_object_or_404(object.revisions, id=self.revision_id)
        return self.revision.as_object()

    def save_instance(self):
        commit = not issubclass(self.model, DraftStateMixin)
        instance = self.form.save(commit=commit)

        self.has_content_changes = self.form.has_changed()

        self.new_revision = instance.save_revision(
            user=self.request.user,
            log_action=True,
            previous_revision=self.revision,
        )

        return instance

    def get_success_message(self):
        message = _(
            "{model_name} '{instance}' has been replaced with version from {timestamp}."
        )
        if self.draftstate_enabled and self.action == "publish":
            message = _(
                "Version from {timestamp} of {model_name} '{instance}' has been published."
            )

            if self.object.go_live_at and self.object.go_live_at > timezone.now():
                message = _(
                    "Version from {timestamp} of {model_name} '{instance}' has been scheduled for publishing."
                )

        return message.format(
            model_name=capfirst(self.model._meta.verbose_name),
            instance=self.object,
            timestamp=self.revision.created_at.strftime("%d %b %Y %H:%M"),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["revision"] = self.revision
        context["action_url"] = self.get_revisions_revert_url()
        return context
