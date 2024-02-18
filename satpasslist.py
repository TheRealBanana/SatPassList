#!/usr/bin/env python3
from time import sleep, time
from datetime import datetime, timedelta
from urllib.request import urlretrieve
import argparse
import os, os.path, pytz
from difflib import SequenceMatcher
print("Loading pyorbital...")
from pyorbital import orbital

#If the sequence matcher thinks the input is over SATNAME_MATCH_RATIO it will assume they are the same
SATNAME_MATCH_RATIO = 0.95
#If the matcher thinks the input match is between 0.95 and 0.75 it assumes you may have misstyped and asks if you meant a similar name.
CLOSE_ENUF_RATIO = 0.75

class SatFinder:
    def __init__(self, ANTENNA_GPS_LONG, ANTENNA_GPS_LAT, ANTENNA_GPS_ALT, PASSLIST_FILTER_ELEVATION, timeframe):
        self.satnames = []
        self.ANTENNA_GPS_LONG = ANTENNA_GPS_LONG
        self.ANTENNA_GPS_LAT = ANTENNA_GPS_LAT
        self.ANTENNA_GPS_ALT = ANTENNA_GPS_ALT
        self.PASSLIST_FILTER_ELEVATION = PASSLIST_FILTER_ELEVATION
        self.timeframe = timeframe
        self.updatesatnames()

    #Takes in a passlist, filters out passes with max elevations under the elevation_limit, and returns the list
    def filterpasses(self, satparams, passlist, elevation_limit):
        filteredpasses = []
        for passdata in passlist:
            _, maxelevation = satparams.get_observer_look(passdata[2], self.ANTENNA_GPS_LONG, self.ANTENNA_GPS_LAT, self.ANTENNA_GPS_ALT)
            if float(maxelevation) < elevation_limit:
                continue
            filteredpasses.append(passdata)
        return filteredpasses

    def printpasses(self, satparams, passlist):
        #Go over the list and pull out some details, then print each one
        for i, passdata in enumerate(passlist):
            #passdata[0] = AOS time
            #passdata[1] = LOS time
            #passdata[2] = max elevation time
            localtz = passdata[0].astimezone()
            nicestarttime = localtz.strftime("%Y-%m-%d %H:%M:%S")
            starttime = localtz - datetime.now().astimezone()
            durationtext = create_time_string((passdata[1] - passdata[0]).total_seconds())
            startimetext = create_time_string(starttime.total_seconds())
            max_location = satparams.get_observer_look(passdata[2], self.ANTENNA_GPS_LONG, self.ANTENNA_GPS_LAT, self.ANTENNA_GPS_ALT)
            eastwest = "E" if max_location[0] < abs(self.ANTENNA_GPS_LONG) else "W"
            longitude = round(satparams.get_lonlatalt(passdata[2])[0]) #Longitude at max elevation
            longtext = "%s%s" % (abs(longitude), "E" if longitude > 0 else "W")
            #Find the direction. Only way I could think of is to look at the change in azimuth angle and if its going down or up
            #One minute ahead in time should be enough to tell for sure what direction we are going, using max elevation as reference
            p2time = passdata[2] + timedelta(minutes=1)
            p2location = satparams.get_observer_look(p2time, self.ANTENNA_GPS_LONG, self.ANTENNA_GPS_LAT, self.ANTENNA_GPS_ALT)
            #More complicated than I thought, I also have to know what side of the circle I'm on
            ns = ["North", "South"]
            if max_location[0] > p2location[0]: #Compare their azimuths
                di = 1
            else:
                di = 0
            #And if we're on the other side of the circle its the opposite
            if max_location[0] < 180:
                di ^= 1
            direction = ns[di]
            print("%s) %s - %s%s degree MEL pass (%s Long) heading %s in %s - duration %s" % (i+1, nicestarttime, round(max_location[1]), eastwest, longtext, direction, startimetext, durationtext))

    def passlist(self, satparams, satname, time_limit):
        #satparams = self.getsatparams(satname)
        if satparams is None:
            return None
        #Horizon limit will affect the start and finish times of the pass and the displayed total duration
        #Do we want to know how long the pass will take with our tracking limits or how long the pass is from horizon to horizon?
        #For now we're counting from the tracking limits.
        passlist = satparams.get_next_passes(datetime.now(pytz.utc), time_limit, self.ANTENNA_GPS_LONG, self.ANTENNA_GPS_LAT, self.ANTENNA_GPS_ALT) #Next 24 hours
        #Filter out passes with max elevations below our filter limit. We filter here instead of using the horizon arg of get_next_passes because
        #the horizon arg modifies the start and end times of the pass based on that horizon limit. We want the horizon limit AND the full pass times.
        passlist = self.filterpasses(satparams, passlist, self.PASSLIST_FILTER_ELEVATION)
        if len(passlist) > 0:
            print("Found %s matching passes in the next %s hours for '%s':" % (len(passlist), time_limit, satname))
        else:
            print("No matching passes above for %s in the next %s hours using current TLE data." % (satname, time_limit))
            return None
        return passlist

    def getsatparams(self, satname):
        #Check if the satellite exists
        try:
            satparams = orbital.Orbital(satname, tle_file="weather.txt")
        except KeyError:
            closenamecheck = self.findclosestsatname(satname)
            if isinstance(closenamecheck, list):
                outstr = "Couldn't find satellite '%s' in TLE file"
                if closenamecheck[1] is not None:
                    outstr += ", did you mean '%s'? " % closenamecheck[1]
                else:
                    outstr +=". "
                outstr += "Use the --satlist argument to see a list of available satellites."
                print(outstr % satname)
                return None
            else:
                print("Returning results for '%s' as '%s' wasn't found in the satellite list." % (closenamecheck, satname))
                satparams = orbital.Orbital(closenamecheck, tle_file="weather.txt")
        except NotImplementedError:
            print("Pyorbital doesn't yet support calculations for geostationary satellites. There are alternative libraries that I have yet to try that may support them.")
            return None
        return satparams

    def findclosestsatname(self, nxsatname):
        #Use the sequence matcher against the satnames list and return if the match is 95% or greater (needs tuning).
        highestmatch = [None, 0]
        for s in self.satnames:
            possiblematch = SequenceMatcher(None, nxsatname.lower(), s.lower()).ratio()
            #keep track of the best match so far
            if possiblematch > highestmatch[1]: highestmatch = [s, possiblematch]
            if possiblematch > SATNAME_MATCH_RATIO:
                return s
        #If we didn't get a good solid match then just return the closest thing along with None so we know its not a good match
        return [None, highestmatch[0] if highestmatch[1] > CLOSE_ENUF_RATIO else None]

    def updatesatnames(self):
        #print("Updating list of satellites names...")
        self.satnames = []
        with open("weather.txt", "r") as tlefile:
            line = tlefile.readline()
            while line != '':
                if line[0].isdigit() is False:
                    self.satnames.append(line.strip())
                line = tlefile.readline()
        self.satnames.sort()

def updatetle():
    #Don't really need to update if its under 2 days old.
    if os.access("weather.txt", os.F_OK) is True:
        #Check age
        curtime = time()
        filemodtime = int(os.stat("weather.txt").st_mtime)
        if curtime - filemodtime < 2 * 24 * 60 * 60: # 2 days
            yn = '.'
            while yn not in "yn":
                yn = input("Current TLE data is less than 48-hours old, are you sure you want to update? (Y/N): ").lower()
            if yn == "n":
                return
    print("Downloading latest weather satellite TLE data from Celestrak.org...")
    urlretrieve("https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle", "weather.txt")

def create_time_string(seconds_total):
    days = int(seconds_total/(60*60*24))
    hours = int(seconds_total%(60*60*24)/(60*60))
    minutes = int(seconds_total%(60*60*24)%(60*60)/60)
    seconds = int(seconds_total%(60*60*24)%(60*60)%60)
    timestring = ""
    if days > 0:
        timestring += "%s day " % days
        if days > 1: timestring = timestring[:-1] + "s" + timestring[-1:]
    if hours > 0:
        timestring += "%s hour " % hours
        if hours > 1: timestring = timestring[:-1] + "s" + timestring[-1:]
    if minutes > 0:
        timestring += "%s minute " % minutes
        if minutes > 1: timestring = timestring[:-1] + "s" + timestring[-1:]
    if seconds > 0:
        timestring += "%s second" % seconds
        if seconds > 1: timestring += "s"
    return timestring

def printsatlist():
    satnames = []
    with open("weather.txt", "r") as tlefile:
        line = tlefile.readline()
        while line != '':
            if line[0].isdigit() is False:
                satnames.append(line.strip())
            line = tlefile.readline()
    satnames.sort()
    #Make it fancy lookin
    linestrs = [""]
    #Approx limit for each line
    widthlimit = 80
    i = 0
    for s in satnames:
        linestrs[i] += s + " "*3
        if len(linestrs[i]) > widthlimit:
            i += 1
            linestrs.append("")
    print("Available satellites:")
    for s in linestrs: print(s)


desc = "A command line utility to print out predicted data on weather satellite passes at your location."
parser = argparse.ArgumentParser(description=desc)
parser.add_argument("--satlist", help="Print out list of satellites in the current TLE data on disk.", action="store_true")
parser.add_argument("--lat", help="Latitude of the location we are making predictions for.", type=float)
parser.add_argument("--long", help="Longitude of the location we are making predictions for.", type=float)
parser.add_argument("--alt", help="Altitude of the location we are making predictions for (in meters). Defaults to sea level (0).", default=0, type=float)
parser.add_argument("-t", "--timeframe", help="Time-frame to look for passes in (in hours). Default is 24.", default=24, type=int)
parser.add_argument("-e", "--elevationlimit", help="Filter out all passes with max elevations lower than this (in degrees). Default is 0.", default=0, type=int)
#parser.add_argument("-u", "--updatetle", help="Manually update weather.txt TLE data from Celestrak.", )
parser.add_argument("-u", "--updatetle", help=argparse.SUPPRESS, action="store_true")
parser.add_argument("Satellite_Name", help="Name of the satellite as it appears in the TLE data", nargs=argparse.REMAINDER, default='')
#To save time, a config file can be used to set all the above arguments at once.
#TODO Implement loading config file to override arguments (or should arguments override config?).
#For now command line arguments are sufficient.

def main():
    args = parser.parse_args()
    # Check if we are updating the TLE first
    if args.updatetle is True:
        updatetle()
        exit(0)

    if args.satlist is True:
        printsatlist()
        exit(0)

    #Ok not in TLE update mode or satlist mode, so make sure we have what we need.
    #TODO I would guess this is where we would load data from the config file when we do that

    #The 3 bare minimum required arguments are the latitude, longitude, and sat name.
    if args.lat is None:
        print("You must include your latitude (--lat) to get any pass information. See --help for more information.")
        exit(1)
    if args.long is None:
        print("You must include your longitude (--long) to get any pass information. See --help for more information.")
        exit(1)
    if len(args.Satellite_Name) == 0:
        print("You must give the name of a satellite as the last argument. See --help for more information or --satlist for a list of satellites.")
        exit(1)
    #To save headaches later, we'll be using this from now on
    satname = " ".join(args.Satellite_Name)

    #Basic sanity checks on all the arguments we will be using: lat long alt timeframe elevationlimit Satellite_Name
    if abs(float(args.lat)) > 90:
        print("Invalid entry for latitude: '%s'. Valid values are between -90 and 90." % args.lat)
        exit(1)
    if abs(float(args.long)) > 180:
        print("Invalid entry for longitude: '%s'. Valid values are between -180 and 180." % args.long)
        exit(1)
    #Nothing valid on earth should ever be outside those values (or even near either).
    if not -500 < float(args.alt) < 9000:
        print("Invalid entry for altitude: '%s'. This should be your altitude in meters, recheck your altimeter." % args.alt)
    #Just because we should probably set a limit, we're limiting the timeframe to a max of 30 days (720 hours)
    if not 0 < args.timeframe < 721:
        print("Invalid timeframe period, this should be a positive integer value (Default is 24).")
        exit(1)

    #Ok so all values except the satellite name have been validated as been somewhat sane, we can get a SatFinder obj running.
    satfind = SatFinder(args.long, args.lat, args.alt/1000, args.elevationlimit, satname)

    #Now we can validate the sat name at the same time we get satparams
    satparams = satfind.getsatparams(satname)
    passes = satfind.passlist(satparams, satname, args.timeframe)
    if passes is None:
        exit(0)
    satfind.printpasses(satparams, passes)

if __name__ == "__main__":
   main()