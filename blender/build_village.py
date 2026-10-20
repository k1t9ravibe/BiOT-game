"""
Локация 6 «Окраина деревни»: сельская улица днём. Вдоль дороги (плитки asfalt.glb, как на трассе) по одной
стороне — дома из сцены 1 (усадьбы dom_usadba и одиночные дома dom_odinochny); там, где дома кончаются, —
окраина: поле с газоном (zemlya_trava), лесополоса (derevya, kusty) и огороженная площадка с высокой вышкой
сотовой связи (sotovaya_vyshka.glb, 36 м). У ворот площадки — фургон Казахтелекома из локации 1.

Запуск (из корня проекта):
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/build_village.py

Результат:
    public/models/village.glb   — сцена для игры (http://localhost:5173/village)
    blender/village_base.blend  — исходник; скрипт перезаписывает его при каждом запуске

Оси Blender: X — вдоль улицы (игрок идёт на +X, к вышке), Y — поперёк (дома на +Y, поле и вышка на −Y), Z — вверх.
Имена, которые читает игра, — как в build_city.py.
"""

import math
import os
import random
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
import build_city as city  # noqa: E402
import build_highway as hw  # noqa: E402
from lowpoly import M, MB, empty, mat  # noqa: E402

ROOT = city.ROOT
OUT_GLB = os.path.join(ROOT, "public", "models", "village.glb")
OUT_BLEND = os.path.join(ROOT, "blender", "village_base.blend")
USADBA_GLB = os.path.join(ROOT, "blender", "assets", "dom_usadba.glb")       # усадьба 16 × 16,2 м (сцена 1)
ODIN_GLB = os.path.join(ROOT, "blender", "assets", "dom_odinochny.glb")      # одиночный дом 8 × 7,2 м (сцена 1)
VYSHKA_GLB = os.path.join(ROOT, "blender", "assets", "sotovaya_vyshka.glb")  # вышка 36 м, основание 5,7 × 6,1 м
NIVA_GLB = os.path.join(ROOT, "blender", "assets", "niva.glb")               # «Нива» 3,74 м

X0, X1 = -160, 160           # дорога по X
SHOULDER = hw.SHOULDER       # край гравийной обочины, 5,4 м от оси
YARD_Y = 7.5                 # от оси дороги до фасадной границы участков на +Y
# Дома по +Y: (вид, x центра); усадьбы и одиночные дома вперемешку, крыльцом к дороге. Дальше X_LAST — окраина
HOUSES = [("usadba", -128), ("odin", -110), ("usadba", -92), ("odin", -74), ("odin", -63), ("usadba", -45),
          ("odin", -27), ("usadba", -9), ("odin", 9)]
HOUSE_DEPTH = {"usadba": 16.2, "odin": 7.2}
HOUSE_SINK = {"usadba": 0.1, "odin": 0.0}  # подложку усадьбы чуть утапливаем в газон
# Дома за дорогой на −Y (только в деревне, до поля): крыльцом к дороге
HOUSES_FAR = [("odin", -120), ("usadba", -100), ("odin", -80), ("usadba", -60)]
X_LAST = 20                  # дальше по +Y — тоже поле

# Площадка вышки на −Y, за полем у обочины; ограда сеткой с воротами к дороге, внутри гравий
VYSHKA_POS = (42.0, -21.0)
FENCE = (6.0, 6.0)           # полуразмеры ограды
FENCE_H = 2.2
GATE = (39.0, 45.0)          # проём ворот в ближней к дороге стороне ограды (по X)
VAN_POS = (35.0, -11.2)      # фургон на подъезде к воротам, мордой по ходу игрока (+X)
NIVA_POS = (28.6, -11.0)     # «Нива» за фургоном (его зад — x 32,2), тоже мордой на +X

TILE_STEP = hw.TILE_STEP     # плитки газона 6 × 6,42 м с шагом чуть меньше плитки
TILE_X = (-55, 95)           # вдоль маршрута игрока
TILE_TOP = hw.TILE_TOP

random.seed(6)


def materials():
    hw.materials()
    M["fence"] = mat("Сетка ограды", "#8E959B", rough=0.5, metal=0.6)
    M["fence_post"] = mat("Стойка ограды", "#6F767C", rough=0.5, metal=0.7)
    M["pad"] = mat("Гравий площадки", "#A39C90", rough=1.0)


def in_compound(x, y, pad=1.0):
    return abs(x - VYSHKA_POS[0]) < FENCE[0] + pad and abs(y - VYSHKA_POS[1]) < FENCE[1] + pad


def on_access(x, y):
    """Подъезд от обочины к воротам площадки (гравий)"""
    return GATE[0] - 9 < x < GATE[1] + 1 and VYSHKA_POS[1] + FENCE[1] - 1 < y < -SHOULDER + 1


def build_ground():
    """Дальняя земля — текстура газона; вдоль маршрута — плитки zemlya_trava (на поле и на окраине за домами)"""
    hw.X0, hw.X1 = X0, X1
    spots = []
    for row in (-1, -2, -3, -4, -5, 1, 2, 3):
        s = 1 if row > 0 else -1
        y = s * (SHOULDER - 0.1 + (abs(row) - 0.5) * TILE_STEP[1])
        x = TILE_X[0] if s < 0 else X_LAST
        while x <= TILE_X[1]:
            if not (in_compound(x, y, 3.0) or on_access(x, y)):
                spots.append((x, y))
            x += TILE_STEP[0]
    hw.TILE_ROWS, hw.TILE_X = [], (0, -1)  # дальнюю землю берём с трассы, плитки ставим сами
    hw.build_ground()
    first = None
    for n, (x, y) in enumerate(spots):
        name, rz = f"zemlya_{n}", random.choice((0, 1, 2, 3)) * math.pi / 2
        if first is None:
            first = city.place_model(hw.ZEMLYA_GLB, name, (x, y), rz, base_z=0, solid=False)
            root0 = first[0].parent
            root0.location.z = 0
            continue
        r = root0.copy()
        r.name = name
        r.location = (x, y, 0)
        r.rotation_euler.z = rz
        bpy.context.collection.objects.link(r)
        for o in first:
            c = o.copy()
            c.parent = r
            bpy.context.collection.objects.link(c)
    print("плиток газона:", len(spots))


def place_copies(path, rows, prefix):
    """Копии модели path (меш и текстуры общие): rows — (x, y, rz, base_z); каждая — препятствие wall_*"""
    first = None
    for i, (x, y, rz, z) in enumerate(rows):
        name = f"{prefix}_{i}"
        if first is None:
            first = city.place_model(path, name, (x, y), rz, base_z=z, smooth=True)
            root0, z0 = first[0].parent, first[0].parent.location.z - z
            continue
        r = root0.copy()
        r.name = name
        r.location = (x, y, z0 + z)
        r.rotation_euler.z = rz
        bpy.context.collection.objects.link(r)
        for o in first:
            c = o.copy()
            c.parent = r
            bpy.context.collection.objects.link(c)


def build_houses():
    for kind, path in (("usadba", USADBA_GLB), ("odin", ODIN_GLB)):
        d, z = HOUSE_DEPTH[kind], -HOUSE_SINK[kind]
        rows = [(x, YARD_Y + d / 2, 0, z) for k, x in HOUSES if k == kind]           # крыльцо (−Y модели) к дороге
        rows += [(x, -YARD_Y - d / 2, math.pi, z) for k, x in HOUSES_FAR if k == kind]
        place_copies(path, rows, f"wall_dom_{kind}")


def mesh(mb, a, ln, rz, cell=0.25, z0=0.1, z1=FENCE_H - 0.05):
    """Сетка-рабица полотном длины ln от точки a под углом rz: тонкие прутья по вертикали и горизонтали — сквозь видно"""
    ux, uy = math.cos(rz), math.sin(rz)
    n = max(1, round(ln / cell))
    for k in range(n + 1):
        t = ln * k / n
        mb.box((a[0] + ux * t, a[1] + uy * t, (z0 + z1) / 2), (0.012, 0.012, z1 - z0), M["fence"], rz=rz)
    m = max(1, round((z1 - z0) / cell))
    for k in range(m + 1):
        mb.box((a[0] + ux * ln / 2, a[1] + uy * ln / 2, z0 + (z1 - z0) * k / m), (ln, 0.012, 0.012), M["fence"], rz=rz)


def build_compound():
    """Площадка вышки: гравий, ограда из сетки на стойках (каждая сторона — отдельное препятствие), ворота открыты"""
    cx, cy = VYSHKA_POS
    fx, fy = FENCE
    pad = MB("vyshka_pad")
    pad.span(cx - fx, cy - fy, 0.0, cx + fx, cy + fy, 0.05, M["pad"])
    # подъезд от обочины к воротам и площадка под фургон
    pad.span(GATE[0] - 9, cy + fy, 0.0, GATE[1] + 1, -SHOULDER + 0.3, 0.035, M["gravel"])
    pad.build()

    def side(name, a, b):
        mb = MB(name)
        d = (b[0] - a[0], b[1] - a[1])
        ln = math.hypot(*d)
        n = max(1, round(ln / 2.5))
        for k in range(n + 1):
            p = (a[0] + d[0] * k / n, a[1] + d[1] * k / n)
            mb.box((*p, FENCE_H / 2), (0.07, 0.07, FENCE_H), M["fence_post"])
        c = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        rz = math.atan2(d[1], d[0])
        mesh(mb, a, ln, rz)
        mb.box((*c, FENCE_H - 0.02), (ln, 0.05, 0.05), M["fence_post"], rz=rz)          # верхняя труба
        mb.build()

    x0, x1, y0, y1 = cx - fx, cx + fx, cy - fy, cy + fy
    side("wall_fence_back", (x0, y0), (x1, y0))
    side("wall_fence_left", (x0, y0), (x0, y1))
    side("wall_fence_right", (x1, y0), (x1, y1))
    side("wall_fence_front_l", (x0, y1), (GATE[0], y1))
    side("wall_fence_front_r", (GATE[1], y1), (x1, y1))
    # створки ворот распахнуты наружу, к дороге
    w = (GATE[1] - GATE[0]) / 2
    for i, (hinge, sgn) in enumerate(((GATE[0], 1), (GATE[1], -1))):
        d = (sgn * math.cos(math.radians(70)), math.sin(math.radians(70)))
        rz = math.atan2(d[1], d[0])
        mb = MB(f"wall_gate_{i}")
        c = (hinge + d[0] * w / 2, y1 + d[1] * w / 2)
        for z in (0.1, FENCE_H - 0.05):  # рама створки
            mb.box((*c, z), (w, 0.04, 0.04), M["fence_post"], rz=rz)
        mb.box((hinge + d[0] * w, y1 + d[1] * w, FENCE_H / 2), (0.04, 0.04, FENCE_H - 0.1), M["fence_post"], rz=rz)
        mesh(mb, (hinge, y1), w, rz)
        mb.build()

    city.place_model(VYSHKA_GLB, "wall_vyshka", VYSHKA_POS, 0, base_z=0.05, smooth=True)


def build_trees():
    trees, kusty = [], []
    x = X0
    while x < X1:  # за домами (+Y) — сады и деревья за участками; на окраине — лесополоса
        x += random.uniform(4, 9)
        y = random.uniform(26, 40) if x < X_LAST else random.uniform(24, 34)
        trees.append((random.choice(("tree_bereza", "tree_topol", "tree_bereza", "tree_el")), x, y, 0.0,
                      random.uniform(0.8, 1.2), random.uniform(0, 2 * math.pi), None))
        if random.random() < 0.5:
            trees.append((random.choice(("tree_el", "tree_bereza")), x + random.uniform(-3, 3), y + random.uniform(8, 16),
                          0.0, random.uniform(0.9, 1.3), random.uniform(0, 2 * math.pi), None))
    x = X0
    while x < X1:  # −Y: за домами и за полем — лесополоса дальше вышки
        x += random.uniform(5, 10)
        near = 30 if x < -50 else 36
        y = -random.uniform(near, near + 10)
        trees.append((random.choice(("tree_bereza", "tree_el", "tree_el", "tree_topol")), x, y, 0.0,
                      random.uniform(0.85, 1.2), random.uniform(0, 2 * math.pi), None))
        if random.random() < 0.6:
            trees.append((random.choice(("tree_el", "tree_bereza")), x + random.uniform(-3, 3), y - random.uniform(8, 14),
                          0.0, random.uniform(0.9, 1.3), random.uniform(0, 2 * math.pi), None))
        if random.random() < 0.4 and x > -50:
            kusty.append((random.choice(("kusty_para", "kust_na_podlozhke")), x, y + random.uniform(4, 7), -0.15, 1.0,
                          random.uniform(0, 2 * math.pi), None))
    # редкие кусты и деревья в поле у дороги, мимо площадки вышки
    for x in range(-45, 95, 14):
        y = -random.uniform(10, 26)
        if not (in_compound(x, y, 4.0) or on_access(x, y)):
            kusty.append((random.choice(("kusty_para", "kust_na_podlozhke")), x + random.uniform(-3, 3), y, -0.15, 1.0,
                          random.uniform(0, 2 * math.pi), None))
    for x in range(X_LAST + 8, 100, 18):  # на окраине за дорогой (+Y)
        kusty.append(("kusty_para", x + random.uniform(-3, 3), random.uniform(10, 18), -0.15, 1.0,
                      random.uniform(0, 2 * math.pi), None))
    city.clone_parts(city.DEREVYA_GLB, trees)
    kusty = [k for k in kusty if not (abs(k[1] - NIVA_POS[0]) < 5 and abs(k[2] - NIVA_POS[1]) < 4)]  # не под «Нивой»
    city.clone_parts(city.KUSTY_GLB, kusty)


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    materials()
    build_ground()
    hw.build_road()
    build_houses()
    build_compound()
    build_trees()
    city.place_model(hw.VAN_GLB, "wall_van", VAN_POS, math.pi, smooth=True)  # rz = π — мордой на +X
    city.place_model(NIVA_GLB, "wall_niva", NIVA_POS, math.pi + 0.08, smooth=True)

    empty("spawn_A", (-40.0, -SHOULDER + 0.6, 0))  # на обочине в деревне, впереди — окраина и вышка
    empty("goal_B", (VAN_POS[0] - 5.0, -SHOULDER - 1.0, 0))  # у подъезда к площадке, за фургоном
    empty("walk_min", (-90, -32, 0))
    empty("walk_max", (100, YARD_Y - 0.5, 0))

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_extras=True, export_apply=True)


build()
print("Готово:", OUT_GLB, OUT_BLEND)
