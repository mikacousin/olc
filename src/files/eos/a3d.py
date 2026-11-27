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


def _decode_glb_mesh(
    glb_bytes: bytes,
) -> tuple[list[_Vec3], list[_Vec3], list[int]]:
    """Decode a glTF 2.0 binary (``.glb``) into ``(vertices, normals, indices)``."""
    if len(glb_bytes) < 12 or glb_bytes[:4] != _GLB_MAGIC:
        return [], [], []
    _magic, version, total_len = struct.unpack_from("<4sII", glb_bytes, 0)
    if version != 2 or total_len > len(glb_bytes):
        return [], [], []

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
                return [], [], []
        elif chunk_type == _GLB_CHUNK_BIN and not bin_data:
            bin_data = chunk_bytes

    if gltf is None:
        return [], [], []

    meshes = gltf.get("meshes", [])
    if not isinstance(meshes, list) or not meshes:
        return [], [], []

    mesh_mats = _collect_mesh_node_transforms(gltf)
    all_verts: list[_Vec3] = []
    all_norms: list[_Vec3] = []
    all_indices: list[int] = []

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
                all_indices.extend(base_v + idx for idx in prim_indices)

    return all_verts, all_norms, all_indices


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


def parse_working_a3d_scenery(
    a3d_bytes: bytes, max_triangles: int = 80000
) -> list[dict[str, Any]]:
    """Extract 3D scenery meshes from ``working.a3d`` for ``olc-viz``."""
    if not a3d_bytes:
        return []
    try:
        with zipfile.ZipFile(io.BytesIO(a3d_bytes)) as azf:
            names = set(azf.namelist())
            model_paths: dict[str, str] = {}
            materials: dict[str, list[float]] = {}
            if "resource_database.json" in names:
                rdb = json.loads(azf.read("resource_database.json").decode("utf-8"))
                for item in rdb.get("items", []):
                    obj = item.get("obj") if isinstance(item, dict) else None
                    if not isinstance(obj, dict):
                        continue
                    uid = str(obj.get("uid", "")).strip().lower()
                    if not uid:
                        continue
                    path = str(obj.get("path", "")).strip()
                    if path.lower().endswith(".glb") and path in names:
                        model_paths[uid] = path
                    bc = obj.get("base_color")
                    if isinstance(bc, dict) and all(k in bc for k in ("x", "y", "z")):
                        materials[uid] = [
                            round(max(0.0, min(1.0, float(bc["x"]))), 4),
                            round(max(0.0, min(1.0, float(bc["y"]))), 4),
                            round(max(0.0, min(1.0, float(bc["z"]))), 4),
                        ]

            glb_cache: dict[str, tuple[list[_Vec3], list[_Vec3], list[int]]] = {}
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
                    pos_z = float(world.get("pos", {}).get("z", 0.0))
                    sc_z = float(world.get("scale", {}).get("z", 1.0))
                    sz_z = float(lb_size.get("z", 0.0))
                    if (
                        name.lower() == "ground"
                        and abs(pos_z) < 0.05
                        and sz_z * sc_z < 0.01
                    ):
                        continue

                    m_uid = str(obj.get("model_uid") or "").strip().lower()
                    verts: list[_Vec3] = []
                    norms: list[_Vec3] = []
                    indices: list[int] = []
                    if m_uid in model_paths:
                        gpath = model_paths[m_uid]
                        if gpath not in glb_cache:
                            glb_cache[gpath] = _decode_glb_mesh(azf.read(gpath))
                        verts, norms, indices = glb_cache[gpath]
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
                                sz_z,
                            ),
                        )

                    tri_count = len(indices) // 3
                    if tri_count == 0 or tri_budget + tri_count > max_triangles:
                        continue

                    color: list[float] | None = None
                    mat_uids = obj.get("material_uids")
                    if isinstance(mat_uids, list):
                        for mu in mat_uids:
                            col = materials.get(str(mu).strip().lower())
                            if col is not None:
                                color = col
                                break
                    if color is None:
                        color = _parse_argb_hex(str(obj.get("color", ""))) or [
                            0.45,
                            0.45,
                            0.48,
                        ]

                    out_v, out_n = _transform_world(world, verts, norms)
                    scenery.append(
                        {
                            "name": name,
                            "color": color,
                            "vertices": out_v,
                            "normals": out_n,
                            "indices": indices,
                        }
                    )
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
