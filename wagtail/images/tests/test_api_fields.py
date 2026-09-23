from django.test import TestCase

from wagtail.images.api import ImageRenditionField
from wagtail.images.api.fields import ImageRenditionField as LegacyImageRenditionField
from wagtail.images.utils import to_svg_safe_spec

from .utils import (
    Image,
    get_test_bad_image,
    get_test_image_file,
    get_test_image_file_svg,
)


class TestImageRenditionField(TestCase):
    def setUp(self):
        self.image = Image.objects.create(
            title="Test image",
            file=get_test_image_file(),
        )

    def test_api_representation(self):
        rendition = self.image.get_rendition("width-400")
        representation = LegacyImageRenditionField("width-400").to_representation(
            self.image
        )
        self.assertEqual(
            set(representation.keys()), {"url", "full_url", "width", "height", "alt"}
        )
        self.assertEqual(representation["url"], rendition.url)
        self.assertEqual(representation["full_url"], rendition.full_url)
        self.assertEqual(representation["width"], rendition.width)
        self.assertEqual(representation["height"], rendition.height)
        self.assertEqual(representation["alt"], rendition.alt)


class Holder:
    """
    A stand-in for a model with a ``feed_image`` foreign key, for testing
    ``source`` resolution without going through a serializer.
    """

    def __init__(self, feed_image=None):
        self.feed_image = feed_image


class TestImageRenditionFieldWithoutDRF(TestCase):
    """
    Tests for the Django REST Framework-free replacement field exposed as
    ``wagtail.images.api.ImageRenditionField``.
    """

    def setUp(self):
        self.image = Image.objects.create(
            title="Test image",
            file=get_test_image_file(),
        )

    def test_api_representation_matches_legacy_field(self):
        legacy = LegacyImageRenditionField("width-400").to_representation(self.image)
        representation = ImageRenditionField("width-400").to_representation(self.image)
        self.assertEqual(representation, legacy)
        self.assertEqual(
            set(representation.keys()), {"url", "full_url", "width", "height", "alt"}
        )
        rendition = self.image.get_rendition("width-400")
        self.assertEqual(representation["url"], rendition.url)
        self.assertEqual(representation["full_url"], rendition.full_url)
        self.assertEqual(representation["width"], rendition.width)
        self.assertEqual(representation["height"], rendition.height)
        self.assertEqual(representation["alt"], rendition.alt)

    def test_null_image_representation(self):
        representation = ImageRenditionField("width-400").to_representation(None)
        self.assertIsNone(representation)

    def test_source_resolution(self):
        field = ImageRenditionField("width-400", source="feed_image")
        field.bind("feed_image_thumbnail")
        representation = field.to_representation(
            field.get_attribute(Holder(self.image))
        )
        self.assertEqual(
            representation,
            ImageRenditionField("width-400").to_representation(self.image),
        )

    def test_source_none_returns_none(self):
        field = ImageRenditionField("width-400", source="feed_image")
        field.bind("feed_image_thumbnail")
        self.assertIsNone(field.get_attribute(Holder()))
        self.assertIsNone(field.to_representation(field.get_attribute(Holder())))

    def test_source_missing_attribute_returns_none(self):
        field = ImageRenditionField("width-400", source="feed_image")
        field.bind("feed_image_thumbnail")
        self.assertIsNone(field.get_attribute(object()))

    def test_source_wildcard(self):
        field = ImageRenditionField("width-400", source="*")
        field.bind("thumbnail")
        self.assertIs(field.get_attribute(self.image), self.image)
        representation = field.to_representation(field.get_attribute(self.image))
        self.assertEqual(representation["alt"], self.image.default_alt_text)

    def test_bind_defaults_to_field_name(self):
        field = ImageRenditionField("width-400")
        field.bind("feed_image")
        self.assertEqual(field.source_attrs, ["feed_image"])
        self.assertIs(field.get_attribute(Holder(self.image)), self.image)

    def test_preserve_svg(self):
        svg_image = Image.objects.create(
            title="Test SVG image",
            file=get_test_image_file_svg(),
        )
        filter_spec = "width-400|jpegquality-80"

        field = ImageRenditionField(filter_spec, preserve_svg=True)
        representation = field.to_representation(svg_image)
        expected = svg_image.get_rendition(to_svg_safe_spec(filter_spec))
        self.assertEqual(representation["url"], expected.url)

        # Without preserve_svg, the full filter spec is used as-is.
        field = ImageRenditionField(filter_spec)
        representation = field.to_representation(svg_image)
        expected = svg_image.get_rendition(filter_spec)
        self.assertEqual(representation["url"], expected.url)

    def test_source_image_io_error(self):
        bad_image = get_test_bad_image()
        bad_image.save()
        representation = ImageRenditionField("width-400").to_representation(bad_image)
        self.assertEqual(representation, {"error": "SourceImageIOError"})
