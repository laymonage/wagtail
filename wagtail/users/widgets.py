from warnings import warn

from wagtail.admin.widgets import Button
from wagtail.utils.deprecation import RemovedInWagtail70Warning


class UserListingButton(Button):
    def __init__(self, *args, **kwargs):
        warn(
            "`UserListingButton` is deprecated. "
            "Use `wagtail.admin.widgets.button.Button` "
            "or `wagtail.admin.widgets.button.ListingButton` instead.",
            category=RemovedInWagtail70Warning,
        )
        super().__init__(*args, **kwargs)
