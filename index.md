[French](index.fr.md)

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
![VirtualConsole](https://raw.githubusercontent.com/mikacousin/olc/assets/virtualconsole.png)

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
Configure your controllers with:
- MIDI Notes for buttons
- MIDI Control Changes for knobs and controllers
- MIDI Control Changes or MIDI Pitchwheel for faders

Default MIDI mapping is Makie Control mode, controllers configured in this way are supported directly.

Open olc MIDI settings, activate controller(s) in MIDI In and choose the rotatives mode used by controller.
- Relative1: Infinite rotative. Values from 0 to 64 in one direction, from 127 to 65 in the other.
- Relative2: Infinite rotative. Values from 65 to 127 in one direction, from 63 to 0 in the other.
- Relative3 (Makie): Infinite rotative. Values from 0 to 64 in one direction, from 65 to 127 in the other.
- Absolute: Non infinite rotative. Values from 0 to 127. Caution, doesn't work for virtual console wheel.

> Note:  
> All rotative on a controller must be configured in the same mode

Activate controller(s) in MIDI Out for MIDI feedback (motorized faders, LED, ...)

Then:
- Open Virtual Console, toggle MIDI button to be in learning mode.
- In Learning mode, select an object (Go for example) and push a button on one of your controllers
- You can learn as many object you want (buttons, faders)
- Toggle MIDI button to quit learning mode
- Play with buttons and faders on your controllers

> Note:  
> MIDI mapping is save in ASCII files.

### Open Sound Control
By default olc listen on port 7000 and send infos to IP address 127.0.0.1, port 9000.  
This can be changed in settings
<style>
.tablelines table, .tablelines td, .tablelines th {
        border: 1px solid black;
        }
</style>
OSC Path | Value | Command
-------- | ----- | -------
/olc/key/go | | Go
/olc/key/seq+ | | Seq+
/olc/key/seq- | | Seq-
/olc/key/pause | | Pause
/olc/key/goback | | Go Back
/olc/key/1 | | 1
/olc/key/2 | | 2
/olc/key/3 | | 3
/olc/key/4 | | 4
/olc/key/5 | | 5
/olc/key/6 | | 6
/olc/key/7 | | 7
/olc/key/8 | | 8
/olc/key/9 | | 9
/olc/key/0 | | 0
/olc/key/. | | .
/olc/key/clear | | Clear Command Line
/olc/key/channel | | Channel
/olc/key/thru | | Thru
/olc/key/+ | | +
/olc/key/- | | -
/olc/key/all | | All
/olc/key/level | | @
/pad/+% | | +%
/pad/-% | | -%
/olc/key/full | | Full
/olc/fader/pageupdate | | Send Faders Page infos
/olc/fader/page | int (de 1 à 10) | Send Fader Page number
/olc/fader/1/x/label | str | Send Fader n°x (1 - 10) name
/olc/fader/page+ | | Next Faders Page
/olc/fader/page- | | Prev Faders Page
/olc/fader/1/x/level | int (de 0 à 255) | Fader n°x level
/olc/fader/1/x/flash | int (0 ou 1) | Flash Fader n°x
/olc/patch/output | | Select Output to patch
/olc/patch/thru | | Output Thru
/olc/patch/+ | | Add Output
/olc/patch/- | | Remove Output
/olc/patch/channel | | Patch Outputs to channel
/olc/patch/selected_outputs | | Send selected Outputs
