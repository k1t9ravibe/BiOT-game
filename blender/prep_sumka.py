"""
Готовит sumka_montera_ognetushitel.glb (сгенерированная модель: сумка монтёра с инструментом и огнетушитель рядом,
~0,5 млн треугольников, текстуры 4096²) для сцены «Улица у КТПН» и сохраняет в blender/assets/sumka_ognetushitel.glb
(ось Z вверх, как остальные готовые модели): лицевой стороной к −Y, низ на нуле, центр в начале координат.

Запуск (из корня проекта), после него — пересобрать сцену build_landscape.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_sumka.py
"""

import os
import sys

from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from prep_model import export_asset, import_decimated, shrink_textures, vertices  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "sumka_montera_ognetushitel.glb")
OUT = os.path.join(ROOT, "blender", "assets", "sumka_ognetushitel.glb")

HEIGHT = 0.55    # высота огнетушителя с рукояткой, м (выше всего в модели)
DECIMATE = 0.08  # доля треугольников, которая остаётся (~40 тыс.)


def build():
    o = import_decimated(SRC, DECIMATE)
    co = vertices(o)
    lo, hi = co.min(0), co.max(0)
    k = HEIGHT / (hi[2] - lo[2])
    o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])))
    o.name = "sumka_body"
    print("size, m:", ((hi - lo) * k).round(2).tolist())
    shrink_textures()
    export_asset(OUT)


build()
