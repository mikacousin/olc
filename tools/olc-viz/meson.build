viz_opt = get_option('viz')
cargo = find_program('cargo', required: viz_opt)

if cargo.found() and not viz_opt.disabled()
  is_release = get_option('buildtype') in ['release', 'debugoptimized']
  profile_dir = is_release ? 'release' : 'debug'
  cargo_profile_flag = is_release ? '--release' : ''

  viz_sources = files(
    'Cargo.toml',
    'Cargo.lock',
    'crates/viz-core/Cargo.toml',
    'crates/viz-core/src/lib.rs',
    'crates/viz-source/Cargo.toml',
    'crates/viz-source/src/lib.rs',
    'crates/viz-render/Cargo.toml',
    'crates/viz-render/src/lib.rs',
    'crates/viz-render/src/math.rs',
    'crates/viz-render/src/camera.rs',
    'crates/viz-render/src/dmx_eval.rs',
    'crates/viz-render/src/mesh.rs',
    'crates/viz-app/Cargo.toml',
    'crates/viz-app/src/main.rs',
  )

  custom_target(
    'olc-viz',
    input: viz_sources,
    output: 'olc-viz',
    build_by_default: true,
    console: true,
    install: true,
    install_dir: get_option('bindir'),
    command: [
      'sh',
      '-c',
      'cargo build --manifest-path "$1" --target-dir "$2" -p viz-app $3 && cp "$2/$4/olc-viz" "$5"',
      '_',
      meson.current_source_dir() / 'Cargo.toml',
      meson.current_build_dir() / 'target',
      cargo_profile_flag,
      profile_dir,
      '@OUTPUT@',
    ],
  )
endif
