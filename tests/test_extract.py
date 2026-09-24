import geopandas as gpd
import h3
import yaml
from shapely.geometry import Polygon

from src.extract import ROOT, compare_to_reference, run_checks, score_checks

SCHEMA = yaml.safe_load((ROOT / "config" / "schema.yaml").read_text())
START_CELL = "88ad360225fffff"


def make_hexes(n=10):
    """A small set of real level 8 hexes, shaped like the S3 Select output."""
    cells = sorted(h3.grid_disk(START_CELL, 2))[:n]
    rows = []
    for cell in cells:
        lat, lon = h3.cell_to_latlng(cell)
        # h3 gives corners as (lat, lon) but shapely wants (lon, lat)
        corners = [(c_lon, c_lat) for c_lat, c_lon in h3.cell_to_boundary(cell)]
        rows.append(
            {
                "index": cell,
                "centroid_lat": lat,
                "centroid_lon": lon,
                "resolution": 8,
                "geometry": Polygon(corners),
            }
        )
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def test_clean_data_scores_perfectly():
    checks = run_checks(make_hexes(), SCHEMA)
    score, weak_rules, ok = score_checks(checks, SCHEMA)
    assert score == 1.0
    assert weak_rules == []
    assert ok


def test_bad_latitude_only_affects_that_rule():
    hexes = make_hexes()
    hexes.loc[0, "centroid_lat"] = 0
    checks = run_checks(hexes, SCHEMA)
    assert checks["centroid_lat: in range"].mean() == 0.9
    assert checks["centroid_lon: in range"].mean() == 1.0


def test_one_bad_rule_fails_even_when_average_is_high():
    hexes = make_hexes()
    hexes.loc[:1, "centroid_lat"] = 0  # 2 of 10 rows, so this rule drops to 80%
    score, weak_rules, ok = score_checks(run_checks(hexes, SCHEMA), SCHEMA)
    assert score >= SCHEMA["threshold"]
    assert weak_rules == ["centroid_lat: in range"]
    assert not ok


def test_wrong_resolution_is_caught():
    hexes = make_hexes()
    hexes.loc[0, "index"] = h3.cell_to_parent(hexes.loc[0, "index"], 7)
    checks = run_checks(hexes, SCHEMA)
    assert checks["index: valid level 8 hex"].mean() == 0.9


def test_missing_column_fails_every_row():
    hexes = make_hexes().drop(columns="resolution")
    checks = run_checks(hexes, SCHEMA)
    assert checks["resolution: column exists"].mean() == 0


def test_reference_check_passes_on_identical_data():
    hexes = make_hexes()
    assert compare_to_reference(hexes, hexes.copy()) == {"missing": 0, "extra": 0, "shape_mismatches": 0}


def test_reference_check_finds_extra_hex():
    ours = make_hexes()
    ref = make_hexes().iloc[1:]  # reference is missing our first hex
    result = compare_to_reference(ours, ref)
    assert result["extra"] == 1
    assert result["missing"] == 0