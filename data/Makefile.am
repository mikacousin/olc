resource_files = $(shell $(GLIB_COMPILE_RESOURCES) --sourcedir=$(srcdir) --sourcedir=$(builddir) --generate-dependencies $(builddir)/olc.gresource.xml) 
olc.gresource: olc.gresource.xml $(resource_files)
	$(AM_V_GEN) $(GLIB_COMPILE_RESOURCES) --target=$@ --sourcedir=$(srcdir) --sourcedir=$(builddir) $<

resourcedir = $(pkgdatadir)
resource_DATA = olc.gresource

appsdir = $(datadir)/applications
apps_DATA = olc.desktop

@INTLTOOL_DESKTOP_RULE@

#appdatadir = $(datadir)/appdata
#appdata_DATA = $(appdata_in_files:.xml.in=.xml)
#appdata_in_files = olc.appdata.xml.in

@INTLTOOL_XML_RULE@

gsettings_SCHEMAS = org.gnome.OpenLightingConsole.gschema.xml

# For uninstalled use
gschemas.compiled: $(gsettings_SCHEMAS) Makefile
	$(AM_V_GEN) $(GLIB_COMPILE_SCHEMAS) $(builddir)

EXTRA_DIST = \
	$(resource_files) \
	olc.desktop.in \
	$(NULL)

CLEANFILES = \
	olc.gresource \
	$(apps_DATA) \
	$(NULL)

all-local: gschemas.compiled
