# AI usage log

I used Claude (Anthropic) throughout this challenge.

## What I used it for
- Understanding the challenge and new concepts (H3 hexagons, S3 Select, GeoJSON)
- Step-by-step exploration of the data in notebooks
- Drafting the pipeline code, tests and README, which I ran, checked and edited

## How I checked the output
- I ran each step and compared the results with the reference files
- I deliberately broke data to check the validation caught it

## Where I corrected or changed things
- AI suggested 1% for the threshold for section 2 and I decided to make it 0.1% to make it stricter
- In the first log for section 1, the log showed an unexpected 'Created 3,823 records' line from another library which I removed from the log
- The script for section 2 failed because it didn't pick up the module 'boto3' because I was initially using 2 virtual environments and I tracked down which one was being used to fix the error
- The first version of the schema for section 1 averaged all the rules, and testing with broken data (switching latitude and longitude) showed it could pass with 75% of latitudes wrong, so I added a per-rule floor with AI's assistance