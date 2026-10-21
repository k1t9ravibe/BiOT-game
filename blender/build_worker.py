"""
Персонаж игрока из модели пользователя monter_walk.glb (корень проекта): монтёр Казахтелекома в каске,
со скелетом и анимациями шага и бега.

Запуск (из корня проекта):
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/build_worker.py

Результат:
    public/models/worker.glb — персонаж для режима ходьбы (/walk и остальные сцены)

В исходнике рядом с монтёром лежит лишняя икосфера — она удаляется. Из анимаций остаются Walking и Running
(обе на месте, без хода корня); walking_2 уводит корень вперёд, а walking_2_inplace дублирует шаг — убираются.
Движок проигрывает Walking/Running через AnimationMixer, а в покое плавно возвращает позу покоя (src/walk/engine.ts).
Персонаж смотрит по −Y (в игре — по +Z), левая рука — на +X, как у прежнего монтёра.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix
from mathutils import Vector as V

sys.path.insert(0, os.path.dirname(__file__))
from prep_model import shrink_textures  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "monter_walk.glb")
OUT = os.path.join(ROOT, "public", "models", "worker.glb")

HEIGHT = 1.85  # рост от подошвы до верха каски, м
RATIO = 0.35  # доля треугольников после упрощения (в исходнике 165 тыс.)
KEEP = ("Walking", "Running")


def mesh_bbox(o):
    pts = [o.matrix_world @ v.co for v in o.data.vertices]
    return V([min(p[i] for p in pts) for i in range(3)]), V([max(p[i] for p in pts) for i in range(3)])


def decimate(o):
    """Как prep_model.import_decimated: склеить вершины и пометить швы развёртки, иначе упрощение
    тянет края островков UV в тёмные щели атласа. Группы вершин (веса скелета) упрощение сохраняет"""
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
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
    m.ratio = RATIO
    bpy.ops.object.modifier_move_to_index(modifier=m.name, index=0)  # до модификатора скелета
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))


def stride(arm, action):
    """Сколько метров проходит персонаж за один цикл анимации: стопа в опоре едет назад относительно корпуса,
    за цикл два шага. Печатается для подбора скорости проигрывания в движке"""
    arm.animation_data.action = action
    sc = bpy.context.scene
    f0, f1 = (int(round(f)) for f in action.frame_range)
    ys = []
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        ys.append((arm.matrix_world @ arm.pose.bones["foot.L"].head).y)
    fps = sc.render.fps / sc.render.fps_base
    return 2 * (max(ys) - min(ys)), (f1 - f0) / fps


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)
    for o in [o for o in bpy.data.objects if o.type not in ("ARMATURE", "MESH") or o.name.startswith("Икосфера")]:
        bpy.data.objects.remove(o)
    for a in [a for a in bpy.data.actions if a.name not in KEEP]:
        bpy.data.actions.remove(a)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = next(o for o in bpy.data.objects if o.type == "MESH")
    arm.name = "worker"

    # Рост — по позе покоя; масштаб остаётся на узле скелета, тогда ключи анимации менять не нужно
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    lo, hi = mesh_bbox(body)
    arm.scale = (HEIGHT / (hi.z - lo.z),) * 3
    arm.location.z -= lo.z * arm.scale.z
    bpy.context.view_layer.update()

    decimate(body)
    print("tris", sum(len(p.vertices) - 2 for p in body.data.polygons))
    shrink_textures()

    for name in KEEP:
        m, t = stride(arm, bpy.data.actions[name])
        print(f"{name}: {m:.2f} m per cycle of {t:.2f} s -> {m / t:.2f} m/s")
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)

    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_image_format="JPEG", export_jpeg_quality=85,
                              export_animation_mode="ACTIONS", export_force_sampling=True)
    print("saved", OUT, os.path.getsize(OUT) // 1024, "KB")


build()
