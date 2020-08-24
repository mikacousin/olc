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

### Open Lighting Architecture
To configure OLA, use the web interface on [http://localhost:9090](http://localhost:9090).

### Select channels
Note: `Buttons` are not keyboard shortcuts but the names on the virtual console. For example, button `Ch` is key `C`, `Thru` is `>`... To find keyboards shortcuts, see the menu entry in the application.
- Select channel 1: `1 Ch`
- Select channel from 1 to 10: `1 Ch 10 Thru`
- Select channel 1, 3, 5 : `1 Ch 3 + 5 +`
- Select channel from 1 to 5 and from 7 to 10: `1 Ch 10 Thru 6 -`
