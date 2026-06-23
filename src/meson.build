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
  'backends.py',
  'channel_time.py',
  'cue.py',
  'curve.py',
  'define.py',
  'dmx.py',
  'editor.py',
  'fader.py',
  'fader_bank.py',
  'group.py',
  'independent.py',
  'main_fader.py',
  'patch.py',
  'sequence.py',
  'settings.py',
  'step.py',
  'timer.py',
  'zoom.py',
]

install_data(
  olc_sources,
  install_dir: join_paths(python_dir, 'olc')
)


install_subdir(
  'actions',
  install_dir: join_paths(python_dir, 'olc')
)

install_subdir(
  'core',
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
  'gtk3',
  install_dir: join_paths(python_dir, 'olc')
)
