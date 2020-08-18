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
  'ascii_save.py',
  'channel_time.py',
  'crossfade.py',
  'cue.py',
  'cues_edition.py',
  'define.py',
  'dmx.py',
  'enttec_wing.py',
  'group.py',
  'master.py',
  'masters_edition.py',
  'midi.py',
  'ola_thread.py',
  'osc.py',
  'patch_channels.py',
  'patch_outputs.py',
  'sequence.py',
  'sequence_edition.py',
  'settings.py',
  'step.py',
  'track_channels.py',
  'virtual_console.py',
  'widgets.py',
  'widgets_button.py',
  'widgets_channel.py',
  'widgets_fader.py',
  'widgets_flash.py',
  'widgets_go.py',
  'widgets_grand_master.py',
  'widgets_group.py',
  'widgets_patch_channels.py',
  'widgets_patch_outputs.py',
  'widgets_sequential.py',
  'widgets_track_channels.py',
  'window.py',
]

install_data(
  olc_sources,
  install_dir: join_paths(python_dir, 'olc')
)
