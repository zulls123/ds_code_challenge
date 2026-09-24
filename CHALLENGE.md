# City of Cape Town Data Engineer Challenge: Sections 1 and 2

This repo is my submission for the Data Engineer track. It pulls the level 8 H3 hexagons out of the City's combined hex file with S3 Select, checks them, then assigns every service request to the level 8 hex it falls in.

The original challenge instructions are in [CHALLENGE.md](CHALLENGE.md).

## How to run it

Tested on Windows with Python 3.13.

```
git clone https://github.com/zulls123/ds_code_challenge.git
cd ds_code_challenge
python -m venv .venv
.venv\Scripts\activate          # on Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

The whole pipeline takes about 30 seconds. All input data and the dummy AWS credentials are downloaded from the City's S3 bucket at runtime, so nothing needs to be set up beforehand. Outputs are written to `data/`.

To run the tests:

```
pytest
```

## What's in the repo

| Path | What it does |
|---|---|
| `main.py` | Runs section 1, then section 2 |
| `src/extract.py` | Section 1: S3 Select extraction and validation |
| `src/transform.py` | Section 2: assigns hexes to service requests and validates |
| `config/schema.yaml` | The rules used for the section 1 schema conformance score |
| `config/transform.yaml` | The join failure threshold for section 2 |
| `tests/` | Unit tests for both sections, using small made-up data (no internet needed) |
| `notebooks/` | My exploration notebooks. Not part of the pipeline |

## Section 1: Extracting level 8 hexes

`city-hex-polygons-8-10.geojson` holds hexes at levels 8, 9 and 10. I use S3 Select to filter to `resolution = 8` on Amazon's side, so only the rows I need come back. S3 still scans the whole 108 MB file, but only about 2 MB is transferred.

S3 Select returns results in chunks, and a record can be split across two chunks, so I join all chunks before splitting them into records.

**Validation.** The result is compared to `city-hex-polygons-8.geojson` on three things: count, hex IDs (in both directions, so missing and extra hexes are both caught) and shapes. Current result: 3,832 hexes, 0 missing, 0 extra, 0 shape differences.

**Schema conformance score.** The rules live in `config/schema.yaml` so they can be changed without touching code. Every rule is applied to every row, each rule gets a pass rate, and the score is the average pass rate across all rules. It passes if the score is at least 0.95.

While testing this, I found a weakness: because the score is an average of 16 rules, one badly broken rule gets hidden by the others. With 75% of latitudes set to 0, the score was still 0.953, a pass. So I added a second condition: every individual rule must also pass at least 90% of rows (`min_rule_pass`). The same broken data now fails, and the log names the rule responsible. There's a test for this case.

## Section 2: Assigning hexes to service requests

The City's hex file is made up of standard H3 level 8 cells, so instead of a point-in-polygon spatial join I calculate each request's hex directly with `h3.latlng_to_cell`. This gives the same answer, is much faster (about 1 to 2 seconds for 941,634 requests), and avoids a spatial join problem where a point exactly on a border can match two polygons and duplicate the request. I then check each hex against the section 1 output to find requests that don't fall in one of the City's hexes.

Requests with no latitude or longitude get `0`, as the challenge asks.

**Validation.** The result is compared with `sr_hex.csv.gz`, matched on `notification_number` (checked to be unique, and the merge refuses duplicates). Current result: 941,634 of 941,634 match.

**Join failure threshold: 0.1%.** A join failure is a request that has coordinates but doesn't fall in any of the City's level 8 hexes. Requests with no coordinates (212,364, or 22.6%) are expected and aren't counted. On the current data only 3 of 729,270 requests fail (0.0004%). They're genuine border cases: two tickets at exactly the same point near the City's eastern edge, and one in Bottelary Smallholdings. They keep their real H3 ID (which is what `sr_hex` does too) and are listed in the log as warnings.

0.1% is roughly 250 times the normal rate, so a few new border cases won't stop the pipeline, but it's strict enough to catch a problem that affects even a small part of the data, like one department sending around 1,000 requests with bad coordinates. Serious problems are caught easily: when I swapped latitude and longitude as a test, close to 100% of requests failed. The trade-off is that a stricter limit could occasionally stop the pipeline for something harmless, like the City's boundary changing. I think that's acceptable, since stopping just means someone takes a look, which is better than bad data flowing through unnoticed.

## Performance

| Step | Time |
|---|---|
| Section 1 total | ~5s |
| Loading service requests | ~6s |
| Assigning hexes | ~1-2s |
| Join failure check | <1s |
| Reference check (incl. download) | ~6s |
| Saving output | ~9s |
| **Whole pipeline** | **~28s** |

Saving the output was originally the slowest step at 30 seconds, because pandas uses the slowest gzip level by default. Switching to `compresslevel=1` brought it down to 9 seconds, and the file went from X MB to Y MB. <!-- TODO: fill in the two file sizes -->

## Things I noticed in the data

- `notification_number` has leading zeros (e.g. `001015950287`), so IDs are read as text. As numbers, the zeros would be lost and they wouldn't match `sr_hex`.
- `reference_number` has blanks, so pandas reads it as a decimal number and shows it in scientific notation, which can lose digits. Also read as text.
- `sr.csv.gz` has an extra unnamed column of row numbers from when it was exported. `sr_hex.csv.gz` doesn't.
- 9,435 requests have no directorate.
- Only 2,082 of the 3,832 level 8 hexes have any service requests, which makes sense given areas like Table Mountain and farmland.

## If I had more time

- Add a check on the share of requests with no location, so a sudden jump (for example from 22% to 60%) would be flagged, since that would also point to an upstream problem.
- Load the settings (thresholds, file names) from one config file rather than having some as constants in the code.
- Save the output as Parquet instead of gzipped CSV, which is smaller, faster and keeps the column types.

## Use of AI

See [AI_log.md](AI_log.md).