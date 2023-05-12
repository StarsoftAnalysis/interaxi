# adrepl

A simple [REPL](https://en.wikipedia.org/wiki/Read%E2%80%93eval%E2%80%93print_loop) console for AxiDraw.

I've found that running AxiDraw commands from the command line is slow,
especially on an old Raspberry Pi B+,
so I wrote this wrapper using the Python API.

Run ```adrepl.py``` or ```python adrepl.py```, and then 
follow the prompts and enter commands to control the plotter.

## Commands

Some commands have synonyms to be consistent with the original axicli commands.  For example `x` and `walk_x` do the same thing.

All commands are changed to lower case before processing (except for file names).

Yes/No options turn a setting on or off.  They can be specified with any of 'yes'/'no', 'true'/'false', 'on'/'off', or '1','0' (or abbreviations of those words).

### `accel <1-100>`
Set the acceleration to a value from 1 to 100.
### `align`
Run the align command, which disengages the plotter's motors and allows the head to be manually moved -- usually to the origin.
`adrepl` asks if you have moved the head to the origin, so that it can then keep track of movements and prevent the
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
### `home|walk_home`
Move the pen to the current home position (as defined by the last time the motors were enabled,
either with `on`, `align`, or `sethome`.
### `ls`
List the plottable (.svg) files in the current directory.
### `model [<num>]`
Set the AxiDraw model number: 
    1 - AxiDraw V2, V3, or SE/A4
    2 - AxiDraw V3/A3 or SE/A3
    3 - AxiDraw V3 XLX
    4 - AxiDraw MiniKit
    5 - AxiDraw SE/A1
    6 - AxiDraw SE/A2
    7 - AxiDraw V3/B6
### `off|disable_xy`
Turn the x/y stepper motors off.
### `on|enable_xy`
Turn the x/y stepper motors on.
### `options|config [<filename>]`
Load the options (aka configuration) from the AxiDraw configuration file specified.  If no filename is given,
display the current options.
### `plot <filename> [<layer>]`
Run the plot from the given filename.  If a layer number (1-1000) is given, plot only that layer.
### `posdown|pen_pos_down <0-100>`
Set the down position of the pen (as a percentage of the total travel of the servo).
### `position`
Display the current head position (if known).
### `posup|pen_pos_up <0-100>`
Set the up position of the pen (as a percentage of the total travel of the servo).
### `preview <y/n>`
Turn on previewing -- no plotting will be done until this option is turned off again.
### `quit` | `Ctrl-C` | `Ctrl-D`
Leave `adrepl`.  The current configuration will not be saved automatically.
### `random_start <y/n>`
Turn the random start feature on or off.
### `ratedown|pen_rate_lower <1-100>`
Set the speed that the pen moves down as a percentage of the maximum.
### `rateup|pen_rate_raise <1-100>`
Set the speed that the pen moves up as a percentage of the maximum.
### `register`
Start pen registration -- see below.
### `render <0-3>`
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
use the default name (`~/.config/adrepl/axidraw_config.py`).
### `speeddown|speed_pendown <1-100>`
Set the plotting speed when the pen is down, as a percentage of the maximum.
### `speedup|speed_penup <1-100>`
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
Display the software version.
### `walkx|x <distance>`
### `walky|y <distance>`

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
    q - quit -- complete the registration

## Requirements

* Python 3.5 or later
...
