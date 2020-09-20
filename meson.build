project('olc',
  version: '0.3.2.alpha',
  meson_version: '>= 0.50.0',
)

i18n = import('i18n')
py_mod = import('python')
project_id = 'com.github.mikacousin.olc'

py_installation = py_mod.find_installation('python3')
if not py_installation.found()
  error('No valid python3 binary found')
else
  message('Found python3 binary')
endif

dependency('gobject-introspection-1.0', version: '>= 1.35.0')
dependency('gtk+-3.0', version: '>= 3.22')
dependency('glib-2.0')
dependency('pygobject-3.0', version: '>= 3.29.1')
dependency('py3cairo')

pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
revision=meson.project_version()
python_dir = join_paths(get_option('prefix'), py_installation.get_install_dir())

conf = configuration_data()
conf.set('PACKAGE_URL', 'https://github.com/mikacousin/olc')
conf.set('REVISION', revision)
conf.set('localedir', join_paths(get_option('prefix'), get_option('localedir')))
conf.set('pkgdatadir', pkgdatadir)
conf.set('pythondir', python_dir)

subdir('data')
subdir('src')
subdir('po')

meson.add_install_script('build-aux/meson/postinstall.py')
