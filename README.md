
# Open Lighting Console

Open Lighting Console (olc) is a software to control lights on shows.

##Depends on
- gtk3 >= 3.20
- python3
- python-gobject
- gobject-introspection
- ola (with python3 support) 
- portmidi
- mido (installed via pip)
- liblo (python-pyliblo on archlinux)

##Building from git
```
$ git clone https://github.com/mikacousin/olc.git
$ cd olc
$ ./autogen.sh
$ make
# make install
```
