"""Section 2: give every service request the level 8 H3 hex it falls in (0 if it has no location),
stop if too many can't be placed in one of the City's hexes, and check the result against sr_hex.csv.gz.

Run from the repo root, after src/extract.py:
    python src/transform.py
"""

import logging
import sys
import time
from pathlib import Path

import geopandas as gpd
import h3
import pandas as pd
import yaml

BASE_URL = "https://cct-ds-code-challenge-input-data.s3.af-south-1.amazonaws.com/"

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "transform.yaml"
HEX_PATH = ROOT / "data" / "hex8.geojson"
OUTPUT_PATH = ROOT / "data" / "sr_with_hex.csv.gz"

RESOLUTION = 8
HEX_COLUMN = "h3_level8_index"
NO_LOCATION = "0"
ID_TYPES = {"notification_number": str, "reference_number": str}

log = logging.getLogger(__name__)


def load_requests():
    """Read sr.csv.gz, keeping the ID columns as text so leading zeros survive."""
    return pd.read_csv(BASE_URL + "sr.csv.gz", index_col=0, dtype=ID_TYPES)


def to_hex(lat, lon):
    """The level 8 hex for one point, or "0" if either coordinate is missing."""
    if pd.isna(lat) or pd.isna(lon):
        return NO_LOCATION
    return h3.latlng_to_cell(lat, lon, RESOLUTION)


def assign_hexes(sr):
    """Return a copy of the requests with a hex column added."""
    sr = sr.copy()
    sr[HEX_COLUMN] = [to_hex(lat, lon) for lat, lon in zip(sr["latitude"], sr["longitude"])]
    return sr


def find_join_failures(sr, city_hexes):
    """True for requests that have a location but whose hex isn't one of the City's."""
    has_location = sr[HEX_COLUMN] != NO_LOCATION
    return has_location & ~sr[HEX_COLUMN].isin(city_hexes)


def compare_to_reference(sr, ref):
    """Return the requests where our hex differs from the one in sr_hex."""
    compare = sr[["notification_number", HEX_COLUMN]].merge(
        ref,
        on="notification_number",
        how="left",
        suffixes=("_ours", "_ref"),
        validate="one_to_one",
    )
    return compare[compare[f"{HEX_COLUMN}_ours"] != compare[f"{HEX_COLUMN}_ref"]]


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("pyogrio").setLevel(logging.WARNING)
    total_start = time.perf_counter()

    config = yaml.safe_load(CONFIG_PATH.read_text())
    max_rate = config["max_join_failure_rate"]

    if not HEX_PATH.exists():
        log.error("%s not found, run python src/extract.py first", HEX_PATH.relative_to(ROOT))
        sys.exit(1)

    start = time.perf_counter()
    sr = load_requests()
    log.info("Loaded %d service requests in %.1fs", len(sr), time.perf_counter() - start)

    start = time.perf_counter()
    sr = assign_hexes(sr)
    no_location = (sr[HEX_COLUMN] == NO_LOCATION).sum()
    with_location = len(sr) - no_location
    log.info("Assigned hexes in %.1fs", time.perf_counter() - start)
    log.info("No location, set to 0: %d (%.1f%% of all requests)", no_location, 100 * no_location / len(sr))

    start = time.perf_counter()
    city_hexes = set(gpd.read_file(HEX_PATH)["index"])
    failed = find_join_failures(sr, city_hexes)
    failure_rate = failed.sum() / with_location if with_location else 1.0
    log.info(
        "Join failures: %d of %d requests with a location (%.4f%%), limit %.2f%% (%.1fs)",
        failed.sum(),
        with_location,
        100 * failure_rate,
        100 * max_rate,
        time.perf_counter() - start,
    )
    for _, row in sr[failed].head(20).iterrows():
        log.warning(
            "  Not in a City hex: %s at (%s, %s) -> %s",
            row["notification_number"],
            row["latitude"],
            row["longitude"],
            row[HEX_COLUMN],
        )

    if failure_rate > max_rate:
        log.error("Join failure rate %.4f%% is above the %.2f%% limit, stopping", 100 * failure_rate, 100 * max_rate)
        sys.exit(1)

    start = time.perf_counter()
    ref = pd.read_csv(BASE_URL + "sr_hex.csv.gz", usecols=["notification_number", HEX_COLUMN], dtype=str)
    mismatches = compare_to_reference(sr, ref)
    log.info(
        "Reference check: %d of %d match sr_hex (%.1fs incl. download)",
        len(sr) - len(mismatches),
        len(sr),
        time.perf_counter() - start,
    )
    if len(mismatches):
        log.warning("%d requests differ from sr_hex, e.g.\n%s", len(mismatches), mismatches.head())

    start = time.perf_counter()
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    sr.to_csv(OUTPUT_PATH, index=False, compression={"method": "gzip", "compresslevel": 1})
    log.info("Saved %s in %.1fs", OUTPUT_PATH.relative_to(ROOT), time.perf_counter() - start)

    log.info("Section 2 done in %.1fs", time.perf_counter() - total_start)


if __name__ == "__main__":
    main()