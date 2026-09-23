from collections import OrderedDict

from wagtail.images.models import SourceImageIOError
from wagtail.images.utils import to_svg_safe_spec


class ImageRenditionField:
    """
    A field that generates a rendition with the specified filter spec, and serialises
    details of that rendition. This is a plain Python class with no dependency on
    Django REST Framework, intended for use with Wagtail's ``api_fields`` - in
    particular with the v3 API, which resolves custom serializer fields through a
    compatibility layer while API v2 is still supported.

    Example:
    "thumbnail": {
        "url": "/media/images/myimage.max-165x165.jpg",
        "full_url": "https://media.example.com/media/images/myimage.max-165x165.jpg",
        "width": 165,
        "height": 100,
        "alt": "Image alt text"
    }

    If there is an error with the source image, the dict will only contain a single
    key, "error", indicating this error:

    "thumbnail": {
        "error": "SourceImageIOError"
    }

    A ``None`` source image serialises to ``None``.

    The ``source`` argument accepts the same values as Django REST Framework fields -
    the name of a model attribute, dotted lookups like ``"feed_image__file"``, or
    ``"*"`` for the model instance itself. When the field is instantiated directly
    with an image (as in tests or custom serialisation code), it can be omitted.

    As this is not a Django REST Framework field, it cannot be used with the API v2
    serializers - models that appear in API v2 endpoints should use
    ``wagtail.images.api.fields.ImageRenditionField`` instead.
    """

    # Recognised by Wagtail's API v2 serializer machinery, which filters out
    # writable fields when serialising responses.
    write_only = False

    def __init__(self, filter_spec, preserve_svg=False, source=None):
        self.filter_spec = filter_spec
        self.preserve_svg = preserve_svg
        self.source = source
        self.field_name = None
        # Set to the traversal path when bound to a serializer, mirroring
        # Django REST Framework's Field.bind(); see get_source().
        self.source_attrs = []

    def get_source(self):
        """
        Return the list of attribute names to traverse to reach the source image,
        following Django REST Framework's conventions: the ``source`` argument if
        given, otherwise the bound field name; ``"*"`` maps to no traversal.
        """
        source = self.source if self.source is not None else self.field_name
        if source == "*":
            return []
        return source.split(".")

    def bind(self, field_name, parent=None):
        """
        Bind the field to a serializer, in the same way as Django REST Framework
        fields, so that the field can be shared between API v2 and API v3 usage.
        """
        self.field_name = field_name
        self.source_attrs = self.get_source()

    def get_attribute(self, instance):
        """
        Return the source image for this field, or ``None`` when the source
        attribute is missing or ``None``.
        """
        value = instance
        for attr in self.source_attrs:
            try:
                value = getattr(value, attr)
            except AttributeError:
                return None
            if value is None:
                return None
        return value

    def to_representation(self, image):
        if image is None:
            return None

        try:
            if image.is_svg() and self.preserve_svg:
                filter_spec = to_svg_safe_spec(self.filter_spec)
            else:
                filter_spec = self.filter_spec

            thumbnail = image.get_rendition(filter_spec)

            return OrderedDict(
                [
                    ("url", thumbnail.url),
                    ("full_url", thumbnail.full_url),
                    ("width", thumbnail.width),
                    ("height", thumbnail.height),
                    ("alt", thumbnail.alt),
                ]
            )
        except SourceImageIOError:
            return OrderedDict(
                [
                    ("error", "SourceImageIOError"),
                ]
            )

    def __repr__(self):
        return (
            f"<{type(self).__name__} filter_spec={self.filter_spec!r} "
            f"preserve_svg={self.preserve_svg!r} source={self.source!r}>"
        )
