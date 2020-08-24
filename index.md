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

## Documentation 
> Note:
> `Buttons` are console keys. You can see them on the virtual console.
> [key] are keyboard shortcuts. Combined shortcuts are written like this [key1 + key2].
> For example, button `Ch` is key [C] on keyboard, `Thru` is [>]... To find keyboards shortcuts, see the menu entry in the application.

### Virtual console
Open with Burger menu or [Shift + Ctrl + C]
![VirtualConsole](https://raw.githubusercontent.com/mikacousin/olc/assets/virtual_console.png)

### Select channels
- Select channel 1: `1 Ch`
- Select channel from 1 to 10: `1 Ch 10 Thru`
- Select channel 1, 3, 5 : `1 Ch 3 + 5 +`
- Select channel from 1 to 5 and from 7 to 10: `1 Ch 10 Thru 6 -`

### Set channels level
- Channel 1 at Full: `1 Ch 100 @`
- Channel from 1 to 5 at 50%: `1 Ch 5 Thru 50 @`
- Add 5% to selected channels: `+%`
- Substract 5% to selected channels: `-%`
> values of `+%` and `-%` can be changed in settings

### Open Lighting Architecture
On start-up, Open Lighting Console will launched olad if not already running.  
To configure OLA, use the web interface on [http://localhost:9090](http://localhost:9090) while olad is running.
