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

# имя: (исходник в корне проекта, результат в blender/assets, размер в метрах, доля треугольников[, HD]);
# размер — высота модели, или ("width", w) — ширина по X; HD — текстуры вдвое крупнее обычного (для моделей,
# к которым игрок подходит близко и на которых видна размытость)
MODELS = {
    # Сумка монтёра с инструментом и огнетушитель; выше всего — огнетушитель с рукояткой
    "sumka": ("sumka_montera_ognetushitel.glb", "sumka_ognetushitel.glb", 0.55, 0.08),
    # Мужчина присел на корточки и показывает рукой, рядом собака и мальчик; выше всего — мужчина в тюбетейке
    "muzhik": ("muzhik_pes_pacan.glb", "muzhik_pes_pacan.glb", 1.3, 0.08),
    # Усадьба: дом с крыльцом, сарай, колодец, грядки, дерево и забор на травяной подложке; крыльцо смотрит на −Y
    "dom": ("village_dom_dlya_1sceny.glb", "dom_usadba.glb", ("width", 16.0), 0.04),
    # Одноэтажный дом с крыльцом и вальмовой крышей без участка — дальние дома у дороги; крыльцо смотрит на −Y
    "odin": ("odinochny_dom_village.glb", "dom_odinochny.glb", ("width", 8.0), 0.04),
    # Городской колодец: люк, ограждение, знак, монтёр в люке и монтёр с газоанализатором (он выше всего);
    # ограждение и знак смотрят на −Y. Низ модели — дно шахты: земля на 0,3 м выше, монтёр от неё — 1,8 м
    "kolodec": ("dva_montera_u_gorodskogo kolodca.glb", "dva_montera_kolodec.glb", 2.04, 0.04),
    # Городской квартал: четыре пятиэтажки на общей подложке с газонами и дорожками; фасады смотрят на −Y
    "doma": ("gorodskie_doma_dlya_scen.glb", "gorodskie_doma.glb", 18.0, 0.04),
    # Лестница колодца, лежит на земле, и бензиновый генератор (он выше всего — 0,6 м); панель генератора — на −Y
    "lestnica": ("lestnica_i_dga.glb", "lestnica_dga.glb", 0.6, 0.03),
    # Автобусная остановка: навес, стеклянные стенки, скамейка, урна, знак на столбе (он выше всего); скамейка — на −Y
    "ostanovka": ("avtobusnaya_ostanovka.glb", "avtobusnaya_ostanovka.glb", 2.9, 0.03),
    # Монтёр без каски с отвёрткой в руках, лицом к +X — работает в корзине автовышки (build_evening.py)
    "monter_otvertka": ("monter_s_otvertkoi.glb", "monter_otvertka.glb", 1.8, 0.04),
    # Серверная стойка 42U с оборудованием и кабелями, фасадом к −Y; высота 2 м (серверная, build_server.py)
    "server": ("servera.glb", "server_rack.glb", 2.0, 0.05, True),
    # Монтёр сидит за столом с компьютером, лицом к монитору на −Y; выше всего — макушка сидящего (1,32 м)
    "monter_comp": ("monter_za_compom.glb", "monter_za_compom.glb", 1.32, 0.04),
    # Монтёр льёт воду из ведра в открытую стойку (нарушение); стойка фасадом к −X, монтёр перед ней;
    # выше всего — верх стойки (2 м, как у остальных стоек)
    # Пожарный шкаф без рукава (открыт, видны кран и табличка) и пустой кронштейн огнетушителя; фасадом к −Y
    "pozh_shkaf": ("bez_shlanga_i_ognetushitel.glb", "pozh_shkaf.glb", ("width", 1.0), 0.04),
    "monter_tushit": ("monter_tushit_server.glb", "monter_tushit_server.glb", 2.0, 0.05, True),
}


def prepare(src, out, size, ratio, hd=False):
    o = import_decimated(os.path.join(ROOT, src), ratio)
    co = vertices(o)
    lo, hi = co.min(0), co.max(0)
    k = size[1] / (hi[0] - lo[0]) if isinstance(size, tuple) else size / (hi[2] - lo[2])
    o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])))
    o.name = os.path.splitext(out)[0]
    print(src, "size, m:", ((hi - lo) * k).round(2).tolist())
    shrink_textures(2 if hd else 1)
    export_asset(os.path.join(ROOT, "blender", "assets", out))


def build():
    names = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else list(MODELS)
    for name in names:
        prepare(*MODELS[name])


build()
