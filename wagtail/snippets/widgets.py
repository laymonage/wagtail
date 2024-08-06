from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from wagtail.admin.staticfiles import versioned_static
from wagtail.admin.widgets import BaseChooser, BaseChooserAdapter
from wagtail.admin.widgets.button import Button
from wagtail.telepath import register


class AdminSnippetChooser(BaseChooser):
    display_title_key = "string"
    classname = "snippet-chooser"
    js_constructor = "SnippetChooser"

    def __init__(self, model, **kwargs):
        self.model = model
        name = self.model._meta.verbose_name
        self.choose_one_text = _("Choose %(object)s") % {"object": name}
        self.choose_another_text = _("Choose another %(object)s") % {"object": name}
        self.link_to_chosen_text = _("Edit this %(object)s") % {"object": name}

        super().__init__(**kwargs)

    def get_chooser_modal_url(self):
        try:
            return reverse(
                self.model.snippet_viewset.chooser_viewset.get_url_name("choose")
            )
        except NoReverseMatch:
            # This most likely failed because the model is not registered as a snippet.
            # Check whether this is the case, and if so, output a more helpful error message
            from .models import get_snippet_models

            if self.model not in get_snippet_models():
                raise ImproperlyConfigured(
                    "AdminSnippetChooser cannot be used on non-snippet model %r"
                    % self.model
                )
            else:
                raise

    @cached_property
    def media(self):
        return forms.Media(
            js=[
                versioned_static("wagtailsnippets/js/snippet-chooser.js"),
            ]
        )


class SnippetChooserAdapter(BaseChooserAdapter):
    js_constructor = "wagtail.snippets.widgets.SnippetChooser"

    @cached_property
    def media(self):
        return forms.Media(
            js=[
                versioned_static("wagtailsnippets/js/snippet-chooser-telepath.js"),
            ]
        )


register(SnippetChooserAdapter(), AdminSnippetChooser)


# This used to extend ListingButton – but since the universal listings design,
# all default buttons are now rendered inside a dropdown. Snippets never had
# separate hooks for top-level buttons and dropdown buttons (as they have no
# "more" button like pages have). As a result, we now extend Button so it
# doesn't have the default CSS classes that ListingButton adds. The class name
# is not changed to avoid unnecessary breaking changes.
class SnippetListingButton(Button):
    pass
