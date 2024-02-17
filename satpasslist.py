from time import sleep, time
from datetime import datetime, timedelta
from urllib.request import urlretrieve
import argparse
import os, os.path, pytz
from difflib import SequenceMatcher
print("Loading pyorbital...")
from pyorbital import orbital


SATNAME_MATCH_RATIO = 0.89





desc = "A command line utility to print out predicted data on weather satellite passes at your location."
parser = argparse.ArgumentParser(description=desc)
parser.add_argument("--lat", help="Latitude of the location we are making predictions for.")
parser.add_argument("--long", help="Longitude of the location we are making predictions for.")
parser.add_argument("--alt", help="Altitude of the location we are making predictions for (in meters). Defaults to sea level (0).", default=0)
parser.add_argument("-t", "--timeframe", help="Time-frame to look for passes in (in hours). Default is 24.", default=24)
parser.add_argument("-e", "--elevationlimit", help="Filter out all passes with max elevations lower than this (in degrees). Default is 0.", default=0)
#parser.add_argument("-u", "--updatetle", help="Manually update weather.txt TLE data from Celestrak.", )
parser.add_argument("-u", "--updatetle", help=argparse.SUPPRESS, action="store_true")
parser.add_argument("Satellite_Name", help="Name of the satellite as it appears in the TLE data", nargs=argparse.REMAINDER, default='')
#To save time, a config file can be used to set all the above arguments at once.
#TODO Implement loading config file to override arguments (or should arguments override config?).
#For now command line arguments are sufficient.


class SatFinder:
    def __init__(self, ANTENNA_GPS_LONG, ANTENNA_GPS_LAT, ANTENNA_GPS_ALT):
        self.satnames = []
        self.ANTENNA_GPS_LONG = ANTENNA_GPS_LONG
        self.ANTENNA_GPS_LAT = ANTENNA_GPS_LAT
        self.ANTENNA_GPS_ALT = ANTENNA_GPS_ALT
        self.updatetle()

    def satlist(self):
        print("Satellites in TLE file:")
        for sat in self.satnames:
            print(sat)

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
            print("%s) %s - %s%s degree MEL pass (%s Long) heading %s in %s - duration %s" % (i, nicestarttime, round(max_location[1]), eastwest, longtext, direction, startimetext, durationtext))

    def passlist(self, satname, time_limit):
        satparams = self.getsatparams(satname)
        if satparams is None:
            return None
        #Horizon limit will affect the start and finish times of the pass and the displayed total duration
        #Do we want to know how long the pass will take with our tracking limits or how long the pass is from horizon to horizon?
        #For now we're counting from the tracking limits.
        passlist = satparams.get_next_passes(datetime.now(pytz.utc), time_limit, self.ANTENNA_GPS_LONG, self.ANTENNA_GPS_LAT, self.ANTENNA_GPS_ALT, horizon=TRACKING_START_ELEVATION) #Next 24 hours
        #Filter out passes with max elevations below our filter limit
        passlist = self.filterpasses(satparams, passlist, PASSLIST_FILTER_ELEVATION)
        if len(passlist) > 0:
            print("Found %s passes in the next %s hours for '%s'." % (len(passlist), time_limit, satname))
        else:
            print("No passes above %sMEL for %s in the next %s hours using current TLE data." % (PASSLIST_FILTER_ELEVATION, satname, time_limit))
            return None
        return passlist

    def getsatparams(self, satname):
        #Check if the satellite exists
        try:
            satparams = orbital.Orbital(satname, tle_file="weather.txt")
        except KeyError:
            closenamecheck = self.findclosestsatname(satname)
            if isinstance(closenamecheck, list):
                print("Couldn't find satellite '%s' in TLE file, did you mean '%s'? Use the 'satlist' command to see a list of available satellites." % (satname, closenamecheck[1]))
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
        return [None, highestmatch[0]]

    def updatesatnames(self):
        print("Updating list of satellites names...")
        self.satnames = []
        with open("weather.txt", "r") as tlefile:
            line = tlefile.readline()
            while line != '':
                if line[0].isdigit() is False:
                    self.satnames.append(line.strip())
                line = tlefile.readline()
        self.satnames.sort()

def updatetle():
    #Check if we have an updated TLE file for weather satellites, if not grab a fresh one.
    #It should be in the same dir this file
    if os.access("weather.txt", os.F_OK) is True:
        #Check age
        curtime = time()
        filemodtime = int(os.stat("weather.txt").st_mtime)
        if curtime - filemodtime < TLE_UPDATE_FREQ_DAYS * 24 * 60 * 60: # 3 days
            print("ARe you suere?")

    print("Downloading weather.txt TLE file...")
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

def main():
    args = parser.parse_args()
    # Check if we are updating the TLE first
    if args.updatetle is True:
        updatetle()

    print("HERE WE ARE")
    print("ARGS")
    #for p in vars(args):
    #        print(" ---------- ")
    #        print(type(p))
    ##        print(p)
    print(args.updatetle)
    print("====================")
    print(" ".join(args.Satellite_Name))




if __name__ == "__main__":
   main()