# AI usage log

I used Claude (Anthropic) throughout this challenge.

- **Model:** Claude Opus 5.5, through the claude.ai chat interface
- **Tokens:** the claude.ai chat interface doesn't show token counts, so I can't report an exact number

## What I used it for
- Understanding the challenge and new concepts (H3 hexagons, S3 Select, GeoJSON)
- Step-by-step exploration of the data in notebooks
- Drafting the pipeline code, tests and README, which I ran and checked

When explaining the data, the AI also searched the web, including other candidates' public forks of this repo, for known data issues (IDs with leading zeros, requests that fall outside the City's hexes). I checked each of these against the data myself before relying on them.

## Prompts

These are my main prompts, in order. Between them I pasted the output of each notebook cell or script run back into the chat and asked what it meant.

| Prompt | What the AI did | What I did with it |
|---|---|---|
| "what do I need to do for section 0,1,2 for data engineer... give summary" | Summarised the three sections and what's being assessed | Used it to plan the work |
| "ok where do I start... what do I need to install... and what do I need to understand about the data" | Listed the tools and packages, and what to look for in the data | Installed them and set up a virtual environment |
| "how to fork and clone repo" | Step-by-step fork and clone instructions | Forked and cloned the repo |
| "can you explain the data itself... what do the columns mean and how they are relevant?" | Explained each column and which ones matter for sections 1 and 2 | Confirmed the columns when I loaded the data |
| "what is it I have to do exactly? what is the end goal here and how do I get there?" | Described the finished pipeline and a step-by-step plan | Followed the plan |
| "can we start at step 1 and just go step by step together" | Gave one small notebook cell at a time and explained the output I pasted back | Ran each cell and checked the results |
| "what is hex8.shape", "what is this polygon stuff", "what is used and what does the last 3 lines of the code do" | Explained the concepts with small examples | Used the explanations to understand my own code |
| "what do I update the scoring to?" | Explained the final pass rule (overall score plus per-rule floor) | Tested it on real and deliberately broken data |
| "is the failure if something can't be put on the city's map because it doesn't have a latitude and longitude or it's latitude and longitude is swopped? I think will pick 0.1% but you can help me explain it" | Clarified what a join failure is and helped word the reasoning | Chose 0.1% and wrote it into the README |
| Pasted errors ("No module named 'boto3'", "running scripts is disabled") | Explained the cause and the fix | Fixed my environment and added a Windows note to the README |
| "what to call the test files?" | Explained pytest naming | Ran the tests: 16 passed |
| "does my ai log file sound good" | Pointed out details that didn't match what happened | Corrected this log |
| "how to submit" | Explained the submission steps from the challenge README | Followed them |

## How I checked the output
- I ran each step and compared the results with the reference files
- I deliberately broke data to check the validation caught it

## Where I corrected, changed or fixed things
- AI suggested a 1% join failure threshold for section 2. I made it 0.1% to make it stricter, and tested it against swapped latitude and longitude, which failed close to 100% of requests.
- The first section 1 log showed an unexpected "Created 3,832 records" line from another library (pyogrio), so I silenced it by raising that library's log level to warnings only.
- The section 1 script failed with "No module named 'boto3'" because I had two virtual environments and the packages were installed in the wrong one. With AI's help I worked out which one was being used and fixed the setup.
- The first version of the section 1 schema score averaged all the rules. AI pointed out that one badly broken rule could be hidden by the others, and I confirmed it by testing: with 75% of latitudes set to 0 the score was still 0.953, a pass. I added a per-rule floor of 90%, and the same data now fails.
