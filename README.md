```ruby
usage: satpasslist.py [-h] [--satlist] [--lat LAT] [--long LONG] [--alt ALT] [-t TIMEFRAME] [-e ELEVATIONLIMIT] ...
```
```
A command line utility to print out predicted data on weather satellite passes at your location.

positional arguments:
  Satellite_Name        Name of the satellite as it appears in the TLE data

options:
  -h, --help            show this help message and exit
  --satlist             Print out list of satellites in the current TLE data on disk.
  --lat LAT             Latitude of the location we are making predictions for.
  --long LONG           Longitude of the location we are making predictions for.
  --alt ALT             Altitude of the location we are making predictions for (in meters). Defaults to sea level (0).
  -t TIMEFRAME, --timeframe TIMEFRAME
                        Time-frame to look for passes in (in hours). Default is 24.
  -e ELEVATIONLIMIT, --elevationlimit ELEVATIONLIMIT
                        Filter out all passes with max elevations lower than this (in degrees). Default is 0.
```


The 4 required arguments are the latitude, longitude, altitude, and the satellite name.
The latitude, longitude, and altitude are of your current location (or where you want the pass predictions for).

Here's a basic example that lists all passes for NOAA 15 in the next 24 hours (the default time period).
```ruby
python satpasslist.py --lat 34.11843 --long -118.30041 --alt 345 NOAA 15
```
Say we wanted to limit the list to only high elevation passes (say over 50 degrees):
```ruby
python satpasslist.py --lat 34.11843 --long -118.30041 --alt 345 --elevationlimit 50 NOAA 15
```
We can also extend the timeframe we are looking in. Here's all the passes from NOAA 15 in the next 72 hours:
```ruby
python satpasslist.py --lat 34.11843 --long -118.30041 --alt 345 --timeframe 72 NOAA 15
```
Example output looking for NOAA 15 passes over the next 72 hours that have a max elevation of greater than 40 degrees:
```ruby
> python satpasslist.py --lat 34.11843 --long -118.30041 --alt 345 --timeframe 72 --elevationlimit 40 NOAA 15
Found 5 matching passes in the next 72 hours for 'NOAA 15':
1) 2024-02-18 08:07:31 - 42W degree MEL pass (126W Long) heading South in 6 hours 1 minute 35 seconds - duration 14 minutes 45 seconds
2) 2024-02-19 07:41:46 - 75W degree MEL pass (120W Long) heading South in 1 day 5 hours 35 minutes 50 seconds - duration 15 minutes 13 seconds
3) 2024-02-19 18:57:42 - 71W degree MEL pass (121W Long) heading North in 1 day 16 hours 51 minutes 46 seconds - duration 15 minutes 9 seconds
4) 2024-02-20 07:16:10 - 61E degree MEL pass (114W Long) heading South in 2 days 5 hours 10 minutes 14 seconds - duration 15 minutes 11 seconds
5) 2024-02-20 18:32:08 - 65E degree MEL pass (115W Long) heading North in 2 days 16 hours 26 minutes 13 seconds - duration 15 minutes 4 seconds
```

