# interaxi

A simple [REPL](https://en.wikipedia.org/wiki/Read%E2%80%93eval%E2%80%93print_loop) console for AxiDraw.

I've found that running AxiDraw commands from the command line is slow,
especially on an old Raspberry Pi B+,
so I wrote this wrapper using the Python API.

Run ```interaxi.py``` or ```python interaxi.py```, and then 
follow the prompts and enter commands to control the plotter.

By default, interaxi.py reads its initial configuration from `<homedir>/.config/interaxi/axidraw_conf.py`.  
An alternative configuration file can be given on the command line, e.g.
```
interaxi.py special_conf.py
```
Configurations can also be loaded from within interaxi using the `config` or `options` commands.

## Commands

Some commands have synonyms to be consistent with the original axicli commands.  For example `x` and `walk_x` do the same thing.

All commands are changed to lower case before processing (except for file names).

Yes/No options turn a setting on or off.  They can be specified with any of 'yes'/'no', 'true'/'false', 'on'/'off', or '1','0' (or abbreviations of those words).

### `accel <1-100>`
Set the acceleration to a value from 1 to 100.
### `align`
Run the align command, which disengages the plotter's motors and allows the head to be manually moved -- usually to the origin.
`interaxi` asks if you have moved the head to the origin, so that it can then keep track of movements and prevent the
head from moving out of range.
### `auto_rotate <y/n>`
Turn auto-rotate on or off.  If on, the plot may be rotated to make sure that it fits on the plotting area.
### `cd [<directory>]`
Change the current directory to the one specified.  On its own, `cd` displays the name of the current working directory.
### `const_speed <y/n>`
Turn constant speed plotting on or off.
### `copies <0-9999>`
Specify the number of copies to plot.
### `cycle`
Move the pen down and then up.
### `delaydown|pen_delay_down <ms>`
Set the delay in milliseconds between the pen being lowered, and movement starting.
### `delaypage|page_delay <s>`
Set the delay in seconds between copies.
### `delayup|pen_delay_up <ms>`
Set the delay in milliseconds between movement stopping and the pen being raised.
### `down|lower_pen`
Move the pen down.
### `fw_version`
Display the firmware version.
### `help`
Display a brief reminder of the available commands.
### `hiding <y/n>`
Turn the AxiDraw's [hidden line removal feature](https://www.evilmadscientist.com/2023/hidden-paths-axidraw/) on or off.
### `home|walk_home`
Move the pen to the current home position (as defined by the last time the motors were enabled,
either with `on`, `align`, or `sethome`.
### `ls`
List the plottable (.svg) files in the current directory.
### `model [<num>]`
Set the AxiDraw model number: 
1 AxiDraw V2, V3, or SE/A4
2 AxiDraw V3/A3 or SE/A3
3 AxiDraw V3 XLX
4 AxiDraw MiniKit
5 AxiDraw SE/A1
6 AxiDraw SE/A2
7 AxiDraw V3/B6
### `off|disable_xy`
Turn the x/y stepper motors off.
### `on|enable_xy`
Turn the x/y stepper motors on.
### `options|config [<filename>]`
Load the options (aka configuration) from the AxiDraw configuration file specified.  If no filename is given,
display the current options.
### `output <filename>`
The plot (or preview) command will create an output file if you specify a file name.
    none - do not create an output file
    auto - generate the output file name automatically (currently by adding '.svg' to the input file name).
    <filename> - use the given file name.
WARNING: If the specified file already exists, it will be overwritten.
### `plot <filename> [<layer>]`
Run the plot from the given filename.  If a layer number (1-1000) is given, plot only that layer.
Don't put quotation marks `"` or `'` around the file name, even if it contains spaces.
Examples: `plot file1.svg` `plot file1.svg 3` `file with spaces.svg` `file layer two.svg 2`
### `posdown|pen_pos_down <0-100>`
Set the down position of the pen (as a percentage of the total travel of the servo).
### `position`
Display the current head position (if known).
### `posup|pen_pos_up <0-100>`
Set the up position of the pen (as a percentage of the total travel of the servo).
### `preview <filename> [<layer>]`
Run the plot in preview mode -- the pen will not move, but the estimated time will be reported.
This will also create an output file if you have set an output file name.
### `quit` | `Ctrl-C` | `Ctrl-D`
Leave `interaxi`.  The current configuration will not be saved automatically.
### `random_start <y/n>`
Turn the random start feature on or off.
### `ratedown|pen_rate_lower <1-100>`
Set the speed that the pen moves down as a percentage of the maximum.
### `rateup|pen_rate_raise <1-100>`
Set the speed that the pen moves up as a percentage of the maximum.
### `register`
Start pen registration -- see below.
### `render <0-3>`
When previewing with an output filename set, a preview of what would have been plotted
can be created.
    0 - Do not render previews
    1 - Render pen-down movement only
    2 - Render pen-up movement only
    3 - Render all movement, both pen-up and pen-down [DEFAULT]
The render option changes the content of the output SVG file, so it has no effect
unless an output file name has been specified.
### `reordering <0-4>`
    0 - Least; Only connect adjoining paths. [DEFAULT]
    1 - Basic; Also reorder paths for speed
    2 - Full; Also allow path reversal
    3 - [Deprecated; currently gives same behavior as 2.]
    4 - None; Strictly preserve file order
### `report_time <y/n>`
Turn plot reporting on or off.
### `save [<filename>]`
Save the current configuration (aka options) to the specified file.  If no file name is given,
use the default name (`~/.config/interaxi/axidraw_config.py`).
### `speeddown|speed_pendown|sd <1-100>`
Set the plotting speed when the pen is down, as a percentage of the maximum.
### `speedup|speed_penup|su <1-100>`
Set the plotting speed when the pen is up, as a percentage of the maximum.
### `sysinfo`
Display system information.
### `toggle`
Toggle the pen up or down.
### `units <mm>|<inches>`
Set the units for future commands to either millimetres or inches.
### `up|raise_pen`
Move the pen up.
### `version`
Display the Python API software version.
### `walk_home`
See `home`.
### `walkx|x <distance>`
Move <distance> (in the current units) horizontally, relative to the current position.  Positive values move to the right, negative ones to the left.  WARNING re limits.
### `walky|y <distance>`
Move <distance> (in the current units) vertically, relative to the current position.  Positive values move down, negative ones up.  WARNING re limits.

## Registering

The `register` command starts interactive control of the pen position.  Use the arrow keys to move the head by small amounts
to help with registering layers (i.e. plots with different pens) onto each other.  

While registering, use these keys:

    <up arrow> - move the pen in the negative Y direction
    <down arrow> - move the pen in the positive Y direction
    <left arrow> - move the pen in the negative X direction
    <right arrow> - move the pen in the positive X direction
    u - raise the pen
    d - lower the pen
    f - fine movements (0.1mm or 0.005in)
    m - fine movements (1mm or 0.05in)
    c - fine movements (10mm or 0.5in)
    r - return to the home position
    q - quit -- complete the registration

## Requirements

* Python 3.5 or later

## Issues

* It needs a better name.
* The documentation is incomplete.
* Lots of others, probably.
