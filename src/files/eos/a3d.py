# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2026 Mika Cousin <mika.cousin@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
"""Augment3d (``working.a3d``) 3D patch transform and scenery/GLB extractor."""

from __future__ import annotations

import io
import json
import math
import struct
import zipfile
from typing import Any

_Vec3 = tuple[float, float, float]
_Mat4 = list[float]  # 16 floats column-major

_GLB_MAGIC = b"glTF"
_GLB_CHUNK_JSON = 0x4E4F534A
_GLB_CHUNK_BIN = 0x004E4942

_COMP_STRUCT: dict[int, tuple[str, int]] = {
    5120: ("b", 1),
    5121: ("B", 1),
    5122: ("h", 2),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}
_TYPE_COUNT: dict[str, int] = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
}


def eos_euler_to_olc(rx: float, ry: float, rz: float) -> _Vec3:
    """Convert Eos Augment3d XYZ Euler degrees to OLC ``(rz, ry, rx)``."""
    return (float(rz), float(ry), float(rx))


def _mat4_identity() -> _Mat4:
    return [
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
    ]


def _mat4_mul(a: _Mat4, b: _Mat4) -> _Mat4:
    out = [0.0] * 16
    for col in range(4):
        for row in range(4):
            out[col * 4 + row] = sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
    return out


def _mat4_from_trs(t: _Vec3, q: tuple[float, float, float, float], s: _Vec3) -> _Mat4:
    """Build column-major 4x4 matrix from translation, quat (x,y,z,w), scale."""
    qx, qy, qz, qw = q
    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    wx, wy, wz = qw * qx, qw * qy, qw * qz

    sx, sy, sz = s
    return [
        (1.0 - 2.0 * (yy + zz)) * sx,
        2.0 * (xy + wz) * sx,
        2.0 * (xz - wy) * sx,
        0.0,
        2.0 * (xy - wz) * sy,
        (1.0 - 2.0 * (xx + zz)) * sy,
        2.0 * (yz + wx) * sy,
        0.0,
        2.0 * (xz + wy) * sz,
        2.0 * (yz - wx) * sz,
        (1.0 - 2.0 * (xx + yy)) * sz,
        0.0,
        t[0],
        t[1],
        t[2],
        1.0,
    ]


def _xform_point(m: _Mat4, p: _Vec3) -> _Vec3:
    x, y, z = p
    return (
        m[0] * x + m[4] * y + m[8] * z + m[12],
        m[1] * x + m[5] * y + m[9] * z + m[13],
        m[2] * x + m[6] * y + m[10] * z + m[14],
    )


def _xform_normal(m: _Mat4, n: _Vec3) -> _Vec3:
    x, y, z = n
    nx = m[0] * x + m[4] * y + m[8] * z
    ny = m[1] * x + m[5] * y + m[9] * z
    nz = m[2] * x + m[6] * y + m[10] * z
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 1e-8:
        return (0.0, 0.0, 1.0)
    return (nx / length, ny / length, nz / length)


def _read_accessor(
    gltf: dict[str, Any], bin_data: bytes, acc_idx: int
) -> list[tuple[float, ...]]:
    accessors = gltf.get("accessors", [])
    buffer_views = gltf.get("bufferViews", [])
    if not (0 <= acc_idx < len(accessors)):
        return []
    acc = accessors[acc_idx]
    bv_idx = acc.get("bufferView")
    if bv_idx is None or not (0 <= bv_idx < len(buffer_views)):
        return []
    bv = buffer_views[bv_idx]
    comp_type = int(acc.get("componentType", 0))
    acc_type = str(acc.get("type", "SCALAR"))
    count = int(acc.get("count", 0))
    if comp_type not in _COMP_STRUCT or acc_type not in _TYPE_COUNT or count <= 0:
        return []

    fmt_char, comp_size = _COMP_STRUCT[comp_type]
    n_comp = _TYPE_COUNT[acc_type]
    elem_size = comp_size * n_comp
    stride = int(bv.get("byteStride") or elem_size)
    base = int(bv.get("byteOffset", 0)) + int(acc.get("byteOffset", 0))
    fmt = f"<{n_comp}{fmt_char}"

    out: list[tuple[float, ...]] = []
    for i in range(count):
        off = base + i * stride
        if off + elem_size > len(bin_data):
            break
        out.append(tuple(float(v) for v in struct.unpack_from(fmt, bin_data, off)))
    return out


def _compute_flat_normals(verts: list[_Vec3], indices: list[int]) -> list[_Vec3]:
    normals: list[list[float]] = [[0.0, 0.0, 0.0] for _ in verts]
    for i in range(0, len(indices) - 2, 3):
        ia, ib, ic = indices[i], indices[i + 1], indices[i + 2]
        if ia >= len(verts) or ib >= len(verts) or ic >= len(verts):
            continue
        ax, ay, az = verts[ia]
        bx, by, bz = verts[ib]
        cx, cy, cz = verts[ic]
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        for idx in (ia, ib, ic):
            normals[idx][0] += nx
            normals[idx][1] += ny
            normals[idx][2] += nz

    out: list[_Vec3] = []
    for nx, ny, nz in normals:
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length <= 1e-8:
            out.append((0.0, 0.0, 1.0))
        else:
            out.append((nx / length, ny / length, nz / length))
    return out


def _collect_mesh_node_transforms(gltf: dict[str, Any]) -> dict[int, list[_Mat4]]:
    nodes = gltf.get("nodes", [])
    if not isinstance(nodes, list) or not nodes:
        return {}

    has_parent: set[int] = set()
    for node in nodes:
        if isinstance(node, dict):
            for ch in node.get("children", []):
                if isinstance(ch, int):
                    has_parent.add(ch)

    def _node_local(node: dict[str, Any]) -> _Mat4:
        mat = node.get("matrix")
        if isinstance(mat, list) and len(mat) == 16:
            return [float(v) for v in mat]
        tr = node.get("translation", [0.0, 0.0, 0.0])
        rot = node.get("rotation", [0.0, 0.0, 0.0, 1.0])
        sc = node.get("scale", [1.0, 1.0, 1.0])
        return _mat4_from_trs(
            (float(tr[0]), float(tr[1]), float(tr[2])),
            (float(rot[0]), float(rot[1]), float(rot[2]), float(rot[3])),
            (float(sc[0]), float(sc[1]), float(sc[2])),
        )

    mesh_mats: dict[int, list[_Mat4]] = {}

    def _walk(idx: int, parent_m: _Mat4) -> None:
        if not (0 <= idx < len(nodes)) or not isinstance(nodes[idx], dict):
            return
        node = nodes[idx]
        world_m = _mat4_mul(parent_m, _node_local(node))
        mesh_idx = node.get("mesh")
        if isinstance(mesh_idx, int):
            mesh_mats.setdefault(mesh_idx, []).append(world_m)
        for ch in node.get("children", []):
            if isinstance(ch, int):
                _walk(ch, world_m)

    roots = [i for i in range(len(nodes)) if i not in has_parent]
    for r in roots or list(range(len(nodes))):
        _walk(r, _mat4_identity())
    return mesh_mats


def _decode_glb_mesh_data(
    glb_bytes: bytes,
) -> tuple[
    list[_Vec3],
    list[_Vec3],
    list[int],
    list[tuple[float, float]],
    dict[str, Any] | None,
]:
    """Decode a glTF 2.0 binary into ``(vertices, normals, indices, uvs, pbr)``."""
    if len(glb_bytes) < 12 or glb_bytes[:4] != _GLB_MAGIC:
        return [], [], [], [], None
    _magic, version, total_len = struct.unpack_from("<4sII", glb_bytes, 0)
    if version != 2 or total_len > len(glb_bytes):
        return [], [], [], [], None

    offset = 12
    gltf: dict[str, Any] | None = None
    bin_data = b""
    while offset + 8 <= total_len:
        chunk_len, chunk_type = struct.unpack_from("<II", glb_bytes, offset)
        offset += 8
        chunk_bytes = glb_bytes[offset : offset + chunk_len]
        offset += chunk_len
        if chunk_type == _GLB_CHUNK_JSON and gltf is None:
            try:
                loaded = json.loads(chunk_bytes.decode("utf-8"))
                if isinstance(loaded, dict):
                    gltf = loaded
            except (UnicodeDecodeError, json.JSONDecodeError):
                return [], [], [], [], None
        elif chunk_type == _GLB_CHUNK_BIN and not bin_data:
            bin_data = chunk_bytes

    if gltf is None:
        return [], [], [], [], None

    meshes = gltf.get("meshes", [])
    if not isinstance(meshes, list) or not meshes:
        return [], [], [], [], None

    gltf_mats = gltf.get("materials", [])
    mesh_mats = _collect_mesh_node_transforms(gltf)
    all_verts: list[_Vec3] = []
    all_norms: list[_Vec3] = []
    all_indices: list[int] = []
    all_uvs: list[tuple[float, float]] = []
    fallback_pbr: dict[str, Any] | None = None

    for m_idx, mesh in enumerate(meshes):
        if not isinstance(mesh, dict):
            continue
        mats = mesh_mats.get(m_idx) or [_mat4_identity()]
        for prim in mesh.get("primitives", []):
            if not isinstance(prim, dict):
                continue
            if int(prim.get("mode", 4)) != 4:
                continue
            attrs = prim.get("attributes", {})
            if not isinstance(attrs, dict) or "POSITION" not in attrs:
                continue
            pos_raw = _read_accessor(gltf, bin_data, int(attrs["POSITION"]))
            if not pos_raw:
                continue
            pos_list: list[_Vec3] = [(p[0], p[1], p[2]) for p in pos_raw]

            if "NORMAL" in attrs:
                norm_raw = _read_accessor(gltf, bin_data, int(attrs["NORMAL"]))
                norm_list: list[_Vec3] = [(n[0], n[1], n[2]) for n in norm_raw]
            else:
                norm_list = []

            uv_list: list[tuple[float, float]] = []
            if "TEXCOORD_0" in attrs:
                uv_raw = _read_accessor(gltf, bin_data, int(attrs["TEXCOORD_0"]))
                if len(uv_raw) == len(pos_list):
                    uv_list = [(round(u[0], 4), round(u[1], 4)) for u in uv_raw]

            if (
                fallback_pbr is None
                and "material" in prim
                and isinstance(gltf_mats, list)
            ):
                mat_idx = int(prim["material"])
                if 0 <= mat_idx < len(gltf_mats) and isinstance(
                    gltf_mats[mat_idx], dict
                ):
                    gm = gltf_mats[mat_idx]
                    pbr = gm.get("pbrMetallicRoughness", {})
                    if isinstance(pbr, dict):
                        bcf = pbr.get("baseColorFactor", [0.8, 0.8, 0.8, 1.0])
                        ef = gm.get("emissiveFactor", [0.0, 0.0, 0.0])
                        op = float(bcf[3]) if len(bcf) > 3 else 1.0
                        met_f = float(pbr.get("metallicFactor", 0.0))
                        rgh_f = float(pbr.get("roughnessFactor", 0.5))
                        fallback_pbr = {
                            "base_color": [
                                round(max(0.0, min(1.0, float(bcf[c]))), 4)
                                for c in range(3)
                            ],
                            "metallic": round(max(0.0, min(1.0, met_f)), 4),
                            "roughness": round(max(0.0, min(1.0, rgh_f)), 4),
                            "emissive": [
                                round(max(0.0, min(1.0, float(ef[c]))), 4)
                                for c in range(3)
                            ],
                            "opacity": round(max(0.0, min(1.0, op)), 4),
                            "transparent": gm.get("alphaMode") == "BLEND" or op < 0.999,
                        }

            if "indices" in prim and prim["indices"] is not None:
                idx_raw = _read_accessor(gltf, bin_data, int(prim["indices"]))
                prim_indices = [int(v[0]) for v in idx_raw]
            else:
                prim_indices = list(range(len(pos_list)))

            if len(norm_list) != len(pos_list):
                norm_list = _compute_flat_normals(pos_list, prim_indices)

            for mat in mats:
                base_v = len(all_verts)
                for p in pos_list:
                    vx, vy, vz = _xform_point(mat, p)
                    # Convert glTF 2.0 (Y-up) -> Augment3d/OLC (Z-up)
                    all_verts.append((vx, -vz, vy))
                for n in norm_list:
                    nx, ny, nz = _xform_normal(mat, n)
                    all_norms.append((nx, -nz, ny))
                if uv_list:
                    all_uvs.extend(uv_list)
                all_indices.extend(base_v + idx for idx in prim_indices)

    if len(all_uvs) != len(all_verts):
        all_uvs = []
    return all_verts, all_norms, all_indices, all_uvs, fallback_pbr


def _decode_glb_mesh(
    glb_bytes: bytes,
) -> tuple[list[_Vec3], list[_Vec3], list[int]]:
    """Decode a glTF 2.0 binary (``.glb``) into ``(vertices, normals, indices)``."""
    verts, norms, indices, _uvs, _pbr = _decode_glb_mesh_data(glb_bytes)
    return verts, norms, indices


def _box_mesh(center: _Vec3, size: _Vec3) -> tuple[list[_Vec3], list[_Vec3], list[int]]:
    """Build a 12-triangle axis-aligned box mesh from local center & size."""
    cx, cy, cz = center
    hx, hy, hz = abs(size[0]) * 0.5, abs(size[1]) * 0.5, abs(size[2]) * 0.5
    if hx <= 1e-5 and hy <= 1e-5 and hz <= 1e-5:
        return [], [], []
    hx = max(hx, 1e-3)
    hy = max(hy, 1e-3)
    hz = max(hz, 1e-3)

    faces: list[tuple[list[_Vec3], _Vec3]] = [
        (
            [
                (cx - hx, cy - hy, cz + hz),
                (cx + hx, cy - hy, cz + hz),
                (cx + hx, cy + hy, cz + hz),
                (cx - hx, cy + hy, cz + hz),
            ],
            (0.0, 0.0, 1.0),
        ),
        (
            [
                (cx - hx, cy + hy, cz - hz),
                (cx + hx, cy + hy, cz - hz),
                (cx + hx, cy - hy, cz - hz),
                (cx - hx, cy - hy, cz - hz),
            ],
            (0.0, 0.0, -1.0),
        ),
        (
            [
                (cx + hx, cy - hy, cz - hz),
                (cx + hx, cy + hy, cz - hz),
                (cx + hx, cy + hy, cz + hz),
                (cx + hx, cy - hy, cz + hz),
            ],
            (1.0, 0.0, 0.0),
        ),
        (
            [
                (cx - hx, cy + hy, cz - hz),
                (cx - hx, cy - hy, cz - hz),
                (cx - hx, cy - hy, cz + hz),
                (cx - hx, cy + hy, cz + hz),
            ],
            (-1.0, 0.0, 0.0),
        ),
        (
            [
                (cx + hx, cy + hy, cz - hz),
                (cx - hx, cy + hy, cz - hz),
                (cx - hx, cy + hy, cz + hz),
                (cx + hx, cy + hy, cz + hz),
            ],
            (0.0, 1.0, 0.0),
        ),
        (
            [
                (cx - hx, cy - hy, cz - hz),
                (cx + hx, cy - hy, cz - hz),
                (cx + hx, cy - hy, cz + hz),
                (cx - hx, cy - hy, cz + hz),
            ],
            (0.0, -1.0, 0.0),
        ),
    ]
    verts: list[_Vec3] = []
    norms: list[_Vec3] = []
    indices: list[int] = []
    for quad, n in faces:
        b = len(verts)
        verts.extend(quad)
        norms.extend([n, n, n, n])
        indices.extend([b, b + 1, b + 2, b, b + 2, b + 3])
    return verts, norms, indices


def _parse_argb_hex(hex_str: str) -> list[float] | None:
    clean = str(hex_str or "").strip().lstrip("#")
    if len(clean) == 8:
        clean = clean[2:]
    if len(clean) != 6:
        return None
    try:
        r = int(clean[0:2], 16) / 255.0
        g = int(clean[2:4], 16) / 255.0
        b = int(clean[4:6], 16) / 255.0
        return [round(r, 4), round(g, 4), round(b, 4)]
    except ValueError:
        return None


def _transform_world(
    world: dict[str, Any],
    verts: list[_Vec3],
    norms: list[_Vec3],
) -> tuple[list[list[float]], list[list[float]]]:
    pos = world.get("pos", {})
    quat = world.get("quat", {})
    sc = world.get("scale", {})
    mat = _mat4_from_trs(
        (float(pos.get("x", 0.0)), float(pos.get("y", 0.0)), float(pos.get("z", 0.0))),
        (
            float(quat.get("x", 0.0)),
            float(quat.get("y", 0.0)),
            float(quat.get("z", 0.0)),
            float(quat.get("w", 1.0)),
        ),
        (float(sc.get("x", 1.0)), float(sc.get("y", 1.0)), float(sc.get("z", 1.0))),
    )
    out_v = [[round(c, 4) for c in _xform_point(mat, v)] for v in verts]
    out_n = [[round(c, 4) for c in _xform_normal(mat, n)] for n in norms]
    return out_v, out_n


def _rgb_to_hex(rgb: list[float]) -> str:
    r = max(0, min(255, round(float(rgb[0]) * 255.0)))
    g = max(0, min(255, round(float(rgb[1]) * 255.0)))
    b = max(0, min(255, round(float(rgb[2]) * 255.0)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _is_horizontal_ground(
    name: str, world: dict[str, Any], lb_size: dict[str, Any]
) -> bool:
    if name.lower() != "ground":
        return False
    pos_z = float(world.get("pos", {}).get("z", 0.0))
    sc_z = float(world.get("scale", {}).get("z", 1.0))
    sz_z = float(lb_size.get("z", 0.0)) if isinstance(lb_size, dict) else 0.0
    if abs(pos_z) >= 0.05 or sz_z * sc_z >= 0.01:
        return False
    quat = world.get("quat")
    if isinstance(quat, dict) and ("x" in quat or "y" in quat):
        return (
            abs(float(quat.get("x", 0.0))) < 0.05
            and abs(float(quat.get("y", 0.0))) < 0.05
        )
    eulers = world.get("eulers")
    if isinstance(eulers, dict):
        return (
            abs(float(eulers.get("x", 0.0))) < 1.0
            and abs(float(eulers.get("y", 0.0))) < 1.0
        )
    return True


def _extract_pbr_from_obj(
    obj: dict[str, Any], names: set[str]
) -> dict[str, Any] | None:
    bc = obj.get("base_color")
    base_color: list[float] | None = None
    if isinstance(bc, dict) and all(k in bc for k in ("x", "y", "z")):
        base_color = [
            round(max(0.0, min(1.0, float(bc["x"]))), 4),
            round(max(0.0, min(1.0, float(bc["y"]))), 4),
            round(max(0.0, min(1.0, float(bc["z"]))), 4),
        ]
    elif "color" in obj:
        base_color = _parse_argb_hex(str(obj.get("color", "")))

    has_pbr = any(
        k in obj
        for k in ("base_color", "metallic", "smoothness", "emissive", "opacity")
    )
    if not has_pbr or base_color is None:
        return None

    metallic = round(max(0.0, min(1.0, float(obj.get("metallic", 0.0)))), 4)
    smoothness = max(0.0, min(1.0, float(obj.get("smoothness", 0.5))))
    roughness = round(1.0 - smoothness, 4)

    em = obj.get("emissive")
    if isinstance(em, dict) and all(k in em for k in ("x", "y", "z")):
        emissive = [
            round(max(0.0, min(1.0, float(em["x"]))), 4),
            round(max(0.0, min(1.0, float(em["y"]))), 4),
            round(max(0.0, min(1.0, float(em["z"]))), 4),
        ]
    else:
        emissive = [0.0, 0.0, 0.0]

    raw_opacity = float(obj.get("opacity", 1.0))
    opacity = 1.0 if raw_opacity < 0.0 else round(max(0.0, min(1.0, raw_opacity)), 4)
    transparent = bool(obj.get("transparent", False)) or opacity < 0.999

    mat: dict[str, Any] = {
        "base_color": base_color,
        "metallic": metallic,
        "roughness": roughness,
        "emissive": emissive,
        "opacity": opacity,
        "transparent": transparent,
    }
    channels = obj.get("channels")
    if isinstance(channels, dict):
        for ch_val in channels.values():
            tex = str(ch_val or "").strip()
            if tex and tex in names:
                mat["texture"] = tex
                break
    return mat


def _load_a3d_resources(
    azf: zipfile.ZipFile, names: set[str]
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    model_paths: dict[str, str] = {}
    materials: dict[str, dict[str, Any]] = {}
    for json_name in ("resource_database.json", "Scene/Material Library.json"):
        if json_name not in names:
            continue
        payload = json.loads(azf.read(json_name).decode("utf-8"))
        for item in payload.get("items", []):
            obj = item.get("obj") if isinstance(item, dict) else None
            if not isinstance(obj, dict):
                continue
            uid = str(obj.get("uid", "")).strip().lower()
            if not uid:
                continue
            path = str(obj.get("path", "")).strip()
            if path.lower().endswith(".glb") and path in names:
                model_paths[uid] = path
            pbr = _extract_pbr_from_obj(obj, names)
            if pbr is not None and uid not in materials:
                materials[uid] = pbr
    return model_paths, materials


def parse_working_a3d_scene_info(a3d_bytes: bytes) -> dict[str, Any]:
    """Extract StageConfig fields (``width``, ``depth``, ``color``, ``enabled``)."""
    if not a3d_bytes:
        return {}
    try:
        with zipfile.ZipFile(io.BytesIO(a3d_bytes)) as azf:
            names = set(azf.namelist())
            _model_paths, materials = _load_a3d_resources(azf, names)
            if "Scene/Primitive.json" not in names:
                return {}
            payload = json.loads(azf.read("Scene/Primitive.json").decode("utf-8"))
            for entry in payload.get("items", []):
                obj = entry.get("obj") if isinstance(entry, dict) else None
                if not isinstance(obj, dict):
                    continue
                name = str(obj.get("name", "")).strip()
                world = obj.get("world") or obj.get("local") or {}
                lb = obj.get("local_bounds", {})
                lb_size = lb.get("size", {}) if isinstance(lb, dict) else {}
                if not isinstance(world, dict) or not _is_horizontal_ground(
                    name, world, lb_size
                ):
                    continue
                sc = world.get("scale", {})
                sz_src = (
                    lb_size
                    if isinstance(lb_size, dict) and lb_size
                    else obj.get("size", {})
                )
                sx = float(sc.get("x", 1.0)) if isinstance(sc, dict) else 1.0
                sy = float(sc.get("y", 1.0)) if isinstance(sc, dict) else 1.0
                is_sz = isinstance(sz_src, dict)
                wx = float(sz_src.get("x", 0.0)) * abs(sx) if is_sz else 0.0
                wy = float(sz_src.get("y", 0.0)) * abs(sy) if is_sz else 0.0
                if wx <= 0.0 or wy <= 0.0:
                    continue

                rgb: list[float] | None = None
                mat_uids = obj.get("material_uids")
                if isinstance(mat_uids, list):
                    for mu in mat_uids:
                        mat = materials.get(str(mu).strip().lower())
                        if mat is not None:
                            rgb = mat["base_color"]
                            break
                if rgb is None:
                    rgb = _parse_argb_hex(str(obj.get("color", "")))

                info: dict[str, Any] = {
                    "width": round(max(1.0, min(100.0, wx)), 2),
                    "depth": round(max(1.0, min(100.0, wy)), 2),
                    "enabled": True,
                }
                if rgb is not None:
                    info["color"] = _rgb_to_hex(rgb)
                return info
            return {}
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, KeyError):
        return {}


def parse_working_a3d_scenery(
    a3d_bytes: bytes, max_triangles: int = 80000
) -> list[dict[str, Any]]:
    """Extract 3D scenery meshes from ``working.a3d`` for ``olc-viz``."""
    if not a3d_bytes:
        return []
    try:
        with zipfile.ZipFile(io.BytesIO(a3d_bytes)) as azf:
            names = set(azf.namelist())
            model_paths, materials = _load_a3d_resources(azf, names)

            glb_cache: dict[
                str,
                tuple[
                    list[_Vec3],
                    list[_Vec3],
                    list[int],
                    list[tuple[float, float]],
                    dict[str, Any] | None,
                ],
            ] = {}
            scenery: list[dict[str, Any]] = []
            tri_budget = 0

            for json_name in (
                "Scene/Primitive.json",
                "Scene/Procedural Primitive.json",
            ):
                if json_name not in names:
                    continue
                payload = json.loads(azf.read(json_name).decode("utf-8"))
                for entry in payload.get("items", []):
                    obj = entry.get("obj") if isinstance(entry, dict) else None
                    if not isinstance(obj, dict):
                        continue
                    name = str(obj.get("name", "")).strip()
                    world = obj.get("world") or obj.get("local") or {}
                    if not isinstance(world, dict):
                        continue

                    lb = obj.get("local_bounds", {})
                    lb_center = lb.get("center", {}) if isinstance(lb, dict) else {}
                    lb_size = lb.get("size", {}) if isinstance(lb, dict) else {}
                    if _is_horizontal_ground(name, world, lb_size):
                        continue

                    m_uid = str(obj.get("model_uid") or "").strip().lower()
                    verts: list[_Vec3] = []
                    norms: list[_Vec3] = []
                    indices: list[int] = []
                    uvs: list[tuple[float, float]] = []
                    glb_pbr: dict[str, Any] | None = None
                    if m_uid in model_paths:
                        gpath = model_paths[m_uid]
                        if gpath not in glb_cache:
                            glb_cache[gpath] = _decode_glb_mesh_data(azf.read(gpath))
                        verts, norms, indices, uvs, glb_pbr = glb_cache[gpath]
                    elif isinstance(lb_size, dict) and lb_size:
                        verts, norms, indices = _box_mesh(
                            (
                                float(lb_center.get("x", 0.0)),
                                float(lb_center.get("y", 0.0)),
                                float(lb_center.get("z", 0.0)),
                            ),
                            (
                                float(lb_size.get("x", 0.0)),
                                float(lb_size.get("y", 0.0)),
                                float(lb_size.get("z", 0.0)),
                            ),
                        )

                    tri_count = len(indices) // 3
                    if tri_count == 0 or tri_budget + tri_count > max_triangles:
                        continue

                    mat_dict: dict[str, Any] | None = None
                    mat_uids = obj.get("material_uids")
                    if isinstance(mat_uids, list):
                        for mu in mat_uids:
                            found = materials.get(str(mu).strip().lower())
                            if found is not None:
                                mat_dict = dict(found)
                                break
                    if mat_dict is None and glb_pbr is not None:
                        mat_dict = dict(glb_pbr)
                    if mat_dict is None:
                        base_rgb = _parse_argb_hex(str(obj.get("color", ""))) or [
                            0.45,
                            0.45,
                            0.48,
                        ]
                        mat_dict = {
                            "base_color": base_rgb,
                            "metallic": 0.0,
                            "roughness": 0.5,
                            "emissive": [0.0, 0.0, 0.0],
                            "opacity": 1.0,
                            "transparent": False,
                        }

                    out_v, out_n = _transform_world(world, verts, norms)
                    item_dict: dict[str, Any] = {
                        "name": name,
                        "color": mat_dict["base_color"],
                        "material": mat_dict,
                        "vertices": out_v,
                        "normals": out_n,
                        "indices": indices,
                    }
                    if uvs:
                        item_dict["uvs"] = [list(u) for u in uvs]
                    scenery.append(item_dict)
                    tri_budget += tri_count

            return scenery
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, KeyError):
        return []


def parse_working_a3d_patch(
    a3d_bytes: bytes,
) -> dict[int, dict[str, _Vec3]]:
    """Extract per-channel 3D ``position`` and ``orientation`` from ``working.a3d``."""
    result: dict[int, dict[str, _Vec3]] = {}
    if not a3d_bytes:
        return result

    try:
        with zipfile.ZipFile(io.BytesIO(a3d_bytes)) as azf:
            if "Scene/Patch.json" not in azf.namelist():
                return result
            raw_json = azf.read("Scene/Patch.json")
            payload: Any = json.loads(raw_json.decode("utf-8"))
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError):
        return result

    items = payload.get("items", payload) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return result

    for entry in items:
        if not isinstance(entry, dict):
            continue
        obj = entry.get("obj")
        if not isinstance(obj, dict):
            continue
        console_data = obj.get("console_data")
        try:
            channel = int(console_data)
        except (TypeError, ValueError):
            continue
        if channel <= 0:
            continue

        local = obj.get("local")
        if not isinstance(local, dict):
            continue

        meta: dict[str, _Vec3] = {}
        pos = local.get("pos")
        if isinstance(pos, dict):
            meta["position"] = (
                float(pos.get("x", 0.0)),
                float(pos.get("y", 0.0)),
                float(pos.get("z", 0.0)),
            )
        eulers = local.get("eulers")
        if isinstance(eulers, dict):
            meta["orientation"] = eos_euler_to_olc(
                float(eulers.get("x", 0.0)),
                float(eulers.get("y", 0.0)),
                float(eulers.get("z", 0.0)),
            )
        if meta:
            result[channel] = meta

    return result
