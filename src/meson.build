moduledir = join_paths(pkgdatadir, 'olc')
gnome = import('gnome')

python = import('python')

#conf = configuration_data()
#conf.set('PYTHON', python.find_installation('python3').path())
#conf.set('VERSION', meson.project_version())
#conf.set('localedir', join_paths(get_option('prefix'), get_option('localedir')))
#conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'olc.in',
  output: 'olc',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir')
)

olc_sources = [
  'application.py',
  'ascii.py',
  'ascii_load.py',
  'ascii_save.py',
  'channel_time.py',
  'crossfade.py',
  'cue.py',
  'cues_edition.py',
  'curve.py',
  'curve_edition.py',
  'define.py',
  'dmx.py',
  'grand_master.py',
  'group.py',
  'independent.py',
  'independents_edition.py',
  'lightshow.py',
  'master.py',
  'masters_edition.py',
  'osc.py',
  'patch.py',
  'patch_channels.py',
  'patch_outputs.py',
  'sequence.py',
  'sequence_edition.py',
  'settings.py',
  'step.py',
  'tabs_manager.py',
  'timer.py',
  'track_channels.py',
  'virtual_console.py',
  'window.py',
  'window_channels.py',
  'window_playback.py',
  'zoom.py',
]

install_data(
  olc_sources,
  install_dir: join_paths(python_dir, 'olc')
)

install_subdir(
  'backends',
  install_dir: join_paths(python_dir, 'olc')
)

install_subdir(
  'files',
  install_dir: join_paths(python_dir, 'olc')
)

install_subdir(
  'midi',
  install_dir: join_paths(python_dir, 'olc')
)

install_subdir(
  'widgets',
  install_dir: join_paths(python_dir, 'olc')
)
