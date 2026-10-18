"""
Готовит кусты kusty_dlya_fona.glb (сгенерированный набор одним мешем: подстриженные бордюры, цветущие кусты,
цветники в бетонных рамках; ~0,5 млн треугольников, текстуры 4096², размер ~1 м) и сохраняет в
blender/assets/kusty.glb отдельными объектами (ось Z вверх, как остальные готовые модели). Начало координат
каждого — центр низа, так что в сцене их удобно клонировать по одному (build_city.py, place_kusty).

Элементы набора разделены на несвязанные куски меша; куски, которые стоят друг на друге (куст на подложке),
объединяются в один элемент. Имена — по порядку элементов слева направо (по X) в исходном файле.

Запуск (из корня проекта), после него — пересобрать сцену build_city.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_kusty.py
"""

import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from prep_model import export_asset, import_decimated, shrink_textures, vertices  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "kusty_dlya_fona.glb")
OUT = os.path.join(ROOT, "blender", "assets", "kusty.glb")

NAMES = ("cvetnik_1", "kust_na_podlozhke", "cvetnik_2", "bordur_dlinny", "kusty_para", "cvetnik_3",
         "bordur_korotky", "kusty_ugol")
BORDUR_H = 0.9     # высота подстриженного бордюра, м — по ней масштаб всего набора
DECIMATE = 0.03


def islands(bm):
    """Группы граней: несвязанные куски меша, объединённые, если они перекрываются в плане"""
    bm.faces.ensure_lookup_table()
    comp, seen = [], set()
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, part = [f], []
        seen.add(f.index)
        while stack:
            a = stack.pop()
            part.append(a)
            for e in a.edges:
                for b in e.link_faces:
                    if b.index not in seen:
                        seen.add(b.index)
                        stack.append(b)
        comp.append(part)
    boxes = []
    for part in comp:
        co = np.array([v.co[:] for f in part for v in f.verts])
        boxes.append((co.min(0), co.max(0)))
    parent = list(range(len(comp)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    t = 0.003
    for i in range(len(comp)):
        for j in range(i + 1, len(comp)):
            (alo, ahi), (blo, bhi) = boxes[i], boxes[j]
            if (alo[:2] - t <= bhi[:2]).all() and (blo[:2] - t <= ahi[:2]).all():
                parent[root(i)] = root(j)
    groups = {}
    for i, part in enumerate(comp):
        groups.setdefault(root(i), []).extend(part)
    groups = [g for g in groups.values() if len(g) > 20]  # крошки после упрощения
    return sorted(groups, key=lambda g: min(v.co.x for f in g for v in f.verts))


def build():
    o = import_decimated(SRC, DECIMATE)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    groups = [{f.index for f in g} for g in islands(bm)]
    bm.free()
    assert len(groups) == len(NAMES), f"элементов {len(groups)}, ждали {len(NAMES)}"
    k = None
    for name, idx in zip(NAMES, groups):
        t = o.copy()
        t.data = o.data.copy()
        t.name = t.data.name = name
        bpy.context.collection.objects.link(t)
        bm = bmesh.new()
        bm.from_mesh(t.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in idx], context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(t.data)
        bm.free()
        co = vertices(t)
        lo, hi = co.min(0), co.max(0)
        if k is None:
            k = BORDUR_H / (vertices_height(o, groups, NAMES))
        base = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2])
        t.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation([-c for c in base]))
        t.location = [c * k for c in base]
        print(name, "size, m:", ((hi - lo) * k).round(2).tolist())
    bpy.data.objects.remove(o)
    shrink_textures()
    export_asset(OUT)


def vertices_height(o, groups, names):
    """Высота длинного бордюра в единицах файла"""
    idx = groups[names.index("bordur_dlinny")]
    z = [v.co.z for f in o.data.polygons if f.index in idx for v in (o.data.vertices[i] for i in f.vertices)]
    return max(z) - min(z)


build()
