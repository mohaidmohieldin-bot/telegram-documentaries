"""The ImageInput contract guards everything we send to Gemini."""

import pytest
from pydantic import ValidationError

from telegram_documentaries.media import MAX_IMAGE_BYTES, ImageInput


@pytest.mark.parametrize("mime", ["image/jpeg", "image/png", "image/webp", "image/heic"])
def test_supported_images_are_accepted(mime: str) -> None:
    image = ImageInput(data=b"\x89fake-image", mime_type=mime)
    assert image.data == b"\x89fake-image"
    assert image.mime_type == mime


def test_image_at_size_limit_is_accepted() -> None:
    assert len(ImageInput(data=b"x" * MAX_IMAGE_BYTES, mime_type="image/jpeg").data) == (
        MAX_IMAGE_BYTES
    )


def test_empty_image_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ImageInput(data=b"", mime_type="image/jpeg")


def test_oversized_image_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ImageInput(data=b"x" * (MAX_IMAGE_BYTES + 1), mime_type="image/jpeg")


@pytest.mark.parametrize("mime", ["image/gif", "image/svg+xml", "application/pdf", "", "jpeg"])
def test_unsupported_mime_types_are_rejected(mime: str) -> None:
    with pytest.raises(ValidationError):
        ImageInput(data=b"data", mime_type=mime)


def test_repr_does_not_dump_image_bytes() -> None:
    image = ImageInput(data=b"SECRET-PIXELS" * 10, mime_type="image/png")
    assert "SECRET-PIXELS" not in repr(image)
