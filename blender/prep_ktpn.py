"""
Готовит КТПН с монтёром monter_u_ktpn_dlya_1sceny.glb (сгенерированная модель одним мешем: ~1,5 млн треугольников,
текстуры 4096², размер ~1 м) для сцены «Улица у КТПН» и сохраняет в blender/assets/ktpn_monter.glb (ось Z вверх,
как остальные готовые модели). Двери в файле смотрят на −Y, обе створки распахнуты, монтёр стоит в проёме
и руками лезет к проводам. Масштаб — по росту монтёра.

Начало координат готовой модели — правый передний угол корпуса на земле: корпус занимает x ∈ [−ширина, 0],
y ∈ [0, глубина]; створки и монтёр выходят в y < 0, правая створка — ещё и в x > 0.

Запуск (из корня проекта), после него — пересобрать сцену build_landscape.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_ktpn.py
"""

import os
import sys

import bpy
from mathutils import Matrix
from mathutils import Vector as V
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(__file__))
from prep_model import export_asset, import_decimated, shrink_textures, vertices  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "monter_u_ktpn_dlya_1sceny.glb")
OUT = os.path.join(ROOT, "blender", "assets", "ktpn_monter.glb")

WORKER_HEIGHT = 1.8  # рост монтёра, м — по нему масштаб всей модели
DECIMATE = 0.04      # доля треугольников, которая остаётся (~60 тыс.)


def build():
    o = import_decimated(SRC, DECIMATE)
    co = vertices(o)
    lo = co.min(0)
    right = co[co[:, 1] > 0.5 * co[:, 1].max()][:, 0].max()  # задняя половина: без распахнутой правой створки
    tree = BVHTree.FromObject(o, bpy.context.evaluated_depsgraph_get())
    # Фасад — передняя стойка у правого края корпуса; макушка монтёра — самая высокая точка перед фасадом
    # в середине проёма (створки — по краям)
    front = min(tree.ray_cast(V((right - 0.02, lo[1] - 1, z)), V((0, 1, 0)))[0].y for z in (0.1, 0.2, 0.3))
    mid = (lo[0] + right) / 2
    top = max((hit.z for x in range(-25, 26) for y in range(0, 25)
               if (hit := tree.ray_cast(V((mid + x * 0.01, front - y * 0.01, 2)), V((0, 0, -1)))[0]) is not None
               and hit.z < 0.8 * co[:, 2].max()), default=None)
    k = WORKER_HEIGHT / (top - lo[2])
    o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation((-right, -front, -lo[2])))
    o.name = "ktpn_body"
    co = vertices(o)
    body = co[co[:, 1] > 0]
    print("ktpn size, m: width %.2f, depth %.2f, height %.2f; doors out %.2f in front, %.2f to the right"
          % (-body[:, 0].min(), co[:, 1].max(), co[:, 2].max(), -co[:, 1].min(), co[:, 0].max()))
    shrink_textures()
    export_asset(OUT)


build()
