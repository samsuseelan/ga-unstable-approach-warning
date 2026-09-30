# GA Unstable Approach Warning

Early warning for unstable approaches in general aviation flight training, built on public ADS-B data.

## What this project does

- Loads OpenSky Network ADS-B data near Daytona Beach International Airport (KDAB)
- Removes frozen ADS-B reports
- Cuts each flight track into individual approaches
- Drops fragments (approaches starting below 500 ft or with fewer than 5 reports)
- Keeps training aircraft only (Cessna 152/172/182, Piper PA-28, Diamond DA40/DA42)
- Flags approaches with Rule B: two back-to-back reports with sink rate over 1,000 fpm, above 100 ft
- Builds a blind labeling sheet for flight instructor review
- Scores Rule B against instructor labels

## How to run

1. Put the OpenSky hour files (.tar) and the aircraft database (.csv) in a Google Drive folder named `opensky`
2. Open a Colab notebook, paste `full_pipeline.py` and run
3. The script downloads directly from OpenSky when the Drive files are missing

## Results so far

Data: 27 June 2022, 14:00 to 17:00 UTC

- Aircraft near KDAB: 98
- Approaches: 105
- Training aircraft approaches: 90
- Fragments removed: 18
- Approaches for instructor review: 72
- Rule B flags: 1

The one flagged approach: a Cessna 172S starting at 625 ft, 109 knots ground speed, sinking over 1,000 fpm for 30 seconds.

![Flagged vs clean approach](approach_compare.png)

Same aircraft, same session. The flagged approach reached the runway in about half the time of the clean approach.

## Known data limits

- ADS-B reports ground speed, not airspeed. Wind shifts ground speed.
- Barometric altitude uses standard pressure (29.92 inHg), not the local altimeter setting.
- Vertical rate comes in 64 fpm steps. Altitude comes in 25 ft steps.
- Reports arrive about every 10 seconds.
- OpenSky repeats the last known state for up to 300 seconds after coverage loss. This project removes those rows.
- ADS-B identifies the aircraft, not the pilot.
- Rule B checks sink rate only, not speed.
- Results cover three hours at one airport.

## Next steps

- Instructor review of the 72 approaches (in progress)
- Score Rule B against instructor labels
- Add a speed rule by aircraft type
- More days of data

## Data source

OpenSky Network: https://opensky-network.org

Code written with AI coding assistance. Design decisions, data validation and analysis by Sam Suseelan.
