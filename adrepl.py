#!/bin/env python

# adrepl -- AxiDraw frontend.
# A simple REPL for controlling the AxiDraw

# Issues:
# * With old (pre 3.8?) software, 'dist' was spelled 'walk_dist' --
#   this code only reads both from config files -- which overrides the other?

# NOTES:
# * options get reset by plot_setup: the docs says they can be set 
#   between plot_setup and plot run.  So we need to keep and options 
#   object, and apply them all before each plot_run (or after plot_setup).
# * developed and tested on Raspberry Pi (orig B+) running Raspbian bullseye.
# * requirements:
#   - python3
#   - modules as below
# * All distances are handled in inches, convert to and from millimetres
#   for display and input if required.

# TODO
# * make sure all options report just their current value if no args
#   - simplify model
# * interactive mode for some things??
# * loop to print many copies
# * at start, load default config from ~/.config/adrepl/config.py and/or current dir etc.
# * save config
# * history - save and restore; complete filenames
# * resolution, reordering options
# * display current options in alpha order
# * maybe: check add.errors.code at end of REPL (after every command)
# * cmd to draw a reg mark
# * pause/resume (capture Ctrl-C while plotting??) -- output to plob etc. -- store temp file somewhere standard; 
#   derive its name from .svg filename to allow auto resume

import atexit
import os
import readline # for user input history etc.
import signal
import sys

from curtsies  import Input
from pyaxidraw import axidraw
from axicli    import utils as acutils

# Globals:
currentUnits = "mm"
aligned = False     # True if we know where the head is.
alignX = None       # Head position if aligned in inches.
alignY = None

# 'Constants'
minX = 0.0
minY = 0.0
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
        pass
    def __repr__ (self):
        # sort the keys for easier reading
        #return "repr:" + repr(vars(self))
        r = "{"
        keys = list(self.__dict__)
        keys.sort()
        for key in keys:
            r += f"'{key}': {self.__dict__[key]}, "
        return r + "}"
    def set (self, sourceDict):
        for key, val in sourceDict.items():
            self.__dict__[key] = val
options = Options()

##############################################################

def printHelp ():
    print("""Available commands: help, quit, cycle, align, version, sysinfo, toggle, units <mm>|<inches>,
    x|walkx <distance>, y|walky <distance>, fw_version, up|raise_pen, down|lower_pen, home|walk_home,
    on|enable_xy, off|disable_xy, plot <filename> [<layer>], options|config [<filename>], model [<num>],
    speeddown|speed_pendown <1-100>, speedup|speed_penup <1-100>, accel, posdown|pen_pos_down <0-100>,
    posup|pen_pos_up <0-100>, ratedown|pen_rate_lower <1-100>, rateup|pen_rate_raise <1-100>,
    delaydown|pen_delay_down <ms>, delayup|pen_delay_up <ms>, delaypage|page_delay <s>, copies <0-9999>,
    random|random_start <y/n>, report|report_time <y/n>, const|const_speed <y/n>, progress <y/n>,
    preview <y/n>, auto|auto_rotate <y/n>, register, render, position""")

cmdList = [
    ("accel", "ac"),
    ("align", "al"),
    ("auto_rotate", "au"),
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
    ("home", "ho"),
    ("lower_pen", "do"),
    ("model", "mo"),
    ("off", "of"),
    ("on", "on"),
    ("options", "op"),
    ("page_delay", "dp"),
    ("pen_delay_down", "dd"),
    ("pen_delay_up", "du"),
    ("pen_pos_down", "pd"),
    ("pen_pos_up", "pu"),
    ("pen_rate_lower", "rd"),
    ("pen_rate_raise", "ru"),
    ("plot", "pl"),
    ("posdown", "pd"),
    ("position", "po"),
    ("posup", "pu"),
    ("preview", "pv"),
    ("quit", "qu"),
    ("raise_pen", "up"),
    ("random", "rn"),
    ("random_start", "rn"),
    ("ratedown", "rd"),
    ("rateup", "ru"),
    ("register", "rg"),
    ("render", "rn"),
    ("report_time", "rp"),
    ("sethome", "sh"),
    ("speed_pendown", "sd"),
    ("speed_penup", "su"),
    ("speeddown", "sd"),
    ("speedup", "su"),
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
]

# Match the abbreviated command against the list,
# returning short-command or None
def miniMatch (cmd):
    if cmd == "":
        return [""], ""
    global cmdList
    matched = []
    short = None
    for pair in cmdList:
        if pair[0].startswith(cmd):
            matched.append(pair[0])
            short = pair[1]
    n = len(matched)
    if n == 0:
        print(f"Command '{cmd}' is not known.  Try 'help'")
        return None
    if n == 1:
        return short
    print(f"Command '{cmd}' is ambiguous -- it could match any of {matched}")
    return None

# Code for loading configuration file(s) provided by Windell Oskay, 22 April 2023.
# Adapted to work here.
# Options and parameters set before this point WILL BE IGNORED.
def loadConfig (args):
    if len(args) == 0:
        # just print the current config
        print("options:", options)
        return
    optionsChanged = False
    for filename in args:
        configFilename = os.path.expanduser(filename)
        try:
            config_dict = acutils.load_config(configFilename)
        except SystemExit as err:
            # (load_config() will have already printed an error message)
            continue
        options.set(config_dict)
        optionsChanged = True
        print(f"config file '{configFilename}' loaded")
    if optionsChanged:
        print(f"new options: {options}")

def handleSigint (*args):
    print("done (Ctrl-C pressed)")
    quit()

# Apply local options, and then call plot_run()
def plotRun ():
    for key, value in options.__dict__.items():
        ad.options.__dict__[key] = value
    #print(f"Running with options {options}")
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
        return None, "need one whole number"
    f, err = getInt(args[0])
    if err:
        return None, err
    return f, ""

# Get a value within a range: return the new value,
# or the old value if the new one is invalid.
def getRange (optName, low, high, oldValue, args):
    if len(args) == 0:
        print(oldValue)
        return
    value, err = get1Float(args)    # FIXME float or int?
    if err:
        print(f"{optName}: invalid value")
        return oldValue
    if value < low or value > high:
        print(f"{optName}: value out of range ({low} - {high})")
        return oldValue
    return value

def getBool (optName, oldValue, args):
    if len(args) == 0 or len(args[0]) == 0:
        print(oldValue)
        return
    value = args[0].lower()  # ignore other args
    v0 = value[0]
    if v0 == 'y' or v0 == 't' or v0 == '1' or value == 'on':
        return True
    if v0 == 'n' or v0 == 'f' or v0 == '0' or value == 'off':
        return False
    print(f"{optName}: can't get yes/no or true/false or on/off value from '{value}'")
    return oldValue

def getFloat (string):
    try:
        value = float(string)
        return value, ""
    except ValueError:
        return None, "invalid number"

def get1Float (args):
    if len(args) != 1:
        return None, "need one number"
    f, err = getFloat(args[0])
    if err:
        return None, err
    return f, ""

def getDist (args):
    if len(args) != 1:
        return None, "need a distance"
    d, err = getFloat(args[0])
    if err:
        return None, err
    if currentUnits == "mm":
        # store as inches
        d /= 25.4
    return d, ""

# Allow fine tuning of position using arrow keys.
def registerXY():
    global currentUnits
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
    regDist = regDistances[currentUnits]["m"]
    print("registering: press arrow keys to move.")
    print("press f for fine, m for medium, c for coarse; u/d for pen up/down; q or ESC to stop.")
    print(f"medium {regDist}{currentUnits} steps")
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
                regDist = regDistances[currentUnits]["f"]
                printMsg(f"fine {regDist}{currentUnits} steps")
            elif e in ('m', 'M'):
                regDist = regDistances[currentUnits]["m"]
                printMsg(f"medium {regDist}{currentUnits} steps")
            elif e in ('c', 'C'):
                regDist = regDistances[currentUnits]["c"]
                printMsg(f"coarse {regDist}{currentUnits} steps")
            elif e in ('u', 'U'):
                manual("raise_pen")
                showMove("u")
            elif e in ('d', 'D'):
                manual("lower_pen")
                showMove("d")
    printMsg("done registering")
    reply = input("Set home? y/n: ")
    if getBool("sethome", False, [reply]):
        setHome()

def setHome ():
    manual("disable_xy")
    manual("enable_xy")

def setUnits (args):
    global currentUnits
    if len(args) >= 1:
        u = args[0].strip().lower()
        if u == "mm" or "millimetres".startswith(u):
            currentUnits = "mm"
        elif "inches".startswith(u):
            currentUnits = "in"
        else:
            print("need 'mm' or 'in'")
    print("current units:", currentUnits)

# Format a distance for printing in the current units
def fmtDist (d):
    format = ".3f"
    if currentUnits == "mm":
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
            print(f"Limited to {fmtDist(dist)}") 
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

def showPos ():
    if aligned: 
        x = alignX
        y = alignY
        print(f"{fmtDist(x)}, {fmtDist(y)} {currentUnits}")
    else:
        print("Head position is unknown.  Use 'align' to manually move head to 0,0.")

def plotFile (args):
    if len(args) == 0 or len(args) > 2:
        print("plot: need one filename (and optional layer prefix)")
        return
    filename = os.path.expanduser(args[0].strip(" \"'\t\r\n"))

    layer = None
    if len(args) == 2:
        layer, err = getInt(args[1])
        if err or layer < 0 or layer > 1000:
            print("plot: layer must be a whole number between 0 and 1000", err)
            return
    try:
        if layer:
            options.mode = "layers"
            print(f"plotting file '{filename}' layer {layer}")
        else:
            options.mode = "plot"
            print(f"plotting file '{filename}'")
        options.layer = layer    # even if it's None
        ad.plot_setup(filename)
        plotRun()   # This re-applies local options to ad.options
        if ad.errors.code == 0:
            # The report will already have been printed,
            # but these values are now available to use:
            if ad.options.report_time: 
                time_elapsed = ad.time_elapsed
                time_estimate = ad.time_estimate 
                dist_pen_down = ad.distance_pendown
                dist_pen_total = ad.distance_total
                pen_lifts = ad.pen_lifts
        else:
            print("plotting failed, error", ad.errors.code)
    except RuntimeError as err:
        # Error msg has already been printed
        pass

# simple manual commands
def manual (cmd):
    options.mode = "manual"
    options.manual_cmd = cmd
    plotRun()   #ad.plot_run()

def setModel (args):
    oldM = options.model
    if len(args) == 0:
        print(f"model is {oldM}")
        return
    m, err = get1Int(args)
    if err:
        print(err)
        return
    if m < 1 or m > 7:
        print("need a model number between 1 and 7")
        return
    if m == oldM:
        print(f"model remains at {oldM}")
    else:
        options.model = m
        print(f"model changed from {oldM} to {m}")

def set1Int (option, args):
    val, err = get1Int(args)
    if err:
        print(err)
    else:
        option = val

def align ():
    global aligned, alignX, alignY
    options.mode = "align"
    plotRun()
    print("Head can now be moved manually.")
    reply = input("Is the head at the origin (0,0)? y/n: ")
    aligned = getBool("align", False, [reply])
    if aligned:
        alignX = 0.0
        alignY = 0.0
    else:
        alignX = None
        alignY = None
        print("WARNING: head position is unknown -- be careful when using walkx/y or reg")

##########################################################################################

signal.signal(signal.SIGINT, handleSigint)

# Setup
ad = axidraw.AxiDraw()          # Initialize class
ad.plot_setup()                 # Go into plot mode and create ad.options
# Copy initial ad.options into local options
options.set(ad.options.__dict__)

# Load config file(s) supplied on command line
loadConfig(sys.argv[1:])

align()

# REPL
while True:
    line = input("> ")  # .decode('utf-8').strip()
    cmd, args = parse(line)
    shortCmd = miniMatch(cmd)
    if shortCmd == None:
        pass
    elif shortCmd == "":
        print("Type a command, or try 'help'")
    elif shortCmd == "he":
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
    elif shortCmd == "fw":
        manual("fw_version")
    elif shortCmd == "up":
        manual("raise_pen")
    elif shortCmd == "do":
        manual("lower_pen")
    elif shortCmd == "ho":
        manual("walk_home")
        if aligned:
            alignX = 0.0
            alignY = 0.0
    elif shortCmd == "on":
        manual("enable_xy")
        print("motors are on")
    elif shortCmd == "of":
        manual("disable_xy")
        print("motors are off")
    elif shortCmd == "pl":
        plotFile(args)
    elif shortCmd == "op":
        loadConfig(args)
    elif shortCmd == "mo":
        setModel(args)
    elif shortCmd == "sd":
        options.speed_pendown = getRange("speeddown", 1, 100, options.speed_pendown, args)
    elif shortCmd == "su":
        options.speed_penup = getRange("speedup", 1, 100, options.speed_penup, args)
    elif shortCmd == "ac":
        options.accel = getRange("accel", 1, 100, options.accel, args)
    elif shortCmd == "pd":
        options.pen_pos_down = getRange("posdown", 0, 100, options.pen_pos_down, args)
    elif shortCmd == "pu":
        options.pen_pos_up = getRange("posup", 0, 100, options.pen_pos_up, args)
    elif shortCmd == "rd":
        options.pen_rate_lower = getRange("ratedown", 1, 100, options.pen_rate_lower, args)
    elif shortCmd == "ru":
        options.pen_rate_raise = getRange("rateup", 1, 100, options.pen_rate_raise, args)
    elif shortCmd == "dd":
        options.pen_delay_down = getRange("delaydown", 0, 10000, options.pen_delay_down, args)
    elif shortCmd == "du":
        options.pen_delay_up = getRange("delayup", 0, 10000, options.pen_delay_up, args)
    elif shortCmd == "dp":
        options.page_delay = getRange("pagedelay", 0, 10000, options.pagedelay, args)
    elif shortCmd == "cp":
        options.copies = getRange("copies", 0, 9999, options.copies, args)
    elif shortCmd == "rn":
        options.random_start = getBool("random", options.random_start, args)
    elif shortCmd == "rp":
        options.report_time = getBool("report", options.report_time, args)
    elif shortCmd == "cs":
        options.const_speed = getBool("const", options.const_speed, args)
    elif shortCmd == "pv":
        options.preview = getBool("preview", options.preview, args)
    elif shortCmd == "au":
        options.auto_rotate = getBool("auto", options.auto_rotate, args)
    elif shortCmd == "rg":
        registerXY()
    elif shortCmd == "rn":
        print("render: not implemented")
    elif shortCmd == "po":
        showPos()
    elif shortCmd == "sh":
        setHome()

    else:
        print(f"Don't understand '{line}'")


# end of REPL loop

