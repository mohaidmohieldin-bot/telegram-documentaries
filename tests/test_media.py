"""The ImageInput contract guards everything we send to Gemini."""

import pytest
from pydantic import ValidationError

from telegram_documentaries.media import MAX_IMAGE_BYTES, ImageInput, PortraitImage


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


# --- PortraitImage (Converter output) ------------------------------------------------


@pytest.mark.parametrize("mime", ["image/png", "image/jpeg", "image/webp"])
def test_portrait_accepts_generated_image_types(mime: str) -> None:
    assert PortraitImage(data=b"\x89PNG", mime_type=mime).mime_type == mime


@pytest.mark.parametrize("mime", ["image/heic", "image/gif", "text/plain"])
def test_portrait_rejects_other_types(mime: str) -> None:
    with pytest.raises(ValidationError):
        PortraitImage(data=b"x", mime_type=mime)


@pytest.mark.parametrize("data", [b"", b"x" * (MAX_IMAGE_BYTES + 1)])
def test_portrait_rejects_empty_or_oversized(data: bytes) -> None:
    with pytest.raises(ValidationError):
        PortraitImage(data=data, mime_type="image/png")


def test_portrait_repr_does_not_dump_bytes() -> None:
    assert "PIXELS" not in repr(PortraitImage(data=b"PIXELS" * 5, mime_type="image/png"))
