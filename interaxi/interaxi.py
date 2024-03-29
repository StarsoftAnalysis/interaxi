# interaxi -- interactive AxiDraw frontend.
# A simple REPL for controlling the AxiDraw

# (previously called adrepl)

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
# * paper/margin settings -- started coding, but couldn't find a way to 
#   tell AxiDraw to limit the plot range, so commented it all out.

# FIXME
# * needs tidying

# TODO
# * 'replot' option -- uses most recent output, doesn't create new output
# * "Command unavailable while in preview mode" -- if preview is True , some plot_run things won't work!!!!
#    -- so, make preview an alternative command to plot.
#   - simplify model
# * interactive mode for some things?? -- easy now that plot_run is used only briefly.
# * cmd to draw a reg mark
# * turn motors off after a delay (or does the firmware do that?)
# * fancy dialling in of 2 or 3 points on the substrate, and transforming whole plot to fit
# * exclude replies (y/n, r/c, maybe reg arrows) from history -- put them all in a function that returns a single char (or nothing)
# * warn if we're going to overwrite an existing file when renaming temp output
# * maybe an option to disable output creation and therefore restarting
# * set margin/paper/plot-size -- can override limits derived from model (but without going beyond the model capabilities)
#   adjusting for margin and previously set registration -- so the calcs done at plot time.  
#   Tell user not to worry about AD's warning re part of image being off the edge
# MAYBE
# * delay between copies instead of waiting for user input

import atexit
from datetime import datetime
import os
import pathlib
import signal
import sys
import tempfile
# Use readline if available:
try:
    import readline
except ImportError:
    readline = None
from curtsies  import Input
from pyaxidraw import axidraw
from axicli    import utils as acutils

# 'Constants'
version = "0.2.3"   # interaxi version
configDir = "~/.config/interaxi/"
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
## Paper sizes in inches
#paperSizes = {"A4L": {"w": 297 / 25.4, "h": 210 / 25.4},
#              "A4P": {"w": 210 / 25.4, "h": 297 / 25.4},
#              "A3L": {"w": 420 / 25.4, "h": 297 / 25.4}}
# Distances for registration moves -- sensible numbers in each set of units
regDistances = {"mm": {"f": 0.1  , "m": 1   , "c": 10  },
                "in": {"f": 0.005, "m": 0.05, "c":  0.5}}
noOutputFile = 'none'
autoOutputFile = 'auto'
userOpts = [     # Options the the user sees
        "accel",
        "auto_rotate",
        "const_speed",
        "copies",
        "digest",
        "hiding",
        "layer",
        "min_gap",
        "model",
        "pen_delay_down",
        "pen_delay_up",
        "pen_pos_down",
        "pen_pos_up",
        "pen_rate_lower",
        "pen_rate_raise",
        "random_start",
        "rendering",
        "reordering",
        "speed_pendown",
        "speed_penup",
        "units",
        ]
addlOpts = [    # options that go in ad.params rather than ad.options
        "min_gap",
        #"report_lifts",
        ]
distOpts = [    # options that use a distance in mm or inches
        #"margin",
        "min_gap",
        ]
# Globals:
aligned = False     # True if we know where the head is.
alignX = None       # Head position if aligned in inches.
alignY = None
outputFilename = noOutputFile
plotRunning = False # True while plotting a file -- used for sigint trap

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

# Local store for options - just the ones that the user can set
class Options:
    def __init__ (self):
        # Hard-coded default options, just to make sure they all have values.
        # i.e. minimum set of options that we assume are available.
        # Most will get updated from ad.options and config file straight away.
        # Distances are in inches -- as per standard AxiDraw configs.
        # NOTE: Some options are specific to interaxi -- not standard AxiDraw ones.
        self.__dict__ = {
            "accel": 75,
            "auto_rotate": True,
            "const_speed": False,
            "copies": 1,
            "digest": 0,
            "hiding": False,
            "layer": 1,
            #"margin": 0,      # distance; interaxi only
            "min_gap": 0.006,   # distance; additional
            "model": 1,
            #"paper": 'A4L',     # interaxi only
            "pen_delay_down": 0,
            "pen_delay_up": 0,
            "pen_pos_down": 30,
            "pen_pos_up": 60,
            "pen_rate_lower": 50,
            "pen_rate_raise": 75,
            #"penlift": 1,
            "random_start": False,
            "rendering": 1,
            "reordering": 0,
            #"report_time": True,
            #"report_lifts": True,   # additional
            "speed_pendown": 25,
            "speed_penup": 75,
            "units": 'in',      # interaxi only
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
            if key in distOpts: 
                # distances -- need to adjust for current units
                val = fmtDist(val) + ' ' + options.units
            r += f"'{key}': {val}, "
        return r + "}"
    def setFromOptions (self, sourceDict):
        # set options from a dictionary
        for key, val in sourceDict.items():
            if key in userOpts:
                self.__dict__[key] = val
                #print(f"setFromOptions {key}={val}")
    def setFromParams (self, paramsDict):
        # 'additional' options from ad.params
        for key in addlOpts:
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
digest <0|1|2>, \
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
#margin [<dist>], \
#paper [<papersize>], \
#report_time <y/n>, \
#report_lifts <y/n>, \
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
    ("digest", "dg"),
    ("disable_xy", "of"),
    ("down", "do"),
    ("enable_xy", "on"),
    ("fw_version", "fw"),
    ("help", "he"),
    ("hiding", "hi"),
    ("home", "wh"),
    ("lower_pen", "do"),
    ("ls", "ls"),
    #("margin", "ma"),
    ("min_gap", "mg"),
    ("model", "mo"),
    ("off", "of"),
    ("on", "on"),
    ("options", "op"),
    ("output", "ou"),
    #("paper", "pa"),
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
    #("report_time", "rp"),
    #("report_lifts", "rl"),
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
        print(f"output {outputFilename}")
        return
    outputFilename = args[0]
    if noOutputFile.startswith(outputFilename.lower()):
        outputFilename = noOutputFile
    elif autoOutputFile.startswith(outputFilename.lower()):
        outputFilename = autoOutputFile
    if outputFilename == noOutputFile:
        print("Plot output will not be saved")
    elif outputFilename == autoOutputFile:
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
        print("\nPlot running -- to pause or cancel it, press the button on the plotter")
    else:
        # Quit from the REPL
        print("\ndone (Ctrl-C pressed)")
        quit()

def applyOptionsToAD (ad, opts = {}):
    #print(f"aOTAD: {opts=} {type(opts)}")
    if type(opts) == type({}):
        o = opts.items()
    else:
        o = opts.__dict__.items()
    for key, value in o:    # pts.__dict__.items():
        if key in addlOpts:
            # 'additional' option -- see https://axidraw.com/doc/py_api/#additional-parameters
            ad.params.__dict__[key] = value
        else:
            # 'normal' option
            ad.options.__dict__[key] = value

# Apply local options, and then call plot_run()
# Returns 0 if OK, else an error code
def plotRun (inputFn = None, outputFn = None, cmdOpts = {}):

    ad = axidraw.AxiDraw()
    ad.plot_setup(inputFn)     # inputFn may be None
    # Apply all the user options
    #for key, value in options.__dict__.items():
    #    if key in addlOpts:
    #        # 'additional' option -- see https://axidraw.com/doc/py_api/#additional-parameters
    #        ad.params.__dict__[key] = value
    #    elif key in mainOpts:
    #        # 'normal' option
    #        ad.options.__dict__[key] = value
    applyOptionsToAD(ad, options)
    # And then apply the command options
    applyOptionsToAD(ad, cmdOpts)
    #print(f"plotRun: {inputFn=}  {outputFn=}  {ad.options=}")

    ## Apply paper/margin limits
    #xLimit = paperSizes[options.paper]["w"] - options.margin
    #yLimit = paperSizes[options.paper]["h"] - options.margin
    #print(f"plotRun: {ad.bounds=}")

    if not outputFn:
        # not plotting a file
        #try:
        ad.plot_run()
        return ad.errors.code
        # what exceptions can occur here?
        #except lxml.etree.XMLSyntaxError as err:
        #    print(f"Nasty SVG 3: {err}")
        #    return 3

    # Plotting or previewing an SVG file:
    try:
        with open(outputFn, "w") as outputFile:
            outputFile.write(ad.plot_run(True))
        return ad.errors.code
    except PermissionError as err:
        print(f"plotRun: unable to create output file {ofn}: {err}")
        return 1
    #except lxml.etree.XMLSyntaxError as err:
    #    print(f"Nasty SVG 2: {err}")
    #    return 2
    # maybe: except RuntimeError as err:

    return 0

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
    if len(args) > 0:
        dist, err = getDist(args)
        if err:
           print(err)
           return
        options.min_gap = dist
    print(f"min_gap {fmtDist(options.min_gap)} {options.units}") 
    return

#def setMargin (args):
#    if len(args) > 0:
#        dist, err = getDist(args)
#        if err:
#           print(err)
#           return
#        options.margin = dist
#    print(f"margin {fmtDist(options.margin)} {options.units}") 
#    return

#def setPaper (args):
#    if len(args) == 0:
#        print(f"paper {options.paper}")
#        return
#    if len(args) != 1:
#        print(f"Need a paper size, not '{args}'")
#        return
#    p = args[0].upper()
#    paper = None
#    for s in paperSizes.keys():
#        if s == p:
#            paper = s
#            break
#    if paper:
#        options.paper = paper
#        print(f"paper {options.paper}")
#    else:
#        print(f"Paper size must be one of {list(paperSizes.keys())}, not '{p}'")

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
    printMsg("Done registering")
    reply = input("Set home? y/n: ")
    if getBool(False, reply):
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
    print("units", options.units)

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
    cmdOpts = {}
    cmdOpts["mode"] = "manual"
    cmdOpts["manual_cmd"] = f"walk_{xy}"
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
    cmdOpts["walk_dist"] = dist     # for pre-3.8 software
    cmdOpts["dist"] = dist
    rc = plotRun(cmdOpts = cmdOpts)
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

# Get a filename and optional layer number.
# args will be |"filename.svg"| or |"filename.svg" "3"| or |"long" "file" "name.svg" "2"| etc.
# If filename has spaces, we need to stick it back together.
def getFilenameAndLayer (cmdName, args):
    layer = None
    if len(args) > 1:
        # Use last arg as layer number if it's numeric
        layer, err = getInt(args[-1])
        if not err:
            if layer < 0 or layer > 1000:
                print(f"{cmdName}: layer must be a whole number between 0 and 1000", err)
                return "", 0
            args.pop()
    if len(args) == 0:
        print(f"{cmdName}: need one filename (and optional layer prefix)")
        return "", 0
    return argsToFileName(args), layer

# Plot a number of copies
def plotCopies (args):
    storedCopies = options.copies
    options.copies = 1  # Don't need AxiDraw to handle the copies
    copies = 99999 if storedCopies == 0 else storedCopies
    for copy in range(1, storedCopies+1):
        print(f"Copy {copy} of {copies}:")
        plotFile(args)
        if copy < storedCopies:
            reply = input("Press Enter to start next copy (or type 'c' to cancel): ")
            if reply and reply.lower()[0] == 'c':
                print(f"Stopping after {copy} copies")
                break
    else:
        print(f"{copy} copies completed")
    options.copies = storedCopies

# Plot or preview an SVG file, with loop to deal with pause/resume
def plotFile (args, preview=False):
    cmdName = "preview" if preview else "plot"
    participle = "Previewing" if preview else "Plotting"
    inputFilename, layer = getFilenameAndLayer(cmdName, args)

    global plotRunning
    plotRunning = True

    # NOTE: The input file name has already been set via ad.plot_setup(filename).
    # It's only need here to generate an automatic outpuf file name.
    # That seems to mean that it doesn't matter if we resume
    # ...but how does it work if I'm not changing the input file?
    # Plotting a file: if there's an outputFilename, output will go that.
    # Else, send output to a temp file in case restart is required.
    # via the with.. just below.
    #print(f"{inputFilename=}  {outputFilename=}")

    infn = inputFilename
    outfn = None
    prevOutfn = None
    plotCancelled = False
    while True:     # until completed or cancelled
        prevOutfn = outfn
        cmdOpts = {}
        # Set up for the input file, and apply options
        if outfn != None:
            #print(f"Time to delete previous {outfn=} ?  NO!!!! outfn=infn")
            # Not the first time round the loop, so we're resuming
            cmdOpts["mode"] = "res_plot"
            print(f"Resuming file '{infn}' layer {layer}")
        elif layer is not None:
            cmdOpts["mode"] = "layers"
            print(f"{participle} file '{infn}' layer {layer}")
        else:
            cmdOpts["mode"] = "plot"
            print(f"{participle} file '{infn}'")
        cmdOpts["layer"] = layer   # even if it's None
        # now in plotRun   ad.plot_setup(infn)     # This changes ad.options
        #oldRT = options.report_time
        #oldRL = options.report_lifts
        if preview:
            cmdOpts["preview"] = True
        # Always do these
        cmdOpts["report_time"] = True
        cmdOpts["report_lifts"] = True
        # Always send output to temp file (see below re saving it)
        ofh, outfn = tempfile.mkstemp(suffix='.svg', text=True)
        # ?? ofh.close() # just need the name
        rc = plotRun(infn, outfn, cmdOpts)
        #if preview:
        #    options.preview = False
        #options.report_time = False
        #options.report_lifts = False
        #del options.report_time
        #del options.report_lifts
        if infn != inputFilename:
            # input was a temporary file -- delete it
            pathlib.Path(infn).unlink(missing_ok = True)
        if rc == 102:
            # user pressed the button -- may want to restart
            cmd = ''
            while not cmd in ['r', 'c']:
                reply = input("\nType 'r' to resume or 'c' to cancel: ").lower()
                if reply:
                    cmd = reply[0]
            if cmd == 'c':
                plotCancelled = True
                walkHome()
                break
            # previous outputfile is the input for the next go (it contains the restart position)
            infn = outfn
        elif rc > 0:
            print(f"{cmdName}: giving up -- got {rc=}   temp files not deleted")
            plotRunning = False
            return 
        else:
            # no pause -- plot is complete
            break
    # end of while True

    if plotCancelled or outputFilename == noOutputFile:
        # Cancelled, or user didn't ask for an output file -- delete it
        pathlib.Path(outfn).unlink(missing_ok = True)
    else:
        # Rename / move the temp output to a permanent file
        if outputFilename == autoOutputFile:
            infix = '.plob' if options.digest > 0 else '.out'
            ofn = f"{pathlib.Path(inputFilename).stem}{infix}.svg"
        else:
            ofn = outputFilename
        try:
            os.replace(outfn, ofn)
            print(f"{cmdName}: output file saved as '{ofn}")
        except OSError as err:
            print(f"{cmdName}: unable to rename '{ofn}' -- it has been kept as '{outfn}'")

    plotRunning = False

# simple manual commands
def manual (cmd):
    #options.mode = "manual"
    #options.manual_cmd = cmd
    rc = plotRun(cmdOpts = {"mode": "manual", "manual_cmd": cmd})

# Other special mode runs
def runMode (m): 
    rc = plotRun(cmdOpts = {"mode": m})

def setModel(args):
    setRangeInt("model", 1, 7, args)
    print(f"Maximum plot size is {fmtDist(xTravel[options.model])} by {fmtDist(yTravel[options.model])} {options.units}")

def align (showMsg = True):
    global aligned, alignX, alignY
    #options.mode = "align"
    rc = plotRun(cmdOpts = {"mode": "align"})
    if showMsg:     # Don't show msg if running via the 'on' command
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

def initOptions ():
    # Setup options from AD's default config and our own config files
    ad = axidraw.AxiDraw()
    ad.plot_setup()                 # Go into plot mode and create ad.options
    print(f"initOptions: {ad.bounds=}")
    # Copy initial ad.options into local options
    options.setFromParams(ad.params.__dict__)
    # User options override params:
    options.setFromOptions(ad.options.__dict__)

    if len(sys.argv[1:]) == 0:
        # Load default config file
        loadConfig([defaultConfigFile], True)
    else:
        # Load config files from command line 
        for arg in sys.argv[1:]:
            loadConfig(arg, True)
    # Make sure preview option is not set -- it interferes with some modes,
    # and we use it a bit differently (see plotFile()).
    options.preview = False

##########################################################################################

def main():

    signal.signal(signal.SIGINT, handleSigint)

    initOptions()

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
            #options.mode = "cycle"
            #rc = plotRun()
            runMode("cycle")
        elif shortCmd == "al":
            align()
        elif shortCmd == "vr":
            #options.mode = "version"
            #rc = plotRun()
            runMode("version")
        elif shortCmd == "sy":
            #options.mode = "sysinfo"
            #rc = plotRun()
            runMode("sysinfo")
        elif shortCmd == "tg":
            #options.mode = "toggle"
            #rc = plotRun()
            runMode("toggle")
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
            align(False);
            print("motors are on")
        elif shortCmd == "of":
            manual("disable_xy")
            print("motors are off")
        elif shortCmd == "pt":
            plotCopies(args)
        elif shortCmd == "pv":
            plotFile(args, preview=True)
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
        elif shortCmd == "dg":
            setRangeInt("digest", 0, 2, args)
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
        #elif shortCmd == "rp":
        #    setBool("report_time", args)
        #elif shortCmd == "rl":
        #    setBool("report_lifts", args)
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
        #elif shortCmd == "pa":
        #    setPaper(args)
        #elif shortCmd == "ma":
        #    setMargin(args)

        else:
            print(f"Short command '{shortCmd}' ('{cmd}') is not known.")

    # end of REPL loop

