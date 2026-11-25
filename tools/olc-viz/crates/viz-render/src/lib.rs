//! Rendu 3D (wgpu) : sol éclairé analytiquement, projecteurs procéduraux et caméra orbitale.

pub mod camera;
pub mod dmx_eval;
pub mod math;
pub mod mesh;

use std::sync::Arc;

use bytemuck::{Pod, Zeroable};
use viz_core::Stage;

use crate::camera::OrbitCamera;
use crate::dmx_eval::ResolvedFixture;
use crate::math::{normalize3, parse_hex_color};
use crate::mesh::{build_beams_mesh, build_fixtures_mesh, BeamVertex, FixtureVertex};

pub const MAX_LIGHTS: usize = 64;

/// Données transmises au callback `wgpu` pour dessiner une frame.
#[derive(Clone)]
pub struct RenderScene {
    pub camera: OrbitCamera,
    pub stage: Stage,
    pub fixtures: Arc<Vec<ResolvedFixture>>,
    pub selected_channel: Option<u32>,
    pub aspect: f32,
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
    pos_intensity: [f32; 4], // x, y, z, intensity
    dir_cos_outer: [f32; 4], // dx, dy, dz, cos(outer_half)
    color_cos_inner: [f32; 4], // r, g, b, cos(inner_half)
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
};

@group(0) @binding(0) var<uniform> u_scene: SceneUniform;
@group(0) @binding(1) var<storage, read> u_lights: array<SpotLight>;

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
            let contrib = l.color_cos_inner.rgb * l.pos_intensity.w * cone * ndotl * atten * 2.8;
            accum = accum + contrib * (base * 1.4 + vec3<f32>(0.12));
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

struct VsIn {
    @location(0) pos: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) color: vec3<f32>,
    @location(3) alpha: f32,
};

struct VsOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) world_pos: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) color: vec3<f32>,
    @location(3) alpha: f32,
};

@vertex
fn vs_main(in: VsIn) -> VsOut {
    var out: VsOut;
    out.clip = u_scene.view_proj * vec4<f32>(in.pos, 1.0);
    out.world_pos = in.pos;
    out.normal = in.normal;
    out.color = in.color;
    out.alpha = in.alpha;
    return out;
}

@fragment
fn fs_main(in: VsOut) -> @location(0) vec4<f32> {
    let view_dir = normalize(u_scene.cam_eye.xyz - in.world_pos);
    let ndotv = abs(dot(normalize(in.normal), view_dir));
    let edge = pow(ndotv, 1.6);
    let rgb = in.color * in.alpha * edge * 0.52;
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
            layout: Some(&fixture_layout),
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

        let vp = self.scene.camera.view_proj(self.scene.aspect);

        let mut lights = Vec::with_capacity(MAX_LIGHTS);
        for f in self.scene.fixtures.iter().take(MAX_LIGHTS) {
            if f.intensity <= 0.005 {
                continue;
            }
            let dir = normalize3(f.direction);
            let outer = (f.beam_angle_deg * 0.5).to_radians().cos();
            let inner = (f.beam_angle_deg * 0.32).to_radians().cos();
            lights.push(SpotLightGpu {
                pos_intensity: [f.position[0], f.position[1], f.position[2], f.intensity],
                dir_cos_outer: [dir[0], dir[1], dir[2], outer],
                color_cos_inner: [f.color[0], f.color[1], f.color[2], inner],
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

        let beam_verts = build_beams_mesh(&self.scene.fixtures, self.scene.stage.fog_density);
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
                    pass.set_bind_group(0, &res.fixture_bind_group, &[]);
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

/// Construit le `egui::PaintCallback` pour afficher la scène 3D dans `rect`.
pub fn paint_callback(rect: egui::Rect, scene: RenderScene) -> egui::PaintCallback {
    egui_wgpu::Callback::new_paint_callback(rect, StageCallback { scene })
}
