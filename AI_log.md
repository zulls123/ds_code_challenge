# AI usage log

I used Claude (Anthropic) throughout this challenge.

## What I used it for
- Understanding the challenge and new concepts (H3 hexagons, S3 Select, GeoJSON)
- Step-by-step exploration of the data in notebooks
- Drafting the pipeline code, tests and README, which I ran and checked

## How I checked the output
- I ran each step and compared the results with the reference files
- I deliberately broke data to check the validation caught it

## Where I corrected, changed or fixed things
- AI suggested a 1% join failure threshold for section 2. I made it 0.1% to make it stricter, and tested it against swapped latitude and longitude, which failed close to 100% of requests.
- The first section 1 log showed an unexpected "Created 3,832 records" line from another library (pyogrio), so I silenced it by raising that library's log level to warnings only.
- The section 1 script failed with "No module named 'boto3'" because I had two virtual environments and the packages were installed in the wrong one. With AI's help I worked out which one was being used and fixed the setup.
- The first version of the section 1 schema score averaged all the rules. AI pointed out that one badly broken rule could be hidden by the others, and I confirmed it by testing: with 75% of latitudes set to 0 the score was still 0.953, a pass. I added a per-rule floor of 90%, and the same data now fails.