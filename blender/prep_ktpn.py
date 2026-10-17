"""
Готовит КТПН KTPN1.glb (сгенерированная модель: ~1 млн треугольников, текстуры 4096², размер ~1 м) для сцены
«Улица у КТПН» и сохраняет в blender/assets/ktpn1.glb (ось Z вверх, как остальные готовые модели).
Двери в файле смотрят на −Y, левая створка распахнута наружу.

Начало координат готовой модели — правый передний угол корпуса на земле: корпус занимает x ∈ [−длина, 0],
y ∈ [0, глубина], открытая створка выходит в y < 0. Так build_landscape.py ставит её фасадом и правым краем
туда же, где были фасад и правый край прежней КТПН, — огнетушитель и посторонние остаются на своих местах.

Запуск (из корня проекта), после него — пересобрать сцену build_landscape.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_ktpn.py
"""

import os
import sys

import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from prep_model import export_asset, import_decimated, shrink_textures, vertices  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "KTPN1.glb")
OUT = os.path.join(ROOT, "blender", "assets", "ktpn1.glb")

LENGTH = 4.6     # длина корпуса вдоль фасада, м (высота выходит ~3 м)
DECIMATE = 0.05  # доля треугольников, которая остаётся (~50 тыс.)


def build():
    o = import_decimated(SRC, DECIMATE)
    co = vertices(o)
    lo, hi = co.min(0), co.max(0)
    # Фасад — передняя стенка правого (закрытого) отсека на средней высоте; распахнутая створка слева его не задевает
    wall = co[(co[:, 0] > (lo[0] + hi[0]) / 2) & (co[:, 2] > 0.3 * hi[2]) & (co[:, 2] < 0.7 * hi[2])]
    front = float(np.percentile(wall[:, 1], 0.5))
    k = LENGTH / (hi[0] - lo[0])
    o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation((-hi[0], -front, -lo[2])))
    o.name = "ktpn_body"
    print("ktpn size, m: length %.2f, depth %.2f, height %.2f, door out %.2f"
          % ((hi[0] - lo[0]) * k, (hi[1] - front) * k, (hi[2] - lo[2]) * k, (front - lo[1]) * k))
    shrink_textures()
    export_asset(OUT)


build()
