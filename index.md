![Window](https://raw.githubusercontent.com/mikacousin/olc/assets/olc.png)

## Features
- Used [Open Lighting Architecture](https://www.openlighting.org/ola/) to send DMX
- [RPN](https://en.wikipedia.org/wiki/Reverse_Polish_notation) syntax
- Open / Save ASCII files (from Congo, DLight for example)
- Patch / Unpatch by channels or by outputs
- Main Playback
- Chasers (as Sequences)
- Groups
- Masters
- Track channels
- Virtual console with easy MIDI learning for controllers
- [Open Sound Control](https://en.wikipedia.org/wiki/Open_Sound_Control)

## Documentation 
> Note:  
> `Buttons` are console keys. You can see them on the virtual console.  
> [key] are keyboard shortcuts. Combined shortcuts are written like this [key1 + key2].  
> For example, button `Ch` is key [C] on keyboard, `Thru` is [>]... To find keyboards shortcuts, see the menu entry in the application.

### Virtual console
Open with Burger menu or [Shift + Ctrl + C]
![VirtualConsole](https://raw.githubusercontent.com/mikacousin/olc/assets/virtual_console.png)

### Main window
#### Select channels
- Select channel 1: `1 Ch`
- Select channel from 1 to 10: `1 Ch 10 Thru`
- Select channel 1, 3, 5 : `1 Ch 3 + 5 +`
- Select channel from 1 to 5 and from 7 to 10: `1 Ch 10 Thru 6 -`

#### Set channels level
- Channel 1 at Full: `1 Ch 100 @`
- Channel from 1 to 5 at 50%: `1 Ch 5 Thru 50 @`
- Add 5% to selected channels: `+%`
- Substract 5% to selected channels: `-%`
> values of `+%` and `-%` can be changed in settings

#### Manipulate Steps and Preset
A Preset store channels levels
- Record Preset with next free number:  `Record`
- Record Preset 10 :  `10 Record`
- Update Preset: `Update`
A Step contains a cue and times
- Time In of 3s: [3], [Shift + I]
- Time Out of 2s: [2], [Shift + O]
- Time In and Time Out of 10s: [10], [Shift + T]
- Delay In of 1s: [1], [Shift + K]
- Delay Out of 2s: [2], [Shift + L]
- Delay In and Delay Out of 3s: [3], [Shift + D]
- Wait of 0.5s: [0.5], [Shift + W]

#### Move in Sequence
- Go: `Go`
- Jump to next step: `Seq+`
- Jump to previous step: `Seq-`
- Go to Preset 2.0: `2 Goto`
- Go to the previous Step:  `Go Back`
> Go Back Time can be changed in settings

### Open Lighting Architecture
On start-up, Open Lighting Console will launched olad if not already running.  
To configure OLA, use the web interface on [http://localhost:9090](http://localhost:9090) while olad is running.

### MIDI controllers
> For now, MIDI mapping isn't save.  
- You need to activate your controllers in settings.
- In Virtual Console, toggle MIDI button to be in learning mode.
- In Learning mode, select an object (Go for example) and push a button on on of your controllers
- You can learn as many object you want (buttons, faders)
- Toggle MIDI button to quit learning mode
- Play with buttons and faders of your controllers

### Open Sound Control
By default olc listen on port 7000 and send infos to IP address 10.0.0.3, port 9000.  
This can be changed in settings
<style>
.tablelines table, .tablelines td, .tablelines th {
        border: 1px solid black;
        }
</style>
OSC Path | Value | Command
-------- | ----- | -------
/seq/go | 1 | Go
/seq/plus | 1 | Seq+
/seq/moins | 1 | Seq-
/pad/1 | | 1
/pad/2 | | 2
/pad/3 | | 3
/pad/4 | | 4
/pad/5 | | 5
/pad/6 | | 6
/pad/7 | | 7
/pad/8 | | 8
/pad/9 | | 9
/pad/9 | | 0
/pad/dot | | .
/pad/clear | | C
/pad/channel | | Ch
/pad/thru | | Thru
/pad/plus | | +
/pad/moins | | -
/pad/all | | All
/pad/level | | @
/pad/pluspourcent | | +%
/pad/moinspourcent | | -%
/pad/ff | | Full
/subStick/flash | master(1-40), level(0-255) | Flash Master
/subStick/level | master(1-40), level(0-255) | Master at level
