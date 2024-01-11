#!/bin/env python

# adrepl -- AxiDraw frontend.
# A simple REPL for controlling the AxiDraw

# Issues:
# * With old (pre 3.8?) software, 'dist' was spelled 'walk_dist' --
#   this code only reads both from config files -- dist overrides walk_dist

# NOTES:
# * options get reset by plot_setup: the docs says they can be set 
#   between plot_setup and plot run.  So we need to keep an options 
#   object, and apply them all before each plot_run (or after plot_setup).
# * developed and tested on Raspberry Pi (orig B+) running Raspbian bullseye.
# * requirements:
#   - python3.5
#   - modules as below
# * All distances are handled in inches, converting to and from millimetres
#   for display and input if required.

# TODO
# * ? use setattr/getattr instead of going via __dict__ in various places?  -- didn't work.
# * "Command unavailable while in preview mode" -- if preview is True , some plot_run things won't work!!!!
#    -- so, make preview an alternative command to plot.
#   - simplify model
# * interactive mode for some things??
# * loop to print many copies -- rather than built-in copy thing. i.e. ignore copies in options -- don't tell ad about it, make sure it's always 1
#   -- pause between coppies.  beep?
# * maybe: check ad.errors.code at end of REPL (after every command)
# * cmd to draw a reg mark
# * don't change options such as mode -- e.g. when doing align, restore mode to what it was before,
#   - otherwise saved config will become a meaningless jumble.
# * turn motors off after a delay (or does the firmware do that?)
# * stream SVG file to plotter instead of ... the library handles all that.
# * fancy dialling in of 2 or 3 points on the substrate, and transforming whole plot to fit
# * "dist" never gets changed -- remove from visible options?

import atexit
from datetime import datetime
import os
import signal
import sys
# Use readline if available:
try:
    import readline
except ImportError:
    readline = None
from curtsies  import Input
from pyaxidraw import axidraw
from axicli    import utils as acutils

# Globals:
aligned = False     # True if we know where the head is.
alignX = None       # Head position if aligned in inches.
alignY = None
outputFilename = 'none'
plotRunning = False # True while plotting a file

# 'Constants'
version = "0.1.4"   # adrepl version
configDir = "~/.config/adrepl/"
configFile = "axidraw_conf.py"
defaultConfigFile = os.path.expanduser(os.path.join(configDir, configFile))
histFile = "history.txt"
defaultHistFile = os.path.expanduser(os.path.join(configDir, histFile))
histFileSize = 1000
origDir = os.getcwd()
# max values depend on model -- these numbers from standard axidraw_conf.py:
# model 1:
# x_travel_default = 11.81 # AxiDraw V2, V3, SE/A4: X.    Default: 11.81 in (300 mm)
# y_travel_default = 8.58  # AxiDraw V2, V3, SE/A4: Y.    Default:  8.58 in (218 mm)
# model 2:
# x_travel_V3A3 = 16.93    # V3/A3 and SE/A3: X           Default: 16.93 in (430 mm)
# y_travel_V3A3 = 11.69    # V3/A3 and SE/A3: Y           Default: 11.69 in (297 mm)
# model 3:
# x_travel_V3XLX = 23.42   # AxiDraw V3 XLX: X            Default: 23.42 in (595 mm)
# y_travel_V3XLX = 8.58    # AxiDraw V3 XLX: Y            Default:  8.58 in (218 mm)
# model 4:
# x_travel_MiniKit = 6.30  # AxiDraw MiniKit: X           Default:  6.30 in (160 mm)
# y_travel_MiniKit = 4.00  # AxiDraw MiniKit: Y           Default:  4.00 in (101.6 mm)
# model 5:
# x_travel_SEA1 = 34.02    # AxiDraw SE/A1: X             Default: 34.02 in (864 mm)
# y_travel_SEA1 = 23.39    # AxiDraw SE/A1: Y             Default: 23.39 in (594 mm)
# model 6:
# x_travel_SEA2 = 23.39    # AxiDraw SE/A2: X             Default: 23.39 in (594 mm)
# y_travel_SEA2 = 17.01    # AxiDraw SE/A2: Y             Default: 17.01 in (432 mm )
# model 7:
# x_travel_V3B6 = 7.48     # AxiDraw V3/B6: X             Default: 7.48 in (190 mm)
# y_travel_V3B6 = 5.51     # AxiDraw V3/B6: Y             Default: 5.51 in (140 mm)
xTravel = [None, 11.81, 16.93, 23.42, 6.30, 34.02, 23.39,  7.48]
yTravel = [None,  8.58, 11.69,  8.58, 4.00, 23.39, 17.01,  5.51]

# Distances for registration moves -- sensible numbers in each set of units
regDistances = {"mm": {"f": 0.1  , "m": 1   , "c": 10  },
                "in": {"f": 0.005, "m": 0.05, "c":  0.5}}

def maxX ():  # inches
    try:
        model = options.model
    except AttributeError:
        model = 1
    return xTravel[model]

def maxY ():  # inches
    try:
        model = options.model
    except AttributeError:
        model = 1
    return yTravel[model]

# Local store for options
class Options:
    def __init__ (self):
        # Hard-coded default options,
        # just to make sure they all have values.
        # Most will get updated from ad.options straight away.
        # Distances are in inches -- as per standard AxiDraw configs.
        self.__dict__ = {
            "accel": 75,
            "auto_rotate": True,
            "const_speed": False,
            "copies": 1,
            "digest": 0,
            "dist": 1.0,
            "hiding": False,
            "ids": [],
            "layer": 1,
            "manual_cmd": 'enable_xy',
            "min_gap": 0.006,   # distance; additional
            "mode": 'manual',
            "model": 1,
            "no_rotate": False,
            "page_delay": 15,
            "pen_delay_down": 0,
            "pen_delay_up": 0,
            "pen_pos_down": 30,
            "pen_pos_up": 60,
            "pen_rate_lower": 50,
            "pen_rate_raise": 75,
            "penlift": 1,
            "port": None,
            "port_config": 0,
            "preview": False,
            "random_start": False,
            "rendering": 3,
            "reordering": 0,
            "report_time": True,
            "report_lifts": True,   # additional
            "resolution": 1,
            "resume_type": 'plot',
            "selected_nodes": [],
            "setup_type": 'align',
            "speed_pendown": 25,
            "speed_penup": 75,
            "submode": 'none',
            "units": 'in',  # NOTE not an AxiDraw option -- invented for adrepl
            "webhook": False,
            "webhook_url": None,
        }
        pass
    def __repr__ (self):
        # sort the keys for easier reading
        #return "repr:" + repr(vars(self))
        r = "{"
        keys = list(self.__dict__)
        keys.sort()
        for key in keys:
            val = self.__dict__[key]
            if key in ['min_gap']:
                # distances -- need to adjust for current units
                val = fmtDist(val) + ' ' + options.units
            r += f"'{key}': {val}, "
        return r + "}"
    def setFromOptions (self, sourceDict):
        # set options from a dictionary
        for key, val in sourceDict.items():
            self.__dict__[key] = val
            #print(f"set {key}={val}")
    def setFromParams (self, paramsDict):
        # 'additional' options from ad.params
        for key in ['min_gap', 'report_lifts']:
            self.__dict__[key] = paramsDict[key]
            #print(f"setFromParams {key}={paramsDict[key]}")
options = Options()

##############################################################

def printHelp ():
    print("""Available commands: 
accel, \
align, \
auto_rotate <y/n>, \
cd <directory>, \
config, \
const_speed <y/n>, \
copies <0-9999>, \
cycle, \
delaydown|pen_delay_down <ms>, \
delaypage|page_delay <s>, \
delayup|pen_delay_up <ms>, \
down|lower_pen, \
fw_version, \
help, \
hiding <y/n>, \
home|walk_home, \
ls, \
min_gap [<dist>], \
model [<num>], \
off|disable_xy, \
on|enable_xy, \
options|config [<filename>], \
output [<filename>], \
plot <filename> [<layer>], \
posdown|pen_pos_down <0-100>, \
position, \
posup|pen_pos_up <0-100>, \
preview <filename> [<layer>], \
quit, \
random_start <y/n>, \
ratedown|pen_rate_lower <1-100>, \
rateup|pen_rate_raise <1-100>, \
register, \
rendering <0-3>, \
reordering <0-4>, \
report_time <y/n>, \
report_lifts <y/n>, \
save [<filename>], \
speeddown|speed_pendown|sd <1-100>, \
speedup|speed_penup|su <1-100>, \
sysinfo, \
toggle, \
units <mm>|<inches>, \
up|raise_pen, \
version, \
walkx|x <distance>, \
walky|y <distance> \
""")
    print("Commands can be abbreviated as long as what you type is unambiguous.")

# List of commands with the associated short internal command name
cmdList = [
    ("accel", "ac"),
    ("align", "al"),
    ("auto_rotate", "au"),
    ("cd", "cd"),
    ("config", "op"),
    ("const_speed", "cs"),
    ("copies", "cp"),
    ("cycle", "cy"),
    ("delaydown", "dd"),
    ("delaypage", "dp"),
    ("delayup", "du"),
    ("disable_xy", "of"),
    ("down", "do"),
    ("enable_xy", "on"),
    ("fw_version", "fw"),
    ("help", "he"),
    ("hiding", "hi"),
    ("home", "wh"),
    ("lower_pen", "do"),
    ("ls", "ls"),
    ("min_gap", "mg"),
    ("model", "mo"),
    ("off", "of"),
    ("on", "on"),
    ("options", "op"),
    ("output", "ou"),
    ("page_delay", "dp"),
    ("pen_delay_down", "dd"),
    ("pen_delay_up", "du"),
    ("pen_pos_down", "pd"),
    ("pen_pos_up", "pu"),
    ("pen_rate_lower", "pl"),
    ("pen_rate_raise", "pr"),
    ("plot", "pt"),
    ("posdown", "pd"),
    ("position", "po"),
    ("posup", "pu"),
    ("preview", "pv"),
    ("quit", "qu"),
    ("raise_pen", "up"),
    ("random_start", "rd"),
    ("ratedown", "pl"),
    ("rateup", "pr"),
    ("register", "rg"),
    ("rendering", "rn"),
    ("reordering", "ro"),
    ("report_time", "rp"),
    ("report_lifts", "rl"),
    ("save", "sc"),
    ("sethome", "sh"),
    ("speed_pendown", "sd"),
    ("speed_penup", "su"),
    ("speeddown", "sd"),
    ("speedup", "su"),
    ("sd", "sd"),
    ("su", "su"),
    ("sysinfo", "sy"),
    ("toggle", "tg"),
    ("units", "un"),
    ("up", "up"),
    ("version", "vr"),
    ("walk_home", "wh"),
    ("walkx", "wx"),
    ("walky", "wy"),
    ("x", "wx"),
    ("y", "wy"),
    ("walk", "wh"),
]

# Match the abbreviated command against the list,
# returning short-command or "" or None
def miniMatch (cmd):
    if cmd == "":
        print("Type a command, or try 'help'")
        return ""
    #global cmdList
    matched = []
    short = None
    for pair in cmdList:
        # Full match succeeds immediately
        # (otherwise would fail if both 'foo' and 'foo_bar' are valid)
        if cmd == pair[0]:
            return pair[1]
        # Else try to match as abbreviation
        if pair[0].startswith(cmd):
            matched.append(pair[0])
            short = pair[1]
    n = len(matched)
    #print(f"{matched=}")
    if n == 0:
        print(f"Command '{cmd}' is not known.  Try typing 'help'.")
        return None
    if n == 1:
        return short
    print(f"Command '{cmd}' is ambiguous -- it could match any of {matched}")
    return None

# Print the current config
def printConfig():
    #for opt in options:
    pass

# Code for loading configuration file provided by Windell Oskay, 22 April 2023.
# Adapted to work here.
# Overwrites existing options if new values are in the file.
def loadConfig (args, showOutput=True):
    global options
    #print(f"loadConfig: {args=} {showOutput=}")
    if len(args) == 0:
        # just print the current config
        print("options:", options)
        return
    optionsChanged = False
    # Gather the rest of the args into a single string
    filename = argsToFileName(args)
    if filename:
        try:
            config_dict = acutils.load_config(filename)
            options.setFromOptions(config_dict)
            optionsChanged = True
            print(f"config file '{filename}' loaded")
        except SystemExit as err:
            #print("SE error:", err, "done")
            pass
    if optionsChanged and showOutput:
        print(f"new options: {options}")

def setOutputFilename (args):
    global outputFilename
    if len(args) == 0:
        print(outputFilename)
        return
    outputFilename = args[0]
    if outputFilename == 'none':
        print("Plot output will not be saved")
    elif outputFilename == 'auto':
        print("Plot output file name will be chosen automatically")
    else:
        print(f"Plot output will be saved as '{outputFilename}'")

# Save the current options.
# NOTE: some options e.g. 'mode' will just save the last value used,
# e.g. if last command was 'align', the mode will be saved as 'align'.
def saveConfig (args):
    if len(args) == 0:
        filename = defaultConfigFile
    else:
        filename = args[0]
    try:
        with open(filename, 'w') as f:
            print(f"Saving configuration to {filename!r}")
            keys = list(options.__dict__)
            keys.sort()
            for key in keys:
                #print(f"{key} = {options.__dict__[key]!r}")
                f.write(f"{key} = {options.__dict__[key]!r}\n")
    except PermissionError as err:
        print("Unable to save configuration:", err)

def handleSigint (*args):
    if plotRunning:
        # Just stop the plot
        print("\nPlot running -- to cancel it, press the button on the plotter")
    else:
        # Quit from the REPL
        print("\ndone (Ctrl-C pressed)")
        quit()

# Apply local options, and then call plot_run()
def plotRun (inputFilename=None):
    for key, value in options.__dict__.items():
        if key in ['min_gap', 'report_lifts']:
            # 'additional' option -- see https://axidraw.com/doc/py_api/#additional-parameters
            ad.params.__dict__[key] = value
        else:
            # 'normal' option
            ad.options.__dict__[key] = value
    #print(f"Running with options {options}")
    #print(f"{inputFilename=}  {outputFilename=}")
    if inputFilename and outputFilename != 'none':
        # Send plot output to a file
        if outputFilename == 'auto':
            ofn = inputFilename + '.svg'   # FIXME could ad 'plob' if --digest value says so
        else:
            ofn = outputFilename
        print(f"{inputFilename=}  {outputFilename=}  {ofn=}")
        try:
            with open(ofn, "w") as outputFile:
                outputFile.write(ad.plot_run(True))
        except PermissionError as err:
            print(f"Unable to create output file {ofn}: {err}")
            return
    else:
        # Not using plot output
        ad.plot_run()

def parse (line):
    tokens = line.split()
    if len(tokens) == 0:
        return "", []
    elif len(tokens) == 1:
        return tokens[0], []
    return tokens[0].strip().lower(), tokens[1:]

def getInt (string):
    try:
        value = int(string)
        return value, ""
    except ValueError:
        return None, "invalid whole number"

def get1Int (args):
    if len(args) != 1:
        return ' '.join(args), "need one whole number"
    i, err = getInt(args[0])
    if err:
        return args[0], err
    return i, ""

def setRangeInt (optName, low, high, args):
    oldValue = getattr(options, optName)
    #print(f"setRange({optName},{low},{high},{oldValue},{args} len={len(args)})")
    if len(args) == 0:
        print(f"{optName} {oldValue}")
        return
    value, err = get1Int(args)
    if err:
        print(f"{optName}: invalid value '{value}'.  Need a single whole number")
        return 
    if value < low or value > high:
        print(f"{optName}: value '{value}' out of range ({low} - {high})")
        return
    setattr(options, optName, value)
    newValue = getattr(options, optName)
    print(f"{optName} {newValue}")

# Get a boolean value from user input
def getBool (default, string):
    if string:
        value = string.lower()
        v0 = value[0]
        if v0 == 'y' or v0 == 't' or v0 == '1' or value == 'on':
            return True
        if v0 == 'n' or v0 == 'f' or v0 == '0' or value == 'off':
            return False
    print(f"Can't get yes/no or true/false or on/off value from '{string}'.  Assuming you meant '{default}'")
    return default

# New version: always print the new value if setting it
def setBool (optName, args):
    oldValue = getattr(options, optName)
    if len(args) == 0 or len(args[0]) == 0:
        print(f"{optName} {oldValue}")
        return 
    value = args[0].lower()  # ignore other args
    v0 = value[0]
    goodValue = None
    if v0 == 'y' or v0 == 't' or v0 == '1' or value == 'on':
        goodValue = True
    if v0 == 'n' or v0 == 'f' or v0 == '0' or value == 'off':
        goodValue = False
    if goodValue == None:
        print(f"{optName}: can't get yes/no or true/false or on/off from '{value}'")
        return
    setattr(options, optName, goodValue)
    newValue = getattr(options, optName)
    print(f"{optName} {newValue}")
    return newValue    # FIXME not needed?

def getFloat (string):
    try:
        value = float(string)
        return value, ""
    except ValueError:
        return None, "invalid number"

def get1Float (args):
    if len(args) != 1:
        return "", "need one number"
    f, err = getFloat(args[0])
    if err:
        return args[0], err
    return f, ""

def getDist (args):
    if len(args) != 1:
        return None, f"need a distance ({options.units})"
    d, err = getFloat(args[0])
    if err:
        return None, err
    if options.units == "mm":
        # store as inches
        d /= 25.4
    return d, ""

def setMinGap (args):
    if len(args) == 0:
        print(f"{fmtDist(options.min_gap)} {options.units}") 
        return
    dist, err = getDist(args)
    if err:
       printf(err)
       return
    options.min_gap = dist
    return

# Allow fine tuning of position using arrow keys.
def registerXY():
    nl = ""
    def showMove (m):
        nonlocal nl
        print(m, end="", flush=True)
        nl = "\n"
    def printMsg (msg):
        nonlocal nl
        print(f"{nl}{msg}")
        nl = ""
    # Start with medium jumps
    regDist = regDistances[options.units]["m"]
    print("registering: press arrow keys to move.")
    print("press f for fine, m for medium, c for coarse; u/d for pen up/down; q or ESC to stop.")
    print(f"medium {regDist}{options.units} steps")
    with Input(keynames='curtsies') as input_generator:
        for e in Input():   # e is a keypress or other event
            if e in ('<ESC>', '<SPACE>', 'q'):
                break
            # print(e)
            if e == '<UP>':
                showMove("\u2191")
                walk('y', [-regDist])
            elif e == '<DOWN>':
                showMove("\u2193")
                walk('y', [regDist])
            elif e == '<LEFT>':
                showMove("\u2190")
                walk('x', [-regDist])
            elif e == '<RIGHT>':
                showMove("\u2192")
                walk('x', [regDist])
            elif e in ('f', 'F'):
                regDist = regDistances[options.units]["f"]
                printMsg(f"fine {regDist}{options.units} steps")
            elif e in ('m', 'M'):
                regDist = regDistances[options.units]["m"]
                printMsg(f"medium {regDist}{options.units} steps")
            elif e in ('c', 'C'):
                regDist = regDistances[options.units]["c"]
                printMsg(f"coarse {regDist}{options.units} steps")
            elif e in ('u', 'U'):
                manual("raise_pen")
                showMove("u")
            elif e in ('d', 'D'):
                manual("lower_pen")
                showMove("d")
            elif e in ('r', 'R'):
                walkHome()
                showMove("r")
    printMsg("done registering")
    reply = input("Set home? y/n: ")
    if getBool(False, [reply]):
        setHome()

def setHome ():
    manual("disable_xy")
    manual("enable_xy")

def setUnits (args):
    if len(args) >= 1:
        u = args[0].strip().lower()
        if u == "mm" or "millimetres".startswith(u):
            options.units = 'mm'
        elif "inches".startswith(u):
            options.units = 'in'
        else:
            print("need 'mm' or 'in'")
    print("units ", options.units)

# Format a distance for printing in the current units
def fmtDist (d):
    format = ".4f"
    if options.units == "mm":
        format = ".2f"
        d *= 25.4
    return f"{d:{format}}"

def walk (xy, args):
    global aligned, alignX, alignY
    dist, err = getDist(args) # in inches
    if err:
        print(f"walk{xy}: {err}")
        return
    #print(f"walk{xy} {dist=} {aligned=} {alignX=} {alignY=} {maxX()=} {maxY()=}")
    options.mode = "manual"
    options.manual_cmd = f"walk_{xy}"
    if aligned: 
        limited = False
        if xy == 'x':
            if alignX + dist < 0:
                dist = -alignX
                limited = True
            elif alignX + dist > maxX():
                dist = maxX() - alignX
                limited = True
            alignX += dist
        else:
            if alignY + dist < 0:
                dist = -alignY
                limited = True
            elif alignY + dist > maxY():
                dist = maxY() - alignY
                limited = True
            alignY += dist
        if limited:
            print(f"Limited to {fmtDist(dist)} {options.units}") 
    # (if not aligned, DOES ONLY MINIMAL CHECKS)
    else:
        if xy == 'x':
            if abs(dist) > maxX():
                print("Too far")
                return
        else:
            if abs(dist) > maxY():
                print("Too far")
                return
    options.walk_dist = dist     # for pre-3.8 software
    options.dist = dist
    plotRun()
    #print(f"NOT RUNNING -- would have walked {dist} {xy}")

def walkHome ():
    manual("walk_home")
    if aligned:
        alignX = 0.0
        alignY = 0.0

def showPos ():
    if aligned: 
        x = alignX
        y = alignY
        print(f"{fmtDist(x)}, {fmtDist(y)} {options.units}")
    else:
        print("Head position is unknown.  Use 'align' to manually move head to 0,0.")

def argsToFileName (args):
    # Gather the args into a single string for use as a file name
    filename = ' '.join(args)
    filename = os.path.expanduser(filename.strip(" \"'\t\r\n"))
    return filename

def plotFile (args, preview=False):
    cmdName = "preview" if preview else "plot"
    layer = None
    # args will be |"filename.svg"| or |"filename.svg" "3"| or |"long" "file" "name.svg" "2"| etc.
    # If filename has spaces, we need to stick it back together.
    if len(args) > 1:
        # Use last arg as layer number if it's numeric
        layer, err = getInt(args[-1])
        if err:
            # Not numeric -- take it as part of the filename
            pass
        else:
            if layer < 0 or layer > 1000:
                print(f"{cmdName}: layer must be a whole number between 0 and 1000", err)
                return
            # Numeric layer 
            args.pop()
    if len(args) == 0:
        print(f"{cmdName}: need one filename (and optional layer prefix)")
        return
    global plotRunning
    plotRunning = True
    # Gather the rest of the args into a single string
    filename = argsToFileName(args)
    try:
        if layer is not None:
            options.mode = "layers"
            print(f"plotting file '{filename}' layer {layer}")
        else:
            options.mode = "plot"
            print(f"plotting file '{filename}'")
        options.layer = layer    # even if it's None
        ad.plot_setup(filename) # This changes ad.options
        oldRT = options.report_time
        oldRL = options.report_lifts
        if preview:
            # Always do these for previews
            options.preview = True
            options.report_time = True
            options.report_lifts = True
        plotRun(filename)   # This re-applies local options to ad.options
        if ad.errors.code == 0:
            ## The report will already have been printed,
            ## but these values are now available to use:
            #if oldRT: 
            #    time_elapsed = ad.time_elapsed
            #    time_estimate = ad.time_estimate 
            #    dist_pen_down = ad.distance_pendown
            #    dist_pen_total = ad.distance_total
            #    pen_lifts = ad.pen_lifts
            pass
        else:
            print("plotting failed, error", ad.errors.code)
        if preview :
            options.preview = False
            options.report_time = oldRT
            options.report_lifts = oldRL
    except RuntimeError as err:
        # Error msg has already been printed
        print(f"plotFile exception")
        pass
    finally:
        print(f"plotting completed")
        plotRunning = False

# simple manual commands
def manual (cmd):
    options.mode = "manual"
    options.manual_cmd = cmd
    plotRun()

def setModel(args):
    setRangeInt("model", 1, 7, args)
    print(f"Plot size is {fmtDist(xTravel[options.model])} by {fmtDist(yTravel[options.model])} {options.units}")

def align ():
    global aligned, alignX, alignY
    options.mode = "align"
    plotRun()
    print("Head can now be moved manually.")
    reply = input("Is the head at the origin (0,0)? y/n: ")
    aligned = getBool(False, reply)
    if aligned:
        alignX = 0.0
        alignY = 0.0
        setHome()
    else:
        alignX = None
        alignY = None
        print("WARNING: head position is unknown -- be careful when using walkx/y or reg")

def loadHistory ():
    if readline and os.path.exists(defaultHistFile):
        readline.read_history_file(defaultHistFile)

def saveHistory ():
    if readline:
        readline.set_history_length(histFileSize)
        readline.write_history_file(defaultHistFile)

def cd (args):
    if len(args) > 0:
        try:
            os.chdir(os.path.expanduser(args[0]))
        except (FileNotFoundError) as err:
            print("Can't change to that directory:", err)
    print(os.getcwd())

def ls ():
    print(f"{os.getcwd()}:")
    with os.scandir() as entries:
        # build list of file details for sorting
        l = []
        for entry in entries:
            if entry.is_file() and entry.name.lower().endswith(".svg"):
                l.append({"name": entry.name, "size": entry.stat().st_size, "mtime": entry.stat().st_mtime, "dirchar": ""})
            if entry.is_dir():
                l.append({"name": entry.name, "size": entry.stat().st_size, "mtime": entry.stat().st_mtime, "dirchar": "/"})
        if len(l) == 0:
            print("No plottable (.svg) files in current directory")
            return
        l = sorted(l, key=lambda d: d['name']) # sort by 'name' field
        for entry in l:
            utcmtime  = datetime.utcfromtimestamp(entry['mtime'])
            timestamp = utcmtime.strftime("%Y-%m-%d %H:%M:%S")
            print(f"{entry['size']:11d}  {timestamp}  {entry['name']}{entry['dirchar']}")

def restoreCWD ():
    os.chdir(origDir)

##########################################################################################

signal.signal(signal.SIGINT, handleSigint)

# Setup
ad = axidraw.AxiDraw()          # Initialize class
ad.plot_setup()                 # Go into plot mode and create ad.options
# Copy initial ad.options into local options
options.setFromParams(ad.params.__dict__)
# User options override params:
options.setFromOptions(ad.options.__dict__)

if len(sys.argv[1:]) == 0:
    # Load default config file
    loadConfig([defaultConfigFile], True)
else:
    # Load config files from command line 
    # (one at a time because that's how loadConfig works)
    for arg in sys.argv[1:]:
        loadConfig(arg, True)

# Make sure preview option is not set -- it interferes with some modes,
# and we use it a bit differently (see plotFile()).
options.preview = False

# Get user to check position of pen
align()

loadHistory()
atexit.register(saveHistory)
atexit.register(restoreCWD)

# REPL
while True:
    try:
        line = input("> ")  # .decode('utf-8').strip()
    except EOFError:
        # Ctrl-D pressed
        print("\ndone (Ctrl-D pressed)")
        break
    cmd, args = parse(line)
    shortCmd = miniMatch(cmd)
    if not shortCmd:
        continue
    if shortCmd == "he":
        printHelp()
    elif shortCmd == "qu":
        print("done")
        break   # out of the while loop
    elif shortCmd == "cy":
        options.mode = "cycle"
        plotRun()
    elif shortCmd == "al":
        align()
    elif shortCmd == "vr":
        options.mode = "version"
        plotRun()
    elif shortCmd == "sy":
        options.mode = "sysinfo"
        plotRun()
    elif shortCmd == "tg":
        options.mode = "toggle"
        plotRun()
    elif shortCmd == "un":
        setUnits(args)
    elif shortCmd == "wx":
        walk("x", args)
    elif shortCmd == "wy":
        walk("y", args)
    elif shortCmd == "wh":
        walkHome()
    elif shortCmd == "fw":
        manual("fw_version")
    elif shortCmd == "hi":
        setBool("hiding", args)
    elif shortCmd == "up":
        manual("raise_pen")
    elif shortCmd == "do":
        manual("lower_pen")
    elif shortCmd == "on":
        manual("enable_xy")
        print("motors are on")
    elif shortCmd == "of":
        manual("disable_xy")
        print("motors are off")
    elif shortCmd == "pt":
        plotFile(args)
    elif shortCmd == "pv":
        plotFile(args, True)
    elif shortCmd == "op":
        loadConfig(args)
    elif shortCmd == "ou":
        setOutputFilename(args)
    elif shortCmd == "mo":
        setModel(args)
    elif shortCmd == "sd":
        setRangeInt("speed_pendown", 1, 100, args)
    elif shortCmd == "su":
        setRangeInt("speed_penup", 1, 100, args)
    elif shortCmd == "ac":
        setRangeInt("accel", 1, 100, args)
    elif shortCmd == "pd":
        setRangeInt("pen_pos_down", 0, 100, args)
    elif shortCmd == "pu":
        setRangeInt("pen_pos_up", 0, 100, args)
    elif shortCmd == "pl":
        setRangeInt("pen_rate_lower", 1, 100, args)
    elif shortCmd == "pr":
        setRangeInt("pen_rate_raise", 1, 100, args)
    elif shortCmd == "dd":
        setRangeInt("pen_delay_down", 0, 10000, args)
    elif shortCmd == "du":
        setRangeInt("pen_delay_up", 0, 10000, args)
    elif shortCmd == "dp":
        setRangeInt("page_delay", 0, 10000, args)
    elif shortCmd == "rn":
        setRangeInt("rendering", 0, 3, args)
    elif shortCmd == "ro":
        setRangeInt("reordering", 0, 4, args)
    elif shortCmd == "cp":
        setRangeInt("copies", 0, 9999, args)
    elif shortCmd == "rd":
        setBool("random_start", args)
    elif shortCmd == "rp":
        setBool("report_time", args)
    elif shortCmd == "rl":
        setBool("report_lifts", args)
    elif shortCmd == "cs":
        setBool("const_speed", args)
    elif shortCmd == "au":
        setBool("auto_rotate", args)
    elif shortCmd == "rg":
        registerXY()
    elif shortCmd == "po":
        showPos()
    elif shortCmd == "sh":
        setHome()
    elif shortCmd == "sc":
        saveConfig(args)
    elif shortCmd == "cd":
        cd(args)
    elif shortCmd == "ls":
        ls()
    elif shortCmd == "mg":
        setMinGap(args)

    else:
        print(f"Short command '{shortCmd}' ('{cmd}') is not known.")

# end of REPL loop

