#!/usr/bin/env python3
from time import time
from datetime import datetime, timedelta
from urllib.request import urlretrieve
import argparse
import os, os.path, pytz, warnings
from difflib import SequenceMatcher
orbital = None

#If the sequence matcher thinks the input is over SATNAME_MATCH_RATIO it will assume they are the same
SATNAME_MATCH_RATIO = 0.90
#If the matcher thinks the input match is between 0.95 and 0.75 it assumes you may have misstyped and asks if you meant a similar name.
CLOSE_ENUF_RATIO = 0.75

#need this later for a couple file loading things
RUNFOLDER = os.path.dirname(__file__)
CONFPATH = os.path.join(RUNFOLDER, "satpasslist.conf")
TLEFILEPATH = os.path.join(RUNFOLDER, "weather.txt")
TLEURL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle"


#Suppress warnings in the pyorbital module about timezone representations for numpy datetime object
warnings.filterwarnings('ignore')

class SatFinder:
    def __init__(self, ANTENNA_GPS_LONG, ANTENNA_GPS_LAT, ANTENNA_GPS_ALT, PASSLIST_FILTER_ELEVATION):
        self.satnames = []
        self.ANTENNA_GPS_LONG = ANTENNA_GPS_LONG
        self.ANTENNA_GPS_LAT = ANTENNA_GPS_LAT
        self.ANTENNA_GPS_ALT = ANTENNA_GPS_ALT
        self.PASSLIST_FILTER_ELEVATION = PASSLIST_FILTER_ELEVATION
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

    #TODO I would definitely appreciate a way to filter out eastern or western passes at certain times.
    #Would be easy enough to do that here
    def printpasses(self, passlist):
        #Our passdata is a list of passes with our satname and satparams attached to the end
        for i, passdata in enumerate(passlist):
            #passdata[0] = AOS time
            #passdata[1] = LOS time
            #passdata[2] = max elevation time
            #passdata[-2]= satname
            #passdata[-1]= satparams
            satname = passdata[-2]
            satparams = passdata[-1]
            localtz = passdata[0].astimezone()
            nicestarttime = localtz.strftime("%Y-%m-%d %H:%M:%S")
            starttime = localtz - datetime.now().astimezone()
            durationtext = create_time_string((passdata[1] - passdata[0]).total_seconds())
            startimetext = create_time_string(starttime.total_seconds())
            max_location = satparams.get_observer_look(passdata[2], self.ANTENNA_GPS_LONG, self.ANTENNA_GPS_LAT, self.ANTENNA_GPS_ALT)
            longitude = round(satparams.get_lonlatalt(passdata[2])[0]) #Longitude at max elevation
            longtext = "%s%s" % (abs(longitude), "E" if longitude > 0 else "W")
            eastwest = "W" if longitude < self.ANTENNA_GPS_LONG else "E"
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
            print("%s) %s\t- %s - %s%s degree MEL pass (%s Long) heading %s in %s - duration %s" % (i+1, satname, nicestarttime, round(max_location[1]), eastwest, longtext, direction, startimetext, durationtext))

    def passlist(self, satparams, satname, time_limit, starttime):
        if satparams is None:
            return None
        if starttime == 0: # Zero means use the current date/time
            starttime_dt = datetime.now(pytz.utc)
        else: #Convert unix epoch time to UTC datetime object
            starttime_dt = datetime.fromtimestamp(starttime, tz=pytz.utc)

        #Horizon limit will affect the start and finish times of the pass and the displayed total duration
        #Because this is app isn't connected to any tracking apps, we want to display the full pass information from a 0 degree horizon.
        passlist = satparams.get_next_passes(starttime_dt, time_limit, self.ANTENNA_GPS_LONG, self.ANTENNA_GPS_LAT, self.ANTENNA_GPS_ALT) #Next 24 hours
        #Filter out passes with max elevations below our filter limit. We filter here instead of using the horizon arg of get_next_passes because
        #the horizon arg modifies the start and end times of the pass based on that horizon limit. We want the horizon limit AND the full pass times.
        passlist = self.filterpasses(satparams, passlist, self.PASSLIST_FILTER_ELEVATION)
        if len(passlist) > 0:
            print("Found %s matching pass%s in the next %s hours for '%s'." % (len(passlist), "es" if len(passlist) > 1 else "", time_limit, satname))
        else:
            print("No matching passes for %s found in the next %s hours using current TLE data." % (satname, time_limit))
            return None
        return passlist

    def getsatparams(self, satname):
        #Check if the satellite exists
        try:
            satparams = orbital.Orbital(satname, tle_file=TLEFILEPATH)
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
                satparams = orbital.Orbital(closenamecheck, tle_file=TLEFILEPATH)
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
        self.satnames = getsatnamelist()

def updatetle(autocheck=False):
    #Don't really need to update if its under 2 days old.
    if os.access(TLEFILEPATH, os.F_OK) is True:
        #File exists and we're not autochecking
        if autocheck is False:
            #Check age
            curtime = time()
            filemodtime = int(os.stat(TLEFILEPATH).st_mtime)
            if curtime - filemodtime < 2 * 24 * 60 * 60: # 2 days
                yn = '.'
                while yn not in "yn":
                    yn = input("Current TLE data is less than 48-hours old, are you sure you want to update? (Y/N): ").lower()
                if yn == "n":
                    return
        #File exists and we are autochecking.
        else:
           #App start autocheck, so download if its older than a week, but otherwise do nothing
           if time() - int(os.stat(TLEFILEPATH).st_mtime) < 7 * 24 * 60 * 60: # 7 days
                return
    print("Downloading latest weather satellite TLE data from Celestrak.org...")
    try:
        urlretrieve(TLEURL, TLEFILEPATH)
    except Exception as e:
        print("Failed to download weather.txt from celestrak.org. Reason: \n%s" % str(e))
    else:
        print("Successfully downloaded a fresh weather.txt from celestrak.org")

def create_time_string(seconds_total):
    days = int(seconds_total/86400)
    hours = int((seconds_total%86400)/3600)
    minutes = int((seconds_total%86400%3600)/60)
    seconds = int(seconds_total%86400%3600%60)
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
    timestring = timestring.strip()
    return timestring


def getsatnamelist():
    satnames = []
    with open(TLEFILEPATH, "r") as tlefile:
        line = tlefile.readline()
        while line != '':
            if line[0].isdigit() is False:
                satnames.append(line.strip())
            line = tlefile.readline()
    satnames.sort()
    return satnames

def printsatlist():
    satnames = getsatnamelist()
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
parser.add_argument("--alt", help="Altitude of the location we are making predictions for (in meters). Defaults to sea level (0).", type=float)
parser.add_argument("-t", "--timeframe", help="Time-frame to look for passes in (in hours). Default is 24.", type=int)
parser.add_argument("-e", "--elevationlimit", help="Filter out all passes with max elevations lower than this (in degrees). Default is 0.", type=int)
parser.add_argument("-s", "--starttime", help="Sets the start date and time for the generated satellite pass schedule. This value is in seconds since the unix epoch. Only dates between year 2000 and 2100 are accepted. Default value is the current time and date.", type=int)
parser.add_argument("-u", "--updatetle", help=argparse.SUPPRESS, action="store_true")
parser.add_argument("Satellite_Name", help="Name of the satellite as it appears in the TLE data. Multiple satellite names can be given by separating them with a comma (,).", nargs=argparse.REMAINDER)
#To save time, a config file can be used to set all the above arguments at once.

def load_config():
    #We're going to return a dictionary with our settings in it, and it will be a combination of the config file and
    #command-line arguments. We'll load the config file first, then overwrite those with any command-line arguments.
    #Moving default values here instead of in parser.add_argument because default values not given as args will still
    #override config values.
    config = {
        "satlist": False,
        "lat": None,
        "long": None,
        "alt": 0,
        "timeframe": 24,
        "elevationlimit": 0,
        "starttime": 0, # 0 means current time/date, anything else is considered a unix epoch format.
        "updatetle": False,
        "Satellite_Name": ""
    }
    #We are assuming the config file is in the same directory as this .py file. Running from a folder in your PATH var and loading
    #the config as "./satpasslist.conf" tries to load it from the dir the user invoked the py from, not the folder the py is in.
    #Easy peasy to fix, just do an os.path.dirname() (or take the first element from os.path.split()) and combine that with the conf
    #file name.
    if os.access(CONFPATH, os.F_OK):
        with open(CONFPATH, "r") as configfile:
            line = '.'
            while line != '':
                line = configfile.readline().strip()
                if len(line) == 0 or line[0] == "#": continue
                key = line[:line.index("=")]
                value = line[line.index("=")+1:]
                if len(value) == 0 or value is None: continue
                #Ok a few values in the config need to be made into floats or ints. Handle that here.
                #Satellite_Name breaks things so dont mess with it
                if key != "Satellite_Name":
                    tfunc = parser._option_string_actions["--%s" % key].type
                    value = tfunc(value)
                config[key] = value # Will fail if you misspell anything
    #Now go through command-line args and override the config values with anything given
    args = parser.parse_args()
    for k in config.keys():
        val = getattr(args, k)
        if val is None:
            continue
        #Handle sat name
        if k == "Satellite_Name":
            if len(val) > 0:
                val = " ".join(val)
            else:
                continue
        config[k] = val

    return config


def main():
    global orbital
    args = load_config()
    # Check if we are updating the TLE first
    if args["updatetle"] is True:
        updatetle()
        exit(0)

    #Now manually run the TLE downloader. If its not there or older than 7 days it will grab a new one
    #The --satlist arg needs the TLE file to be there, so we need to autocheck that first. 
    updatetle(autocheck=True)

    if args["satlist"] is True:
        printsatlist()
        exit(0)
    
    #Ok not in TLE update mode or satlist mode, so make sure we have what we need.
    #The 3 bare minimum required arguments are the latitude, longitude, and sat name.
    if args["lat"] is None:
        print("You must include your latitude (--lat) to get any pass information. See --help for more information.")
        exit(1)
    if args["long"] is None:
        print("You must include your longitude (--long) to get any pass information. See --help for more information.")
        exit(1)
    if len(args["Satellite_Name"]) == 0:
        print("You must give the name of a satellite as the last argument. See --help for more information or --satlist for a list of satellites.")
        exit(1)

    #Basic sanity checks on all the arguments we will be using: lat long alt timeframe elevationlimit starttime Satellite_Name
    if abs(float(args["lat"])) > 90:
        print("Invalid entry for latitude: '%s'. Valid values are between -90 and 90." % args["lat"])
        exit(1)
    if abs(float(args["long"])) > 180:
        print("Invalid entry for longitude: '%s'. Valid values are between -180 and 180." % args["long"])
        exit(1)
    #Nothing valid on earth should ever be outside those values (or even near either).
    if not -500 < float(args["alt"]) < 9000:
        print("Invalid entry for altitude: '%s'. This should be your altitude in meters, recheck your altimeter." % args["alt"])
    #Just because we should probably set a limit, we're limiting the timeframe to a max of 30 days (720 hours)
    if not 0 < args["timeframe"] < 721:
        print("Invalid timeframe period, this should be a positive integer value (Default is 24).")
        exit(1)
    if not 0 <= args["elevationlimit"] <= 90:
        print("Invalid elevation limit, this value should be between 0 and 90 degrees.")
        exit(1)
    #Accepting dates between year 2000 and 2100 is still way too wide but at least keeps everything from crashing
    #Again, starttime 0 is current date/time.
    if not args["starttime"] == 0 and not 946684800 <= args["starttime"] <= 4102444800:
        print("Invalid unix epoch timestamp given for the starttime. Only dates between year 2000-2100 are accepted. Millisecond timestamps are not supported.")
        exit(1)

    #Takes a bit of time to load the library, so for help args and satlist/updatetle we don't need it so we can save time
    print("Loading pyorbital...")
    from pyorbital import orbital

    #Ok so all values except the satellite name have been validated as being somewhat sane, we can get a SatFinder obj running.
    #Convert Satellite_Name into a list, which will separate values at the comma and remove whitespace at the ends.
    satnamelist = [s.strip() for s in args["Satellite_Name"].split(",") if len(s) > 0]
    satfind = SatFinder(args["long"], args["lat"], args["alt"]/1000, args["elevationlimit"]) #pyorbital takes altitude in km, but we like to use meters so divide by 1000.
    satpassdata = []
    #each item in the list is the tuple returned from get_next_passes() with the satname and satparams attached to the end
    for satname in satnamelist:
        #Now we can validate the sat name at the same time we get satparams
        satparams = satfind.getsatparams(satname)
        #Technically passlist() will just return none when we give it a nonetype satparams, so it will just exit one function call later
        #But why not do it here properly.
        if satparams is None:
            continue
        #Using the internal satellite names in satparams instead of the supplied name incase we had to correct a typo
        satname = satparams.satellite_name
        passes = satfind.passlist(satparams, satname, args["timeframe"], args["starttime"])
        if passes is None:
            continue
        #Annotate the passes list with the satname and satparams
        apasses = []
        for p in passes:
            apasses.append((*p, satname, satparams))
        satpassdata += apasses
    if len(satpassdata) == 0:
        exit(0)
    #Because the first index of each tuple is a datetime object, we can just do a simple sort() on our list to put it in chronological order
    satpassdata.sort()
    satfind.printpasses(satpassdata)


if __name__ == "__main__":
   main()