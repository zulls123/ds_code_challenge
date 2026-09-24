"""Section 1: pull the level 8 H3 hexagons out of the combined 8-10 file with S3 Select,
check them against the City's level 8 file, and score them against config/schema.yaml.

Run from the repo root:
    python src/extract.py
"""

import json
import logging
import numbers
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import boto3
import geopandas as gpd
import h3
import pandas as pd
import yaml

BASE_URL = "https://cct-ds-code-challenge-input-data.s3.af-south-1.amazonaws.com/"
BUCKET = "cct-ds-code-challenge-input-data"
REGION = "af-south-1"
SOURCE_KEY = "city-hex-polygons-8-10.geojson"
REFERENCE_KEY = "city-hex-polygons-8.geojson"

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "config" / "schema.yaml"
OUTPUT_PATH = ROOT / "data" / "hex8.geojson"

TYPES = {"str": str, "float": numbers.Real, "int": numbers.Integral}

log = logging.getLogger(__name__)


def get_s3_client():
    """Log in to S3 with the dummy credentials the City provides."""
    with urlopen(BASE_URL + "ds_code_challenge_creds.json") as f:
        creds = json.load(f)["s3"]

    return boto3.client(
        "s3",
        region_name=REGION,
        aws_access_key_id=creds["access_key"],
        aws_secret_access_key=creds["secret_key"],
    )


def select_hexes(s3, resolution=8):
    """Return the hexes at one resolution as GeoJSON features, plus S3 Select's stats."""
    query = f"SELECT * FROM S3Object[*].features[*] s WHERE s.properties.resolution = {resolution}"

    response = s3.select_object_content(
        Bucket=BUCKET,
        Key=SOURCE_KEY,
        ExpressionType="SQL",
        Expression=query,
        InputSerialization={"JSON": {"Type": "DOCUMENT"}},
        OutputSerialization={"JSON": {"RecordDelimiter": "\n"}},
    )

    chunks = []
    stats = {}
    for event in response["Payload"]:
        if "Records" in event:
            chunks.append(event["Records"]["Payload"])
        elif "Stats" in event:
            stats = event["Stats"]["Details"]

    # a record can be split across two chunks, so join everything before splitting into lines
    raw = b"".join(chunks).decode("utf-8")
    features = [json.loads(line) for line in raw.splitlines() if line]
    return features, stats


def compare_to_reference(extracted, reference):
    """Count hexes that are missing, extra, or a different shape compared to the reference."""
    ours = extracted.set_index("index").sort_index()
    ref = reference.set_index("index").sort_index()

    missing = set(ref.index) - set(ours.index)
    extra = set(ours.index) - set(ref.index)

    common = ours.index.intersection(ref.index)
    same_shape = ours.loc[common].geometry.geom_equals_exact(ref.loc[common].geometry, tolerance=1e-9)

    return {
        "missing": len(missing),
        "extra": len(extra),
        "shape_mismatches": int((~same_shape).sum()),
    }


def run_checks(df, schema):
    """Run every rule in the schema on every row. Returns {rule name: True/False per row}."""
    results = {}

    for name, rules in schema["columns"].items():
        if name not in df.columns:
            results[f"{name}: column exists"] = pd.Series(False, index=df.index)
            continue

        col = df[name]

        if rules.get("required"):
            results[f"{name}: not blank"] = col.notna()

        if name == "geometry":
            results[f"{name}: is a polygon"] = col.geom_type == rules["type"]
            results[f"{name}: valid shape"] = col.is_valid
        else:
            expected = TYPES[rules["type"]]
            results[f"{name}: is {rules['type']}"] = col.map(lambda v: isinstance(v, expected))

        if "min" in rules:
            results[f"{name}: in range"] = col.between(rules["min"], rules["max"])

        if "allowed" in rules:
            results[f"{name}: allowed value"] = col.isin(rules["allowed"])

        if rules.get("unique"):
            results[f"{name}: unique"] = ~col.duplicated(keep=False)

        if "h3_resolution" in rules:
            res = rules["h3_resolution"]
            results[f"{name}: valid level {res} hex"] = col.map(
                lambda v: isinstance(v, str) and h3.is_valid_cell(v) and h3.get_resolution(v) == res
            )

    return results


def score_checks(checks, schema):
    """Average pass rate across all rules, plus any rule that falls below the per-rule floor."""
    score = sum(passed.mean() for passed in checks.values()) / len(checks)
    weak_rules = [name for name, passed in checks.items() if passed.mean() < schema["min_rule_pass"]]
    ok = score >= schema["threshold"] and not weak_rules
    return score, weak_rules, ok


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("pyogrio").setLevel(logging.WARNING)
    total_start = time.perf_counter()

    start = time.perf_counter()
    s3 = get_s3_client()
    features, stats = select_hexes(s3)
    extracted = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    log.info(
        "Extracted %d level 8 hexes in %.1fs (S3 scanned %.0f MB, returned %.1f MB)",
        len(extracted),
        time.perf_counter() - start,
        stats.get("BytesScanned", 0) / 1e6,
        stats.get("BytesReturned", 0) / 1e6,
    )

    start = time.perf_counter()
    reference = gpd.read_file(BASE_URL + REFERENCE_KEY)
    diff = compare_to_reference(extracted, reference)
    log.info(
        "Reference check: %d missing, %d extra, %d shape mismatches (%.1fs incl. download)",
        diff["missing"],
        diff["extra"],
        diff["shape_mismatches"],
        time.perf_counter() - start,
    )

    start = time.perf_counter()
    schema = yaml.safe_load(SCHEMA_PATH.read_text())
    checks = run_checks(extracted, schema)
    for name, passed in checks.items():
        log.info("  %-30s %.1f%%", name, passed.mean() * 100)

    score, weak_rules, schema_ok = score_checks(checks, schema)
    log.info(
        "Schema conformance score %.3f (threshold %s), checked in %.1fs",
        score,
        schema["threshold"],
        time.perf_counter() - start,
    )
    if weak_rules:
        log.warning("Rules below the %.0f%% floor: %s", schema["min_rule_pass"] * 100, ", ".join(weak_rules))

    reference_ok = not any(diff.values())
    if not (reference_ok and schema_ok):
        log.error("Section 1 validation failed")
        sys.exit(1)

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    extracted.to_file(OUTPUT_PATH, driver="GeoJSON")
    log.info(
        "Saved %s. Section 1 done in %.1fs",
        OUTPUT_PATH.relative_to(ROOT),
        time.perf_counter() - total_start,
    )


if __name__ == "__main__":
    main()