"""
Общие шаги подготовки сгенерированных моделей (prep_furgon.py, prep_ktpn.py): такие модели приходят
с ~1–1,5 млн треугольников, текстурами 4096² и размером ~1 м. Здесь — импорт с упрощением меша,
уменьшение текстур и сохранение в blender/assets в том виде, которого ждёт place_model в build_landscape.py.
"""

import math
import os

import bmesh
import bpy
import numpy as np

TEX = {"normal": 1024, "metallic": 1024}  # размер текстур по части имени; остальные (цвет) — 2048
TEX_DEFAULT = 2048


def import_decimated(src, ratio):
    """Импортирует модель из одного меша и упрощает её до доли ratio треугольников. Возвращает объект"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=src)
    o = next(o for o in bpy.data.objects if o.type == "MESH")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)  # импорт кладёт поворот Y→Z в объект

    # glTF хранит меш разрезанным по швам развёртки, и упрощение двигает края островков UV в тёмные щели атласа —
    # на модели появляются чёрные треугольники. Склеиваем вершины и помечаем швы, тогда упрощение их бережёт
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.to_mesh(o.data)
    bm.free()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.seams_from_islands()
    bpy.ops.object.mode_set(mode="OBJECT")

    m = o.modifiers.new("decimate", "DECIMATE")
    m.ratio = ratio
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
    return o


def vertices(o):
    co = np.empty(len(o.data.vertices) * 3, np.float32)
    o.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def shrink_textures(scale=1):
    """scale — во сколько раз крупнее обычного оставить текстуры (2 — HD: цвет 4096, карты 2048)"""
    maps = set()  # карты, названные безлико (Image_0…): узнаём по тому, что текстура не идёт в цвет
    for m in bpy.data.materials:
        if m.node_tree:
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image and not any(
                        l.to_socket.name == "Base Color" for o in n.outputs for l in o.links):
                    maps.add(n.image.name)
    for img in bpy.data.images:
        if img.size[0] == 0:
            continue
        key = "normal" if img.name in maps else img.name.lower()
        side = int(next((s for k, s in TEX.items() if k in key), TEX_DEFAULT) * scale)
        if img.size[0] > side:
            img.scale(side, side)


def export_asset(out):
    # export_yup=False — как у остальных моделей в blender/assets: place_model ставит их поворотом на −90° по X
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_yup=False, export_image_format="JPEG",
                              export_jpeg_quality=85)
    print("saved", out, os.path.getsize(out) // 1024, "KB")
