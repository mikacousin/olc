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

# hicolor icons
hicolor_icon16dir = $(datadir)/icons/hicolor/16x16/apps
hicolor_icon16_DATA = icons/hicolor/16x16/apps/olc.png
hicolor_icon22dir = $(datadir)/icons/hicolor/22x22/apps
hicolor_icon22_DATA = icons/hicolor/22x22/apps/olc.png
hicolor_icon32dir = $(datadir)/icons/hicolor/32x32/apps
hicolor_icon32_DATA = icons/hicolor/32x32/apps/olc.png
hicolor_icon48dir = $(datadir)/icons/hicolor/48x48/apps
hicolor_icon48_DATA = icons/hicolor/48x48/apps/olc.png
hicolor_icon256dir = $(datadir)/icons/hicolor/256x256/apps
hicolor_icon256_DATA = icons/hicolor/256x256/apps/olc.png
hicolor_iconsymbolicdir = $(datadir)/icons/hicolor/symbolic/apps
hicolor_iconsymbolic_DATA = icons/hicolor/symbolic/apps/olc-symbolic.svg
hicolor_icon_files = \
				$(hicolor_icon16_DATA) \
				$(hicolor_icon22_DATA) \
				$(hicolor_icon32_DATA) \
				$(hicolor_icon48_DATA) \
				$(hicolor_icon256_DATA) \
				$(hicolor_iconsymbolic_DATA) \
				icons/hicolor/olc.svg

install-data-hook: update-icon-cache
uninstall-hook: update-icon-cache
update-icon-cache:
	      @-if test -z "$(DESTDIR)"; then \
								echo "Updating Gtk hicolor icon cache."; \
								$(gtk_update_hicolor_icon_cache); \
				else \
				        echo "*** Icon cache not updated. After (un)install, run this:"; \
								echo "***   $(gtk_update_hicolor_icon_cache)"; \
				fi

gsettings_SCHEMAS = org.gnome.OpenLightingConsole.gschema.xml

# For uninstalled use
gschemas.compiled: $(gsettings_SCHEMAS) Makefile
	$(AM_V_GEN) $(GLIB_COMPILE_SCHEMAS) $(builddir)

@GSETTINGS_RULES@

EXTRA_DIST = \
	$(hicolor_icon_files) \
	$(resource_files) \
	olc.desktop.in \
	olc.gresource.xml \
	org.gnome.OpenLightingConsole.gschema.xml \
	$(NULL)

CLEANFILES = \
	olc.gresource \
	$(apps_DATA) \
	$(NULL)

all-local: gschemas.compiled
