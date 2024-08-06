```ruby
usage: satpasslist.py [-h] [--satlist] [--lat LAT] [--long LONG] [--alt ALT] [-t TIMEFRAME] [-e ELEVATIONLIMIT] [-s STARTTIME] ...
```
```
A command line utility to print out predicted data on weather satellite passes at your location.

positional arguments:
  Satellite_Name        Name of the satellite as it appears in the TLE data. Multiple satellite names can be given by separating them with a comma (,).

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
  -s STARTTIME, --starttime STARTTIME
                        Sets the start date and time for the generated satellite pass schedule. This value is in seconds since the unix epoch. Only dates between year 2000 and 2100 are accepted. Default value is the current time and date.
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
You can also search for multiple satellites at once by separating their names with a comma:
```ruby
python satpasslist.py --lat 34.11843 --long -118.30041 --alt 345 NOAA 15, NOAA 18, NOAA 19
Loading pyorbital...
Found 2 matching passes in the next 24 hours for 'NOAA 15'.
Found 2 matching passes in the next 24 hours for 'NOAA 18'.
Found 2 matching passes in the next 24 hours for 'NOAA 19'.
1) NOAA 15      - 2024-05-03 08:39:10 - 76W degree MEL pass (120W Long) heading South in 7 hours 29 minutes 13 seconds - duration 15 minutes 5 seconds
2) NOAA 19      - 2024-05-03 10:08:06 - 67E degree MEL pass (115W Long) heading South in 8 hours 58 minutes 9 seconds - duration 15 minutes 39 seconds
3) NOAA 18      - 2024-05-03 11:27:16 - 55E degree MEL pass (113W Long) heading South in 10 hours 17 minutes 19 seconds - duration 15 minutes 28 seconds
4) NOAA 15      - 2024-05-03 19:55:04 - 72W degree MEL pass (121W Long) heading North in 18 hours 45 minutes 7 seconds - duration 15 minutes 7 seconds
5) NOAA 19      - 2024-05-03 21:30:25 - 86E degree MEL pass (118W Long) heading South in 20 hours 20 minutes 28 seconds - duration 15 minutes 36 seconds
6) NOAA 18      - 2024-05-03 22:49:20 - 71E degree MEL pass (116W Long) heading North in 21 hours 39 minutes 23 seconds - duration 15 minutes 44 seconds
```
The command-line arguments can also be set permanently in the config file so they don't have to be supplied at runtime. Options given on the command-line will override anything in the config file.
