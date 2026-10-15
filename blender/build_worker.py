"""
Персонаж игрока из готовой модели blender/assets/kazakhtelecom_worker_lowpoly.glb.

Запуск (из корня проекта):
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/build_worker.py

Результат:
    public/models/worker.glb — персонаж для режима ходьбы (/walk)

Исходный файл сохранён с осью Z вверх, ростом 2,7 м и без узлов для анимации. Здесь он ставится вертикально,
приводится к росту прежнего монтёра (1,9 м), а рукава с кистями и брюки с ботинками собираются под узлы
arm_L / arm_R / leg_L / leg_R — их качает движок при ходьбе (src/walk/engine.ts).
Персонаж смотрит по +Z игры (в исходнике — по −Y), поэтому его левая сторона — +X: это суффикс _L.
"""

import math
import os

import bpy
from mathutils import Matrix
from mathutils import Vector as V

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "blender", "assets", "kazakhtelecom_worker_lowpoly.glb")
OUT = os.path.join(ROOT, "public", "models", "worker.glb")

HEIGHT = 1.9  # рост от подошвы до верха каски, м
ARM_PARTS = ("upper_sleeve", "lower_sleeve", "hand")  # плечевая накладка остаётся на корпусе
LEG_PARTS = ("trouser", "boot")


def bbox(objs):
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    return V([min(p[i] for p in pts) for i in range(3)]), V([max(p[i] for p in pts) for i in range(3)])


def unmirror_decal(o):
    """Если наклейка (логотип, надпись) читается зеркально для зрителя снаружи, переворачивает её UV.
    Наружу — от вертикальной оси персонажа (x = y = 0)"""
    me = o.data
    uv = me.uv_layers.active.data
    poly = me.polygons[0]
    loops = list(poly.loop_indices)
    pts = [me.vertices[me.loops[i].vertex_index].co for i in loops]
    us = [uv[i].uv.x for i in loops]
    du = pts[us.index(max(us))] - pts[us.index(min(us))]
    c = sum(pts, V()) / len(pts)
    n = poly.normal.copy()
    if n.dot(V((c.x, c.y, 0))) < 0:
        n = -n
    if du.dot((-n).cross(V((0, 0, 1)))) < 0:
        for l in uv:
            l.uv.x = 1 - l.uv.x


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]

    # Запекаем импортные трансформы и поворот «лёжа → стоя» прямо в вершины
    stand = Matrix.Rotation(math.radians(-90), 4, "X")
    done = set()
    for o in meshes:
        mw = stand @ o.matrix_world
        if o.data in done:
            o.data = o.data.copy()
        done.add(o.data)
        o.parent = None
        o.data.transform(mw)
        o.matrix_world = Matrix.Identity(4)
    for o in [o for o in bpy.data.objects if o.type != "MESH"]:
        bpy.data.objects.remove(o)

    # Рост как у прежнего монтёра, подошвы на земле
    lo, hi = bbox(meshes)
    fit = Matrix.Scale(HEIGHT / (hi.z - lo.z), 4) @ Matrix.Translation((0, 0, -lo.z))
    for o in meshes:
        o.data.transform(fit)
        if "logo" in o.name.lower() and o.data.uv_layers:
            unmirror_decal(o)
    bpy.context.view_layer.update()

    root = bpy.data.objects.new("worker", None)
    bpy.context.collection.objects.link(root)

    def limb(name, parts, pivot_of):
        objs = [o for o in meshes if o.name.startswith(parts) and
                (bbox([o])[0].x + bbox([o])[1].x > 0) == name.endswith("_L")]
        e = bpy.data.objects.new(name, None)
        bpy.context.collection.objects.link(e)
        e.location = pivot_of(objs)
        e.parent = root
        bpy.context.view_layer.update()
        for o in objs:
            o.parent = e
            o.matrix_parent_inverse = e.matrix_world.inverted()
        return objs

    def shoulder(objs):
        lo, hi = bbox([o for o in objs if o.name.startswith("upper_sleeve")])
        return V(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z - 0.04))

    def hip(objs):
        lo, hi = bbox([o for o in objs if o.name.startswith("trouser")])
        return V(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z))

    moved = []
    for side in ("L", "R"):
        moved += limb(f"arm_{side}", ARM_PARTS, shoulder)
        moved += limb(f"leg_{side}", LEG_PARTS, hip)
    for o in meshes:
        if o not in moved:
            o.parent = root

    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_extras=True)


build()
print("Готово:", OUT)
