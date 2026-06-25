"""Tests for source display name helper."""

from src.ingestion.document_manager import source_display_name


def test_source_display_name_from_temp_path() -> None:
    path = "/var/folders/xx/T/tmpm7rcd6vz.md"
    assert source_display_name(path) == "tmpm7rcd6vz.md"


def test_source_display_name_from_upload_name() -> None:
    assert source_display_name("travel-plan-洛阳.md") == "travel-plan-洛阳.md"


def test_source_display_name_from_windows_path() -> None:
    assert source_display_name("data\\documents\\guide.txt") == "guide.txt"
