"""
Готовит простые сгенерированные модели для сцены «Улица у КТПН» (по ~0,5 млн треугольников, текстуры 4096²,
размер ~1 м): упрощает меш, уменьшает текстуры, ставит в натуральную величину и сохраняет в blender/assets
(ось Z вверх, как остальные готовые модели): лицевой стороной к −Y, низ на нуле, центр в начале координат.

Запуск (из корня проекта) — все модели или только перечисленные; после него — пересобрать сцену build_landscape.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_static.py
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_static.py -- sumka
"""

import os
import sys

from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from prep_model import export_asset, import_decimated, shrink_textures, vertices  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# имя: (исходник в корне проекта, результат в blender/assets, размер в метрах, доля треугольников);
# размер — высота модели, или ("width", w) — ширина по X
MODELS = {
    # Сумка монтёра с инструментом и огнетушитель; выше всего — огнетушитель с рукояткой
    "sumka": ("sumka_montera_ognetushitel.glb", "sumka_ognetushitel.glb", 0.55, 0.08),
    # Мужчина присел на корточки и показывает рукой, рядом собака и мальчик; выше всего — мужчина в тюбетейке
    "muzhik": ("muzhik_pes_pacan.glb", "muzhik_pes_pacan.glb", 1.3, 0.08),
    # Усадьба: дом с крыльцом, сарай, колодец, грядки, дерево и забор на травяной подложке; крыльцо смотрит на −Y
    "dom": ("village_dom_dlya_1sceny.glb", "dom_usadba.glb", ("width", 16.0), 0.04),
}


def prepare(src, out, size, ratio):
    o = import_decimated(os.path.join(ROOT, src), ratio)
    co = vertices(o)
    lo, hi = co.min(0), co.max(0)
    k = size[1] / (hi[0] - lo[0]) if isinstance(size, tuple) else size / (hi[2] - lo[2])
    o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])))
    o.name = os.path.splitext(out)[0]
    print(src, "size, m:", ((hi - lo) * k).round(2).tolist())
    shrink_textures()
    export_asset(os.path.join(ROOT, "blender", "assets", out))


def build():
    names = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else list(MODELS)
    for name in names:
        prepare(*MODELS[name])


build()
