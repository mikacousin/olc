//! 3D rendering (wgpu): analytically lit floor, procedural fixtures, and orbital camera.

pub mod camera;
pub mod dmx_eval;
pub mod gobo;
pub mod math;
pub mod mesh;

use std::collections::HashMap;
use std::sync::Arc;

use bytemuck::{Pod, Zeroable};
use viz_core::Stage;

use crate::camera::OrbitCamera;
use crate::dmx_eval::{GoboWheelState, ResolvedFixture};
use crate::gobo::{
    decode_png_to_gobo_layer, generate_builtin_layer, generate_mipmaps, resolve_builtin_index,
    BUILTIN_COUNT, GOBO_MIP_LEVELS, GOBO_SIZE, MAX_GOBO_LAYERS,
};
use crate::math::{cross3, normalize3, parse_hex_color};
use crate::mesh::{build_beams_mesh, build_fixtures_mesh, BeamVertex, FixtureVertex};

pub const MAX_LIGHTS: usize = 64;

/// Data passed to the `wgpu` callback to render a frame.
#[derive(Clone)]
pub struct RenderScene {
    pub camera: OrbitCamera,
    pub stage: Stage,
    pub fixtures: Arc<Vec<ResolvedFixture>>,
    pub selected_channel: Option<u32>,
    pub aspect: f32,
    pub gobo_images: Arc<HashMap<String, Vec<u8>>>,
    pub scenery: Arc<Vec<viz_core::SceneryMesh>>,
    pub show_scenery: bool,
}

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
struct SceneryVertex {
    pos: [f32; 3],
    normal: [f32; 3],
    color: [f32; 3],
}

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
struct SceneUniform {
    view_proj: [[f32; 4]; 4],
    stage_size_grid: [f32; 4], // width, depth, grid_spacing, fog_density
    stage_color_count: [f32; 4], // r, g, b, light_count
    cam_eye: [f32; 4],         // x, y, z, 0
}

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
struct SpotLightGpu {
    pos_intensity: [f32; 4],    // x, y, z, intensity
    dir_cos_outer: [f32; 4],    // dx, dy, dz, cos(outer_half)
    color_cos_inner: [f32; 4],  // r, g, b, cos(inner_half)
    right_gobo: [f32; 4],       // rx, ry, rz, gobo1_layer
    rot_blur: [f32; 4],         // cos(rot1), sin(rot1), blur_lod, 0
    gobo2_rot_layer: [f32; 4],  // cos(rot2), sin(rot2), gobo2_layer, 0
}

const FLOOR_SHADER: &str = r#"
struct SceneUniform {
    view_proj: mat4x4<f32>,
    stage_size_grid: vec4<f32>,
    stage_color_count: vec4<f32>,
    cam_eye: vec4<f32>,
};

struct SpotLight {
    pos_intensity: vec4<f32>,
    dir_cos_outer: vec4<f32>,
    color_cos_inner: vec4<f32>,
    right_gobo: vec4<f32>,
    rot_blur: vec4<f32>,
    gobo2_rot_layer: vec4<f32>,
};

@group(0) @binding(0) var<uniform> u_scene: SceneUniform;
@group(0) @binding(1) var<storage, read> u_lights: array<SpotLight>;
@group(0) @binding(2) var t_gobos: texture_2d_array<f32>;
@group(0) @binding(3) var s_gobos: sampler;

struct VsOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) world_pos: vec3<f32>,
};

@vertex
fn vs_main(@builtin(vertex_index) vid: u32) -> VsOut {
    var corners = array<vec2<f32>, 6>(
        vec2<f32>(-0.5, -0.5),
        vec2<f32>( 0.5, -0.5),
        vec2<f32>( 0.5,  0.5),
        vec2<f32>(-0.5, -0.5),
        vec2<f32>( 0.5,  0.5),
        vec2<f32>(-0.5,  0.5),
    );
    let c = corners[vid];
    let wp = vec3<f32>(c.x * u_scene.stage_size_grid.x, c.y * u_scene.stage_size_grid.y, 0.0);
    var out: VsOut;
    out.clip = u_scene.view_proj * vec4<f32>(wp, 1.0);
    out.world_pos = wp;
    return out;
}

@fragment
fn fs_main(in: VsOut) -> @location(0) vec4<f32> {
    var base = u_scene.stage_color_count.rgb;
    let spacing = u_scene.stage_size_grid.z;
    if (spacing > 0.01) {
        let coord = in.world_pos.xy / spacing;
        let grid = abs(fract(coord - 0.5) - 0.5) / max(fwidth(coord), vec2<f32>(0.0005));
        let line = 1.0 - min(min(grid.x, grid.y), 1.0);
        base = mix(base, base + vec3<f32>(0.09, 0.09, 0.11), line * 0.6);

        let ax_x = 1.0 - min(abs(in.world_pos.y) / max(fwidth(in.world_pos.y), 0.001), 1.0);
        let ax_y = 1.0 - min(abs(in.world_pos.x) / max(fwidth(in.world_pos.x), 0.001), 1.0);
        base = mix(base, vec3<f32>(0.45, 0.14, 0.14), ax_x * 0.45);
        base = mix(base, vec3<f32>(0.14, 0.42, 0.18), ax_y * 0.45);
    }

    var accum = base * 0.28;
    let count = u32(u_scene.stage_color_count.w);
    let n = vec3<f32>(0.0, 0.0, 1.0);
    for (var i = 0u; i < count; i = i + 1u) {
        let l = u_lights[i];
        let to_frag = in.world_pos - l.pos_intensity.xyz;
        let dist = length(to_frag);
        if (dist > 0.01) {
            let ldir = to_frag / dist;
            let cos_theta = dot(ldir, l.dir_cos_outer.xyz);
            let cone = smoothstep(l.dir_cos_outer.w, l.color_cos_inner.w, cos_theta);
            let ndotl = max(dot(-ldir, n), 0.0);
            let atten = 1.0 / (1.0 + 0.035 * dist * dist);

            var gobo_mask = 1.0;
            let g_layer1 = i32(l.right_gobo.w + 0.5);
            let g_layer2 = i32(l.gobo2_rot_layer.z + 0.5);
            let z_proj = dot(ldir, l.dir_cos_outer.xyz);
            if ((g_layer1 > 0 || g_layer2 > 0) && z_proj > 0.05) {
                let right0 = l.right_gobo.xyz;
                let up0 = cross(l.dir_cos_outer.xyz, right0);
                let cos_o = clamp(l.dir_cos_outer.w, 0.05, 0.999);
                let tan_half = sqrt(max(1.0 - cos_o * cos_o, 0.0)) / cos_o;
                let denom = z_proj * max(tan_half, 0.02);
                let dx = dot(ldir, right0) / denom * 0.5;
                let dy = dot(ldir, up0) / denom * 0.5;
                if (g_layer1 > 0) {
                    let cr1 = l.rot_blur.x;
                    let sr1 = l.rot_blur.y;
                    let u1 = dx * cr1 + dy * sr1 + 0.5;
                    let v1 = dy * cr1 - dx * sr1 + 0.5;
                    if (u1 >= 0.0 && u1 <= 1.0 && v1 >= 0.0 && v1 <= 1.0) {
                        gobo_mask = gobo_mask * textureSampleLevel(t_gobos, s_gobos, vec2<f32>(u1, v1), g_layer1, l.rot_blur.z).r;
                    } else {
                        gobo_mask = 0.0;
                    }
                }
                if (g_layer2 > 0) {
                    let cr2 = l.gobo2_rot_layer.x;
                    let sr2 = l.gobo2_rot_layer.y;
                    let u2 = dx * cr2 + dy * sr2 + 0.5;
                    let v2 = dy * cr2 - dx * sr2 + 0.5;
                    if (u2 >= 0.0 && u2 <= 1.0 && v2 >= 0.0 && v2 <= 1.0) {
                        gobo_mask = gobo_mask * textureSampleLevel(t_gobos, s_gobos, vec2<f32>(u2, v2), g_layer2, l.rot_blur.z).r;
                    } else {
                        gobo_mask = 0.0;
                    }
                }
            }

            let contrib = l.color_cos_inner.rgb * l.pos_intensity.w * cone * ndotl * atten * gobo_mask * 2.8;
            accum = accum + contrib * (base * 1.4 + vec3<f32>(0.12));
        }
    }
    let mapped = accum / (accum + vec3<f32>(1.0));
    return vec4<f32>(mapped, 1.0);
}
"#;

const SCENERY_SHADER: &str = r#"
struct SceneUniform {
    view_proj: mat4x4<f32>,
    stage_size_grid: vec4<f32>,
    stage_color_count: vec4<f32>,
    cam_eye: vec4<f32>,
};

struct SpotLight {
    pos_intensity: vec4<f32>,
    dir_cos_outer: vec4<f32>,
    color_cos_inner: vec4<f32>,
    right_gobo: vec4<f32>,
    rot_blur: vec4<f32>,
    gobo2_rot_layer: vec4<f32>,
};

@group(0) @binding(0) var<uniform> u_scene: SceneUniform;
@group(0) @binding(1) var<storage, read> u_lights: array<SpotLight>;
@group(0) @binding(2) var t_gobos: texture_2d_array<f32>;
@group(0) @binding(3) var s_gobos: sampler;

struct VsIn {
    @location(0) pos: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) color: vec3<f32>,
};

struct VsOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) world_pos: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) color: vec3<f32>,
};

@vertex
fn vs_main(in: VsIn) -> VsOut {
    var out: VsOut;
    out.clip = u_scene.view_proj * vec4<f32>(in.pos, 1.0);
    out.world_pos = in.pos;
    out.normal = in.normal;
    out.color = in.color;
    return out;
}

@fragment
fn fs_main(in: VsOut) -> @location(0) vec4<f32> {
    let base = in.color;
    let n = normalize(in.normal);
    var accum = base * 0.28;
    let count = u32(u_scene.stage_color_count.w);
    for (var i = 0u; i < count; i = i + 1u) {
        let l = u_lights[i];
        let to_frag = in.world_pos - l.pos_intensity.xyz;
        let dist = length(to_frag);
        if (dist > 0.01) {
            let ldir = to_frag / dist;
            let cos_theta = dot(ldir, l.dir_cos_outer.xyz);
            let cone = smoothstep(l.dir_cos_outer.w, l.color_cos_inner.w, cos_theta);
            let ndotl = max(abs(dot(-ldir, n)), 0.0);
            let atten = 1.0 / (1.0 + 0.035 * dist * dist);

            var gobo_mask = 1.0;
            let g_layer1 = i32(l.right_gobo.w + 0.5);
            let g_layer2 = i32(l.gobo2_rot_layer.z + 0.5);
            let z_proj = dot(ldir, l.dir_cos_outer.xyz);
            if ((g_layer1 > 0 || g_layer2 > 0) && z_proj > 0.05) {
                let right0 = l.right_gobo.xyz;
                let up0 = cross(l.dir_cos_outer.xyz, right0);
                let cos_o = clamp(l.dir_cos_outer.w, 0.05, 0.999);
                let tan_half = sqrt(max(1.0 - cos_o * cos_o, 0.0)) / cos_o;
                let denom = z_proj * max(tan_half, 0.02);
                let dx = dot(ldir, right0) / denom * 0.5;
                let dy = dot(ldir, up0) / denom * 0.5;
                if (g_layer1 > 0) {
                    let cr1 = l.rot_blur.x;
                    let sr1 = l.rot_blur.y;
                    let u1 = dx * cr1 + dy * sr1 + 0.5;
                    let v1 = dy * cr1 - dx * sr1 + 0.5;
                    if (u1 >= 0.0 && u1 <= 1.0 && v1 >= 0.0 && v1 <= 1.0) {
                        gobo_mask = gobo_mask * textureSampleLevel(t_gobos, s_gobos, vec2<f32>(u1, v1), g_layer1, l.rot_blur.z).r;
                    } else {
                        gobo_mask = 0.0;
                    }
                }
                if (g_layer2 > 0) {
                    let cr2 = l.gobo2_rot_layer.x;
                    let sr2 = l.gobo2_rot_layer.y;
                    let u2 = dx * cr2 + dy * sr2 + 0.5;
                    let v2 = dy * cr2 - dx * sr2 + 0.5;
                    if (u2 >= 0.0 && u2 <= 1.0 && v2 >= 0.0 && v2 <= 1.0) {
                        gobo_mask = gobo_mask * textureSampleLevel(t_gobos, s_gobos, vec2<f32>(u2, v2), g_layer2, l.rot_blur.z).r;
                    } else {
                        gobo_mask = 0.0;
                    }
                }
            }

            let contrib = l.color_cos_inner.rgb * l.pos_intensity.w * cone * ndotl * atten * gobo_mask * 2.5;
            accum = accum + contrib * (base * 1.4 + vec3<f32>(0.10));
        }
    }
    let mapped = accum / (accum + vec3<f32>(1.0));
    return vec4<f32>(mapped, 1.0);
}
"#;

const FIXTURE_SHADER: &str = r#"
struct SceneUniform {
    view_proj: mat4x4<f32>,
    stage_size_grid: vec4<f32>,
    stage_color_count: vec4<f32>,
    cam_eye: vec4<f32>,
};

@group(0) @binding(0) var<uniform> u_scene: SceneUniform;

struct VsIn {
    @location(0) pos: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) color: vec3<f32>,
    @location(3) emissive: f32,
};

struct VsOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) normal: vec3<f32>,
    @location(1) color: vec3<f32>,
    @location(2) emissive: f32,
};

@vertex
fn vs_main(in: VsIn) -> VsOut {
    var out: VsOut;
    out.clip = u_scene.view_proj * vec4<f32>(in.pos, 1.0);
    out.normal = in.normal;
    out.color = in.color;
    out.emissive = in.emissive;
    return out;
}

@fragment
fn fs_main(in: VsOut) -> @location(0) vec4<f32> {
    let key = normalize(vec3<f32>(0.4, -0.5, 0.8));
    let ndotl = max(dot(normalize(in.normal), key), 0.0);
    let lit = in.color * (0.35 + 0.65 * ndotl) + in.color * in.emissive;
    let mapped = lit / (lit + vec3<f32>(1.0));
    return vec4<f32>(mapped, 1.0);
}
"#;

const BEAM_SHADER: &str = r#"
struct SceneUniform {
    view_proj: mat4x4<f32>,
    stage_size_grid: vec4<f32>,
    stage_color_count: vec4<f32>,
    cam_eye: vec4<f32>,
};

@group(0) @binding(0) var<uniform> u_scene: SceneUniform;
@group(0) @binding(1) var t_gobos: texture_2d_array<f32>;
@group(0) @binding(2) var s_gobos: sampler;

struct VsIn {
    @location(0) pos: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) color: vec3<f32>,
    @location(3) alpha: f32,
    @location(4) gobo_uv: vec3<f32>,
    @location(5) gobo2_uv: vec3<f32>,
};

struct VsOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) world_pos: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) color: vec3<f32>,
    @location(3) alpha: f32,
    @location(4) gobo_uv: vec3<f32>,
    @location(5) gobo2_uv: vec3<f32>,
};

@vertex
fn vs_main(in: VsIn) -> VsOut {
    var out: VsOut;
    out.clip = u_scene.view_proj * vec4<f32>(in.pos, 1.0);
    out.world_pos = in.pos;
    out.normal = in.normal;
    out.color = in.color;
    out.alpha = in.alpha;
    out.gobo_uv = in.gobo_uv;
    out.gobo2_uv = in.gobo2_uv;
    return out;
}

@fragment
fn fs_main(in: VsOut) -> @location(0) vec4<f32> {
    let view_dir = normalize(u_scene.cam_eye.xyz - in.world_pos);
    let ndotv = abs(dot(normalize(in.normal), view_dir));
    let edge = pow(ndotv, 1.6);
    var streak = 1.0;
    let g_layer1 = i32(in.gobo_uv.z + 0.5);
    let g_layer2 = i32(in.gobo2_uv.z + 0.5);
    if (g_layer1 > 0 || g_layer2 > 0) {
        var sample_m = 1.0;
        if (g_layer1 > 0) {
            let uv1 = vec2<f32>(0.5 + 0.36 * in.gobo_uv.x, 0.5 + 0.36 * in.gobo_uv.y);
            sample_m = sample_m * textureSampleLevel(t_gobos, s_gobos, uv1, g_layer1, 1.0).r;
        }
        if (g_layer2 > 0) {
            let uv2 = vec2<f32>(0.5 + 0.36 * in.gobo2_uv.x, 0.5 + 0.36 * in.gobo2_uv.y);
            sample_m = sample_m * textureSampleLevel(t_gobos, s_gobos, uv2, g_layer2, 1.0).r;
        }
        streak = 0.25 + 0.75 * sample_m;
    }
    let rgb = in.color * in.alpha * edge * streak * 0.52;
    return vec4<f32>(rgb, 1.0);
}
"#;

const BLIT_SHADER: &str = r#"
@group(0) @binding(0) var t_color: texture_2d<f32>;
@group(0) @binding(1) var s_color: sampler;

struct VsOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) uv: vec2<f32>,
};

@vertex
fn vs_main(@builtin(vertex_index) vid: u32) -> VsOut {
    var pos = array<vec2<f32>, 6>(
        vec2<f32>(-1.0, -1.0),
        vec2<f32>( 1.0, -1.0),
        vec2<f32>( 1.0,  1.0),
        vec2<f32>(-1.0, -1.0),
        vec2<f32>( 1.0,  1.0),
        vec2<f32>(-1.0,  1.0),
    );
    var uvs = array<vec2<f32>, 6>(
        vec2<f32>(0.0, 1.0),
        vec2<f32>(1.0, 1.0),
        vec2<f32>(1.0, 0.0),
        vec2<f32>(0.0, 1.0),
        vec2<f32>(1.0, 0.0),
        vec2<f32>(0.0, 0.0),
    );
    var out: VsOut;
    out.clip = vec4<f32>(pos[vid], 0.0, 1.0);
    out.uv = uvs[vid];
    return out;
}

@fragment
fn fs_main(in: VsOut) -> @location(0) vec4<f32> {
    return textureSample(t_color, s_color, in.uv);
}
"#;

struct GpuResources {
    floor_pipeline: wgpu::RenderPipeline,
    scenery_pipeline: wgpu::RenderPipeline,
    fixture_pipeline: wgpu::RenderPipeline,
    beam_pipeline: wgpu::RenderPipeline,
    blit_pipeline: wgpu::RenderPipeline,
    blit_bgl: wgpu::BindGroupLayout,
    blit_sampler: wgpu::Sampler,
    blit_bind_group: Option<wgpu::BindGroup>,
    uniform_buf: wgpu::Buffer,
    lights_buf: wgpu::Buffer,
    floor_bind_group: wgpu::BindGroup,
    fixture_bind_group: wgpu::BindGroup,
    beam_bind_group: wgpu::BindGroup,
    gobo_tex: wgpu::Texture,
    gobo_layers: HashMap<String, u32>,
    next_gobo_layer: u32,
    scenery_vbuf: Option<wgpu::Buffer>,
    scenery_vcount: u32,
    last_scenery_key: (usize, usize),
    fixture_vbuf: Option<wgpu::Buffer>,
    fixture_vcount: u32,
    beam_vbuf: Option<wgpu::Buffer>,
    beam_vcount: u32,
    color_view: Option<wgpu::TextureView>,
    depth_view: Option<wgpu::TextureView>,
    rt_size: [u32; 2],
    target_format: wgpu::TextureFormat,
}

impl GpuResources {
    fn new(device: &wgpu::Device, target_format: wgpu::TextureFormat) -> Self {
        let uniform_buf = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("viz_scene_uniform"),
            size: std::mem::size_of::<SceneUniform>() as u64,
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });
        let lights_buf = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("viz_spot_lights"),
            size: (std::mem::size_of::<SpotLightGpu>() * MAX_LIGHTS) as u64,
            usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });

        let gobo_tex = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("viz_gobo_atlas"),
            size: wgpu::Extent3d {
                width: GOBO_SIZE,
                height: GOBO_SIZE,
                depth_or_array_layers: MAX_GOBO_LAYERS,
            },
            mip_level_count: GOBO_MIP_LEVELS,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::R8Unorm,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
            view_formats: &[],
        });
        let gobo_view = gobo_tex.create_view(&wgpu::TextureViewDescriptor {
            dimension: Some(wgpu::TextureViewDimension::D2Array),
            ..Default::default()
        });
        let gobo_sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("viz_gobo_sampler"),
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            mipmap_filter: wgpu::MipmapFilterMode::Linear,
            address_mode_u: wgpu::AddressMode::ClampToEdge,
            address_mode_v: wgpu::AddressMode::ClampToEdge,
            ..Default::default()
        });

        let floor_bgl = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("viz_floor_bgl"),
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::VERTEX_FRAGMENT,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Storage { read_only: true },
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 2,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Texture {
                        sample_type: wgpu::TextureSampleType::Float { filterable: true },
                        view_dimension: wgpu::TextureViewDimension::D2Array,
                        multisampled: false,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 3,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                    count: None,
                },
            ],
        });
        let floor_bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("viz_floor_bg"),
            layout: &floor_bgl,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: uniform_buf.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: lights_buf.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 2,
                    resource: wgpu::BindingResource::TextureView(&gobo_view),
                },
                wgpu::BindGroupEntry {
                    binding: 3,
                    resource: wgpu::BindingResource::Sampler(&gobo_sampler),
                },
            ],
        });

        let fixture_bgl = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("viz_fixture_bgl"),
            entries: &[wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::VERTEX_FRAGMENT,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: false,
                    min_binding_size: None,
                },
                count: None,
            }],
        });
        let fixture_bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("viz_fixture_bg"),
            layout: &fixture_bgl,
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: uniform_buf.as_entire_binding(),
            }],
        });

        let depth_state = Some(wgpu::DepthStencilState {
            format: wgpu::TextureFormat::Depth32Float,
            depth_write_enabled: Some(true),
            depth_compare: Some(wgpu::CompareFunction::Less),
            stencil: wgpu::StencilState::default(),
            bias: wgpu::DepthBiasState::default(),
        });

        let floor_shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("viz_floor_shader"),
            source: wgpu::ShaderSource::Wgsl(FLOOR_SHADER.into()),
        });
        let floor_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("viz_floor_layout"),
            bind_group_layouts: &[Some(&floor_bgl)],
            immediate_size: 0,
        });
        let floor_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("viz_floor_pipeline"),
            layout: Some(&floor_layout),
            vertex: wgpu::VertexState {
                module: &floor_shader,
                entry_point: Some("vs_main"),
                buffers: &[],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &floor_shader,
                entry_point: Some("fs_main"),
                targets: &[Some(wgpu::ColorTargetState {
                    format: target_format,
                    blend: Some(wgpu::BlendState::REPLACE),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: depth_state.clone(),
            multisample: wgpu::MultisampleState::default(),
            multiview_mask: None,
            cache: None,
        });

        let scenery_shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("viz_scenery_shader"),
            source: wgpu::ShaderSource::Wgsl(SCENERY_SHADER.into()),
        });
        let scenery_vbuf_layout = wgpu::VertexBufferLayout {
            array_stride: std::mem::size_of::<SceneryVertex>() as u64,
            step_mode: wgpu::VertexStepMode::Vertex,
            attributes: &[
                wgpu::VertexAttribute {
                    offset: 0,
                    shader_location: 0,
                    format: wgpu::VertexFormat::Float32x3,
                },
                wgpu::VertexAttribute {
                    offset: 12,
                    shader_location: 1,
                    format: wgpu::VertexFormat::Float32x3,
                },
                wgpu::VertexAttribute {
                    offset: 24,
                    shader_location: 2,
                    format: wgpu::VertexFormat::Float32x3,
                },
            ],
        };
        let scenery_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("viz_scenery_pipeline"),
            layout: Some(&floor_layout),
            vertex: wgpu::VertexState {
                module: &scenery_shader,
                entry_point: Some("vs_main"),
                buffers: &[Some(scenery_vbuf_layout)],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &scenery_shader,
                entry_point: Some("fs_main"),
                targets: &[Some(wgpu::ColorTargetState {
                    format: target_format,
                    blend: Some(wgpu::BlendState::REPLACE),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            }),
            primitive: wgpu::PrimitiveState {
                cull_mode: None,
                ..Default::default()
            },
            depth_stencil: depth_state.clone(),
            multisample: wgpu::MultisampleState::default(),
            multiview_mask: None,
            cache: None,
        });

        let fixture_shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("viz_fixture_shader"),
            source: wgpu::ShaderSource::Wgsl(FIXTURE_SHADER.into()),
        });
        let fixture_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("viz_fixture_layout"),
            bind_group_layouts: &[Some(&fixture_bgl)],
            immediate_size: 0,
        });
        let vbuf_layout = wgpu::VertexBufferLayout {
            array_stride: std::mem::size_of::<FixtureVertex>() as u64,
            step_mode: wgpu::VertexStepMode::Vertex,
            attributes: &[
                wgpu::VertexAttribute {
                    offset: 0,
                    shader_location: 0,
                    format: wgpu::VertexFormat::Float32x3,
                },
                wgpu::VertexAttribute {
                    offset: 12,
                    shader_location: 1,
                    format: wgpu::VertexFormat::Float32x3,
                },
                wgpu::VertexAttribute {
                    offset: 24,
                    shader_location: 2,
                    format: wgpu::VertexFormat::Float32x3,
                },
                wgpu::VertexAttribute {
                    offset: 36,
                    shader_location: 3,
                    format: wgpu::VertexFormat::Float32,
                },
            ],
        };
        let fixture_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("viz_fixture_pipeline"),
            layout: Some(&fixture_layout),
            vertex: wgpu::VertexState {
                module: &fixture_shader,
                entry_point: Some("vs_main"),
                buffers: &[Some(vbuf_layout)],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &fixture_shader,
                entry_point: Some("fs_main"),
                targets: &[Some(wgpu::ColorTargetState {
                    format: target_format,
                    blend: Some(wgpu::BlendState::REPLACE),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: depth_state,
            multisample: wgpu::MultisampleState::default(),
            multiview_mask: None,
            cache: None,
        });

        let beam_bgl = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("viz_beam_bgl"),
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::VERTEX_FRAGMENT,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Texture {
                        sample_type: wgpu::TextureSampleType::Float { filterable: true },
                        view_dimension: wgpu::TextureViewDimension::D2Array,
                        multisampled: false,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 2,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                    count: None,
                },
            ],
        });
        let beam_bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("viz_beam_bg"),
            layout: &beam_bgl,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: uniform_buf.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::TextureView(&gobo_view),
                },
                wgpu::BindGroupEntry {
                    binding: 2,
                    resource: wgpu::BindingResource::Sampler(&gobo_sampler),
                },
            ],
        });
        let beam_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("viz_beam_layout"),
            bind_group_layouts: &[Some(&beam_bgl)],
            immediate_size: 0,
        });

        let beam_shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("viz_beam_shader"),
            source: wgpu::ShaderSource::Wgsl(BEAM_SHADER.into()),
        });
        let beam_vbuf_layout = wgpu::VertexBufferLayout {
            array_stride: std::mem::size_of::<BeamVertex>() as u64,
            step_mode: wgpu::VertexStepMode::Vertex,
            attributes: &[
                wgpu::VertexAttribute {
                    offset: 0,
                    shader_location: 0,
                    format: wgpu::VertexFormat::Float32x3,
                },
                wgpu::VertexAttribute {
                    offset: 12,
                    shader_location: 1,
                    format: wgpu::VertexFormat::Float32x3,
                },
                wgpu::VertexAttribute {
                    offset: 24,
                    shader_location: 2,
                    format: wgpu::VertexFormat::Float32x3,
                },
                wgpu::VertexAttribute {
                    offset: 36,
                    shader_location: 3,
                    format: wgpu::VertexFormat::Float32,
                },
                wgpu::VertexAttribute {
                    offset: 40,
                    shader_location: 4,
                    format: wgpu::VertexFormat::Float32x3,
                },
                wgpu::VertexAttribute {
                    offset: 52,
                    shader_location: 5,
                    format: wgpu::VertexFormat::Float32x3,
                },
            ],
        };
        let additive_blend = wgpu::BlendState {
            color: wgpu::BlendComponent {
                src_factor: wgpu::BlendFactor::One,
                dst_factor: wgpu::BlendFactor::One,
                operation: wgpu::BlendOperation::Add,
            },
            alpha: wgpu::BlendComponent {
                src_factor: wgpu::BlendFactor::One,
                dst_factor: wgpu::BlendFactor::One,
                operation: wgpu::BlendOperation::Add,
            },
        };
        let beam_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("viz_beam_pipeline"),
            layout: Some(&beam_layout),
            vertex: wgpu::VertexState {
                module: &beam_shader,
                entry_point: Some("vs_main"),
                buffers: &[Some(beam_vbuf_layout)],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &beam_shader,
                entry_point: Some("fs_main"),
                targets: &[Some(wgpu::ColorTargetState {
                    format: target_format,
                    blend: Some(additive_blend),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            }),
            primitive: wgpu::PrimitiveState {
                cull_mode: None,
                ..Default::default()
            },
            depth_stencil: Some(wgpu::DepthStencilState {
                format: wgpu::TextureFormat::Depth32Float,
                depth_write_enabled: Some(false),
                depth_compare: Some(wgpu::CompareFunction::Less),
                stencil: wgpu::StencilState::default(),
                bias: wgpu::DepthBiasState::default(),
            }),
            multisample: wgpu::MultisampleState::default(),
            multiview_mask: None,
            cache: None,
        });

        let blit_bgl = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("viz_blit_bgl"),
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Texture {
                        sample_type: wgpu::TextureSampleType::Float { filterable: true },
                        view_dimension: wgpu::TextureViewDimension::D2,
                        multisampled: false,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                    count: None,
                },
            ],
        });
        let blit_sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("viz_blit_sampler"),
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            ..Default::default()
        });
        let blit_shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("viz_blit_shader"),
            source: wgpu::ShaderSource::Wgsl(BLIT_SHADER.into()),
        });
        let blit_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("viz_blit_layout"),
            bind_group_layouts: &[Some(&blit_bgl)],
            immediate_size: 0,
        });
        let blit_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("viz_blit_pipeline"),
            layout: Some(&blit_layout),
            vertex: wgpu::VertexState {
                module: &blit_shader,
                entry_point: Some("vs_main"),
                buffers: &[],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &blit_shader,
                entry_point: Some("fs_main"),
                targets: &[Some(wgpu::ColorTargetState {
                    format: target_format,
                    blend: Some(wgpu::BlendState::REPLACE),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: None,
            multisample: wgpu::MultisampleState::default(),
            multiview_mask: None,
            cache: None,
        });

        Self {
            floor_pipeline,
            scenery_pipeline,
            fixture_pipeline,
            beam_pipeline,
            blit_pipeline,
            blit_bgl,
            blit_sampler,
            blit_bind_group: None,
            uniform_buf,
            lights_buf,
            floor_bind_group,
            fixture_bind_group,
            beam_bind_group,
            gobo_tex,
            gobo_layers: HashMap::new(),
            next_gobo_layer: 0,
            scenery_vbuf: None,
            scenery_vcount: 0,
            last_scenery_key: (0, 0),
            fixture_vbuf: None,
            fixture_vcount: 0,
            beam_vbuf: None,
            beam_vcount: 0,
            color_view: None,
            depth_view: None,
            rt_size: [0, 0],
            target_format,
        }
    }

    fn ensure_builtin_gobos(&mut self, queue: &wgpu::Queue) {
        if self.next_gobo_layer >= BUILTIN_COUNT {
            return;
        }
        for idx in 0..BUILTIN_COUNT {
            let data = generate_builtin_layer(idx);
            self.upload_gobo_layer(queue, idx, &data);
        }
        self.next_gobo_layer = BUILTIN_COUNT;
    }

    fn upload_gobo_layer(&self, queue: &wgpu::Queue, layer: u32, data: &[u8]) {
        for (mip, (size, mip_data)) in generate_mipmaps(data).into_iter().enumerate() {
            queue.write_texture(
                wgpu::TexelCopyTextureInfo {
                    texture: &self.gobo_tex,
                    mip_level: mip as u32,
                    origin: wgpu::Origin3d {
                        x: 0,
                        y: 0,
                        z: layer,
                    },
                    aspect: wgpu::TextureAspect::All,
                },
                &mip_data,
                wgpu::TexelCopyBufferLayout {
                    offset: 0,
                    bytes_per_row: Some(size),
                    rows_per_image: Some(size),
                },
                wgpu::Extent3d {
                    width: size,
                    height: size,
                    depth_or_array_layers: 1,
                },
            );
        }
    }

    fn sync_custom_gobos(&mut self, queue: &wgpu::Queue, images: &HashMap<String, Vec<u8>>) {
        for (gid, bytes) in images {
            if self.gobo_layers.contains_key(gid) || self.next_gobo_layer >= MAX_GOBO_LAYERS {
                continue;
            }
            if let Some(mask) = decode_png_to_gobo_layer(bytes) {
                let layer = self.next_gobo_layer;
                self.next_gobo_layer += 1;
                self.upload_gobo_layer(queue, layer, &mask);
                self.gobo_layers.insert(gid.clone(), layer);
            }
        }
    }

    fn resolve_gobo_layer(&self, g: &GoboWheelState) -> u32 {
        if let Some(&layer) = self.gobo_layers.get(&g.gobo_id) {
            return layer;
        }
        if g.gobo_id.is_empty() {
            0
        } else {
            resolve_builtin_index(&g.gobo_id, g.slot_index)
        }
    }

    fn ensure_targets(&mut self, device: &wgpu::Device, width: u32, height: u32) {
        let w = width.max(1);
        let h = height.max(1);
        if self.rt_size == [w, h] && self.color_view.is_some() && self.depth_view.is_some() {
            return;
        }
        let color_tex = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("viz_color_rt"),
            size: wgpu::Extent3d {
                width: w,
                height: h,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: self.target_format,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::TEXTURE_BINDING,
            view_formats: &[],
        });
        let color_view = color_tex.create_view(&wgpu::TextureViewDescriptor::default());

        let depth_tex = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("viz_depth_rt"),
            size: wgpu::Extent3d {
                width: w,
                height: h,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Depth32Float,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            view_formats: &[],
        });
        let depth_view = depth_tex.create_view(&wgpu::TextureViewDescriptor::default());

        let blit_bg = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("viz_blit_bg"),
            layout: &self.blit_bgl,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: wgpu::BindingResource::TextureView(&color_view),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::Sampler(&self.blit_sampler),
                },
            ],
        });

        self.color_view = Some(color_view);
        self.depth_view = Some(depth_view);
        self.blit_bind_group = Some(blit_bg);
        self.rt_size = [w, h];
    }
}

struct StageCallback {
    scene: RenderScene,
}

impl egui_wgpu::CallbackTrait for StageCallback {
    fn prepare(
        &self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        screen_descriptor: &egui_wgpu::ScreenDescriptor,
        encoder: &mut wgpu::CommandEncoder,
        callback_resources: &mut egui_wgpu::CallbackResources,
    ) -> Vec<wgpu::CommandBuffer> {
        let target_format = callback_resources
            .get::<wgpu::TextureFormat>()
            .copied()
            .unwrap_or(wgpu::TextureFormat::Bgra8Unorm);
        let res = callback_resources
            .entry::<GpuResources>()
            .or_insert_with(|| GpuResources::new(device, target_format));

        res.ensure_targets(
            device,
            screen_descriptor.size_in_pixels[0],
            screen_descriptor.size_in_pixels[1],
        );
        res.ensure_builtin_gobos(queue);
        res.sync_custom_gobos(queue, &self.scene.gobo_images);

        let vp = self.scene.camera.view_proj(self.scene.aspect);

        let mut lights = Vec::with_capacity(MAX_LIGHTS);
        for f in self.scene.fixtures.iter().take(MAX_LIGHTS) {
            if f.intensity <= 0.005 {
                continue;
            }
            let dir = normalize3(f.direction);
            let up_ref = if dir[2].abs() > 0.98 {
                [0.0, 1.0, 0.0]
            } else {
                [0.0, 0.0, 1.0]
            };
            let right = normalize3(cross3(up_ref, [-dir[0], -dir[1], -dir[2]]));
            let gobo_layer1 = res.resolve_gobo_layer(&f.gobos[0]) as f32;
            let outer = (f.beam_angle_deg * 0.5).to_radians().cos();
            let inner = (f.beam_angle_deg * 0.32).to_radians().cos();
            let (rs1, rc1) = f.gobos[0].rot_rad.sin_cos();
            let gobo_layer2 = res.resolve_gobo_layer(&f.gobos[1]) as f32;
            let (rs2, rc2) = f.gobos[1].rot_rad.sin_cos();
            lights.push(SpotLightGpu {
                pos_intensity: [f.position[0], f.position[1], f.position[2], f.intensity],
                dir_cos_outer: [dir[0], dir[1], dir[2], outer],
                color_cos_inner: [f.color[0], f.color[1], f.color[2], inner],
                right_gobo: [right[0], right[1], right[2], gobo_layer1],
                rot_blur: [rc1, rs1, f.gobo_blur_lod, 0.0],
                gobo2_rot_layer: [rc2, rs2, gobo_layer2, 0.0],
            });
        }
        let light_count = lights.len() as f32;
        if !lights.is_empty() {
            queue.write_buffer(&res.lights_buf, 0, bytemuck::cast_slice(&lights));
        }

        let sc = parse_hex_color(&self.scene.stage.color);
        let eye = self.scene.camera.eye();
        let uni = SceneUniform {
            view_proj: vp,
            stage_size_grid: [
                self.scene.stage.width,
                self.scene.stage.depth,
                self.scene.stage.grid_spacing,
                self.scene.stage.fog_density,
            ],
            stage_color_count: [sc[0], sc[1], sc[2], light_count],
            cam_eye: [eye[0], eye[1], eye[2], 0.0],
        };
        queue.write_buffer(&res.uniform_buf, 0, bytemuck::bytes_of(&uni));

        let scenery_key = (
            Arc::as_ptr(&self.scene.scenery) as usize,
            self.scene.scenery.len(),
        );
        if scenery_key != res.last_scenery_key {
            res.last_scenery_key = scenery_key;
            let mut s_verts = Vec::new();
            for mesh in self.scene.scenery.iter() {
                for tri in mesh.indices.chunks_exact(3) {
                    for &idx in tri {
                        let i = idx as usize;
                        if let Some(&pos) = mesh.vertices.get(i) {
                            let normal = mesh.normals.get(i).copied().unwrap_or([0.0, 0.0, 1.0]);
                            s_verts.push(SceneryVertex {
                                pos,
                                normal,
                                color: mesh.color,
                            });
                        }
                    }
                }
            }
            res.scenery_vcount = s_verts.len() as u32;
            if !s_verts.is_empty() {
                let bytes = bytemuck::cast_slice(&s_verts);
                let need_realloc = res
                    .scenery_vbuf
                    .as_ref()
                    .is_none_or(|b| b.size() < bytes.len() as u64);
                if need_realloc {
                    res.scenery_vbuf = Some(device.create_buffer(&wgpu::BufferDescriptor {
                        label: Some("viz_scenery_vbuf"),
                        size: (bytes.len().max(1024) * 2) as u64,
                        usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
                        mapped_at_creation: false,
                    }));
                }
                if let Some(buf) = &res.scenery_vbuf {
                    queue.write_buffer(buf, 0, bytes);
                }
            }
        }

        let verts = build_fixtures_mesh(&self.scene.fixtures, self.scene.selected_channel);
        res.fixture_vcount = verts.len() as u32;
        if !verts.is_empty() {
            let bytes = bytemuck::cast_slice(&verts);
            let need_realloc = res
                .fixture_vbuf
                .as_ref()
                .is_none_or(|b| b.size() < bytes.len() as u64);
            if need_realloc {
                res.fixture_vbuf = Some(device.create_buffer(&wgpu::BufferDescriptor {
                    label: Some("viz_fixture_vbuf"),
                    size: (bytes.len().max(1024) * 2) as u64,
                    usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
                    mapped_at_creation: false,
                }));
            }
            if let Some(buf) = &res.fixture_vbuf {
                queue.write_buffer(buf, 0, bytes);
            }
        }

        let beam_verts = build_beams_mesh(
            &self.scene.fixtures,
            self.scene.stage.fog_density,
            |g| res.resolve_gobo_layer(g),
        );
        res.beam_vcount = beam_verts.len() as u32;
        if !beam_verts.is_empty() {
            let bytes = bytemuck::cast_slice(&beam_verts);
            let need_realloc = res
                .beam_vbuf
                .as_ref()
                .is_none_or(|b| b.size() < bytes.len() as u64);
            if need_realloc {
                res.beam_vbuf = Some(device.create_buffer(&wgpu::BufferDescriptor {
                    label: Some("viz_beam_vbuf"),
                    size: (bytes.len().max(1024) * 2) as u64,
                    usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
                    mapped_at_creation: false,
                }));
            }
            if let Some(buf) = &res.beam_vbuf {
                queue.write_buffer(buf, 0, bytes);
            }
        }

        if let (Some(color_view), Some(depth_view)) = (&res.color_view, &res.depth_view) {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("viz_3d_offscreen_pass"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: color_view,
                    depth_slice: None,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color {
                            r: 0.025,
                            g: 0.027,
                            b: 0.035,
                            a: 1.0,
                        }),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: Some(wgpu::RenderPassDepthStencilAttachment {
                    view: depth_view,
                    depth_ops: Some(wgpu::Operations {
                        load: wgpu::LoadOp::Clear(1.0),
                        store: wgpu::StoreOp::Store,
                    }),
                    stencil_ops: None,
                }),
                timestamp_writes: None,
                occlusion_query_set: None,
                multiview_mask: None,
            });

            pass.set_pipeline(&res.floor_pipeline);
            pass.set_bind_group(0, &res.floor_bind_group, &[]);
            pass.draw(0..6, 0..1);

            if self.scene.show_scenery && res.scenery_vcount > 0 {
                if let Some(vbuf) = &res.scenery_vbuf {
                    pass.set_pipeline(&res.scenery_pipeline);
                    pass.set_bind_group(0, &res.floor_bind_group, &[]);
                    pass.set_vertex_buffer(0, vbuf.slice(..));
                    pass.draw(0..res.scenery_vcount, 0..1);
                }
            }

            if res.fixture_vcount > 0 {
                if let Some(vbuf) = &res.fixture_vbuf {
                    pass.set_pipeline(&res.fixture_pipeline);
                    pass.set_bind_group(0, &res.fixture_bind_group, &[]);
                    pass.set_vertex_buffer(0, vbuf.slice(..));
                    pass.draw(0..res.fixture_vcount, 0..1);
                }
            }

            if res.beam_vcount > 0 {
                if let Some(vbuf) = &res.beam_vbuf {
                    pass.set_pipeline(&res.beam_pipeline);
                    pass.set_bind_group(0, &res.beam_bind_group, &[]);
                    pass.set_vertex_buffer(0, vbuf.slice(..));
                    pass.draw(0..res.beam_vcount, 0..1);
                }
            }
        }

        Vec::new()
    }

    fn paint(
        &self,
        _info: egui::PaintCallbackInfo,
        render_pass: &mut wgpu::RenderPass<'static>,
        callback_resources: &egui_wgpu::CallbackResources,
    ) {
        let Some(res) = callback_resources.get::<GpuResources>() else {
            return;
        };
        let Some(bg) = &res.blit_bind_group else {
            return;
        };
        render_pass.set_pipeline(&res.blit_pipeline);
        render_pass.set_bind_group(0, bg, &[]);
        render_pass.draw(0..6, 0..1);
    }
}

/// Enregistre le format de swapchain d'eframe dans les ressources wgpu du callback.
pub fn init_wgpu(render_state: &egui_wgpu::RenderState) {
    render_state
        .renderer
        .write()
        .callback_resources
        .insert(render_state.target_format);
}

/// Build the `egui::PaintCallback` to display the 3D scene in `rect`.
pub fn paint_callback(rect: egui::Rect, scene: RenderScene) -> egui::PaintCallback {
    egui_wgpu::Callback::new_paint_callback(rect, StageCallback { scene })
}
