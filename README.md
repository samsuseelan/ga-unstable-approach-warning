# GA Unstable Approach Warning

Early warning for unstable approaches in general aviation flight training, built on public ADS-B data.

## What this project does

- Loads one hour of OpenSky Network ADS-B data (27 June 2022, 15:00 to 16:00 UTC)
- Keeps aircraft near Daytona Beach International Airport (KDAB) below 1,500 ft
- Removes frozen ADS-B reports
- Cuts each flight track into individual approaches
- Flags approaches with high sink rate, based on Flight Safety Foundation stabilized approach criteria (1,000 fpm)
- Adds aircraft type from the OpenSky aircraft database

## First results

- 18 aircraft in the traffic pattern
- 36 approaches from 13 aircraft
- Peak rule (any single report over 1,000 fpm): 8 flags across 3 aircraft
- Sustained rule (2 or more reports over 1,000 fpm, about 20 seconds): 4 flags, 3 of them on one Cessna 172S
- The other five Cessna 172S aircraft in the same hour: 1 sustained flag in total

The sustained rule cuts false alarms by half. Fewer false alarms means instructors trust the warnings.

## Known data limits

- ADS-B reports ground speed, not airspeed. Wind shifts ground speed.
- Barometric altitude uses standard pressure (29.92 inHg), not the local altimeter setting.
- Vertical rate comes in 64 fpm steps. Altitude comes in 25 ft steps.
- Reports arrive about every 10 seconds.
- OpenSky repeats the last known state for up to 300 seconds after coverage loss. This project removes those rows.
- Results cover one hour at one airport. Not yet enough data for a trained model.

## Next steps

- Limits by aircraft type
- More hours and days of data
- Train a model on approach features

## Data source

OpenSky Network: https://opensky-network.org
