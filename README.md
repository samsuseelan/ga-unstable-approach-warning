# GA Unstable Approach Warning

Early warning for unstable approaches in general aviation flight training, built on public ADS-B data.

## What this project does

- Loads one hour of OpenSky Network ADS-B data (27 June 2022, 15:00 to 16:00 UTC)
- Keeps aircraft near Daytona Beach International Airport (KDAB) below 1,500 ft
- Removes frozen ADS-B reports
- Cuts each flight track into individual approaches
- Flags approaches with a peak sink rate over 1,000 fpm, based on Flight Safety Foundation stabilized approach criteria
- Adds aircraft type from the OpenSky aircraft database

## First results

- 18 aircraft in the traffic pattern
- 36 approaches from 13 aircraft
- Two Cessna 172S aircraft from the same operator, same hour: one flagged on 3 of 5 approaches, the other on 0 of 5

## Known data limits

- ADS-B reports ground speed, not airspeed. Wind shifts ground speed.
- Barometric altitude uses standard pressure (29.92 inHg), not the local altimeter setting.
- Vertical rate comes in 64 fpm steps. Altitude comes in 25 ft steps.
- Reports arrive about every 10 seconds.
- OpenSky repeats the last known state for up to 300 seconds after coverage loss. This project removes those rows.

## Next steps

- Limits by aircraft type
- Count sustained high sink rate, not only the peak
- More hours and days of data

## Data source

OpenSky Network: https://opensky-network.org
