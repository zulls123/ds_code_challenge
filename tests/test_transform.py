import pandas as pd
import pytest

from src.transform import HEX_COLUMN, assign_hexes, compare_to_reference, find_join_failures, to_hex

KNOWN_POINT = (-33.872839, 18.522488)  # first request in sr.csv.gz
KNOWN_HEX = "88ad360225fffff"


def test_known_point_gets_known_hex():
    assert to_hex(*KNOWN_POINT) == KNOWN_HEX


@pytest.mark.parametrize("lat, lon", [(None, 18.5), (-33.9, None), (None, None), (float("nan"), 18.5)])
def test_missing_coordinates_give_zero(lat, lon):
    assert to_hex(lat, lon) == "0"


def test_assign_hexes_adds_column_without_changing_input():
    sr = pd.DataFrame({"latitude": [KNOWN_POINT[0], None], "longitude": [KNOWN_POINT[1], None]})
    result = assign_hexes(sr)
    assert list(result[HEX_COLUMN]) == [KNOWN_HEX, "0"]
    assert HEX_COLUMN not in sr.columns


def test_join_failures_ignore_missing_locations():
    sr = pd.DataFrame({HEX_COLUMN: [KNOWN_HEX, "0", "88ad36c629fffff"]})
    failed = find_join_failures(sr, city_hexes={KNOWN_HEX})
    assert list(failed) == [False, False, True]


def test_compare_to_reference_finds_differences():
    ours = pd.DataFrame({"notification_number": ["001", "002"], HEX_COLUMN: [KNOWN_HEX, "0"]})
    ref = pd.DataFrame({"notification_number": ["001", "002"], HEX_COLUMN: [KNOWN_HEX, KNOWN_HEX]})
    mismatches = compare_to_reference(ours, ref)
    assert list(mismatches["notification_number"]) == ["002"]


def test_duplicate_ids_are_refused():
    ours = pd.DataFrame({"notification_number": ["001"], HEX_COLUMN: [KNOWN_HEX]})
    ref = pd.DataFrame({"notification_number": ["001", "001"], HEX_COLUMN: [KNOWN_HEX, "0"]})
    with pytest.raises(pd.errors.MergeError):
        compare_to_reference(ours, ref)