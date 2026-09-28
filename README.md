# GA Unstable Approach Warning

Early warning for unstable approaches in general aviation flight training, built on public ADS-B data.

## What this project does

- Loads six hours of OpenSky Network ADS-B data (27 June 2022, 13:00 to 19:00 UTC)
- Keeps aircraft near Daytona Beach International Airport (KDAB) below 1,500 ft
- Removes frozen ADS-B reports
- Cuts each flight track into individual approaches
- Flags approaches with high sink rate, based on Flight Safety Foundation stabilized approach criteria (1,000 fpm)
- Adds aircraft type from the OpenSky aircraft database

## Results

- 71 aircraft in the traffic pattern
- 149 approaches
- Rule A, 2 or more reports over 1,000 fpm anywhere in the approach: 6 flags
- Rule B, 2 or more back-to-back reports over 1,000 fpm, 10 seconds apart, above 100 ft: 1 flag

Rule B drops touchdown noise and brief spikes the pilot corrected. The one remaining flag shows a Cessna 172S at 625 ft, 109 knots ground speed, sinking over 1,000 fpm for 30 seconds.

![Flagged vs clean approach](approach_compare.png)

Same aircraft, same session. The flagged approach reached the runway in about 50 seconds, the clean approach in about 100 seconds. On a 3 degree glidepath, sink rate equals about 5 times ground speed, so the clean approach matches a normal glidepath and the flagged approach descended about three times faster.

## Known data limits

- ADS-B reports ground speed, not airspeed. Wind shifts ground speed.
- Barometric altitude uses standard pressure (29.92 inHg), not the local altimeter setting.
- Vertical rate comes in 64 fpm steps. Altitude comes in 25 ft steps.
- Reports arrive about every 10 seconds.
- OpenSky repeats the last known state for up to 300 seconds after coverage loss. This project removes those rows.
- ADS-B identifies the aircraft, not the pilot. A school aircraft flies with several students a day.
- The rules check sink rate only, not speed.
- No expert labels yet, so the number of missed unstable approaches is unknown.

## Next steps

- Speed limits by aircraft type
- Instructor review of approaches to create stable and unstable labels
- More days of data, then a trained model tested against instructor labels

## Data source

OpenSky Network: https://opensky-network.org
