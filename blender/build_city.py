"""
Локация 2 «Город»: улица днём, вид сбоку с горизонтальной прокруткой (src/city/engine.ts).

Запуск (из корня проекта):
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/build_city.py

Результат:
    public/models/city.glb   — сцена для игры (http://localhost:5173/city)
    blender/city_base.blend  — исходник; скрипт перезаписывает его при каждом запуске

Оси Blender: X — вдоль улицы, Y — вглубь от камеры, Z — вверх. Слои по глубине дают параллакс:
передний план (газон, тротуар, дорога) → здания-организации → дома среднего плана → силуэты высоток.

Имена, которые читает игра:
    bld_<id>        — здание-организация (кликабельно): houses, clinic, fire, business, construction, factory
    spot_<id>       — где над зданием висит метка
    win_<id>_<k>    — окна, которые мигают
    crane_slew      — поворотная часть крана (вращается вокруг своего начала координат), crane_trolley — тележка
    smoke_src       — устье заводской трубы
    car_tpl_<вид>   — образцы машин (игра клонирует их на полосы); материал «Кузов авто» перекрашивается
    ped_tpl_<n>     — образцы пешеходов; дети <...>_leg_L/R, <...>_arm_L/R качаются при ходьбе
    lane_near / lane_far / walk_near / walk_far — оси полос и тротуаров (по Y)
    cam_min / cam_max — пределы прокрутки камеры по X
"""

import math
import os
import random
import sys

import bpy
from mathutils import Vector as V

sys.path.insert(0, os.path.dirname(__file__))
from lowpoly import M, MB, base_materials, empty, gable, mat, picket_fence, principled, rad, srgb, tree, window  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_GLB = os.path.join(ROOT, "public", "models", "city.glb")
OUT_BLEND = os.path.join(ROOT, "blender", "city_base.blend")

random.seed(11)

X0, X1 = -60, 240          # улица по X
CURB_NEAR, CURB_FAR = -3.0, 5.0   # край проезжей части
WALK_NEAR = (-7.0, -3.0)   # ближний тротуар
WALK_FAR = (5.0, 8.6)      # дальний тротуар
LANE_NEAR, LANE_FAR = -1.0, 3.0   # оси полос: ближняя едет по +X, дальняя по −X
TEMPLATES_X = -400         # образцы машин и пешеходов стоят далеко за кадром


def glow(m, hex_color, strength=1.0):
    """Лёгкое собственное свечение: низ перекрытий иначе уходит в почти чёрный"""
    b = principled(m.node_tree)
    b.inputs["Emission Color"].default_value = (*srgb(hex_color), 1)
    b.inputs["Emission Strength"].default_value = strength
    return m


def city_materials():
    base_materials()
    M.update(
        lawn=mat("Газон", "#7EA650", rough=1.0),
        ground=mat("Земля города", "#9DB27A", rough=1.0),
        asphalt=mat("Асфальт", "#575C64", rough=0.95),
        marking=mat("Разметка", "#F1F1EC", rough=0.8),
        curb=mat("Бордюр", "#B9B9B1", rough=0.9),
        paving=mat("Плитка", "#CFCBC0", rough=0.95),
        paving_dark=mat("Плитка тёмная", "#B8B3A6", rough=0.95),
        metal=mat("Металл", "#8E959C", rough=0.4, metal=0.7),
        dark=mat("Тёмный металл", "#3A3F45", rough=0.6, metal=0.3),
        lamp=mat("Плафон", "#FFF4D6", rough=0.3),
        white=mat("Белый", "#F4F5F2", rough=0.7),
        red=mat("Красный", "#D0312D", rough=0.45),
        blink=mat("Окно бликует", "#2D4B6E", rough=0.1),
        stop_glass=mat("Стекло остановки", "#A8CBE0", rough=0.1),
        # Поликлиника
        clinic_band=mat("Поликлиника полосы", "#7FB8D8", rough=0.7),
        # Пожарная часть
        fire_brick=mat("Кирпич красный", "#B04A32", rough=0.9),
        gate_red=mat("Ворота пожарные", "#C8302B", rough=0.5),
        # Бизнес-центр
        tower_glass=mat("Стекло высотки", "#5E95BF", rough=0.12, metal=0.35),
        tower_glass_dark=mat("Стекло высотки тёмное", "#3E6F98", rough=0.12, metal=0.35),
        mullion=mat("Импосты", "#DDE3EA", rough=0.35, metal=0.4),
        # Стройка
        crane=mat("Кран", "#F2B705", rough=0.5, metal=0.2),
        hoarding=mat("Ограждение стройки", "#2F6FB8", rough=0.7),
        scaffold=mat("Леса", "#C9CDD2", rough=0.4, metal=0.6),
        boards=mat("Доски", "#B5874E", rough=0.9),
        rebar=mat("Арматура", "#6B5246", rough=0.6, metal=0.5),
        frame=glow(mat("Бетон каркаса", "#B4B8BD", rough=0.9), "#4A4E53"),
        counterweight=mat("Противовес", "#8F949A", rough=0.9),
        # Завод
        factory_wall=mat("Стена цеха", "#C9C1B0", rough=0.9),
        cladding=mat("Профлист", "#8FA6B8", rough=0.6, metal=0.3),
        factory_roof=mat("Кровля цеха", "#7C8792", rough=0.7, metal=0.3),
        chimney_red=mat("Труба красная", "#B83A2E", rough=0.8),
        chimney_white=mat("Труба белая", "#F1EFEA", rough=0.8),
        tank=mat("Резервуар", "#D9DCDF", rough=0.4, metal=0.5),
        hazard=mat("Сигнальная жёлтая", "#F2C230", rough=0.6),
        # Город на фоне
        block_a=mat("Дом панельный бежевый", "#E6DCC8", rough=0.9),
        block_b=mat("Дом панельный голубой", "#D4E2EC", rough=0.9),
        block_c=mat("Дом панельный розовый", "#EBD3C4", rough=0.9),
        sky_a=mat("Силуэт высоток", "#A9BBCD", rough=1.0),
        sky_b=mat("Силуэт высоток тёмный", "#97ABC0", rough=1.0),
        sky_c=mat("Силуэт высоток светлый", "#B9C8D6", rough=1.0),
        # Транспорт и люди
        car_body=mat("Кузов авто", "#D64541", rough=0.35, metal=0.3),
        car_glass=mat("Стекло авто", "#24303D", rough=0.1),
        tire=mat("Шины", "#1E1F21", rough=0.9),
        headlight=mat("Фары", "#F3F1E4", rough=0.2),
        taillight=mat("Задние фонари", "#C0262C", rough=0.3),
        bus=mat("Автобус", "#F2B705", rough=0.4, metal=0.2),
        truck_box=mat("Фургон грузовика", "#EDEFF1", rough=0.6),
        skin=mat("Кожа", "#E9C3A0", rough=0.8),
        hair=mat("Волосы", "#3B2A20", rough=0.9),
    )


# ---------- Земля и улица ----------

def build_street():
    g = MB("ground")
    g.span(X0 - 200, -80, -0.05, X1 + 260, 700, -0.01, M["ground"])
    g.span(X0, -40, -0.01, X1, WALK_NEAR[0], 0.0, M["lawn"])
    g.build()

    s = MB("street")
    s.span(X0, CURB_NEAR, 0.0, X1, CURB_FAR, 0.02, M["asphalt"])
    for y0, y1 in (WALK_NEAR, WALK_FAR):
        s.span(X0, y0, 0.0, X1, y1, 0.12, M["paving"])
        for x in range(X0, X1, 3):  # швы плитки
            s.span(x, y0, 0.12, x + 0.05, y1, 0.125, M["paving_dark"])
    for y in (CURB_NEAR, CURB_FAR):  # бордюры
        s.span(X0, y - 0.15, 0.0, X1, y + 0.15, 0.16, M["curb"])
    for x in range(X0, X1, 6):  # прерывистая осевая
        s.span(x, 0.92, 0.02, x + 3, 1.08, 0.03, M["marking"])
    for y in (CURB_NEAR + 0.35, CURB_FAR - 0.35):  # краевые линии
        s.span(X0, y - 0.06, 0.02, X1, y + 0.06, 0.03, M["marking"])
    for k in range(8):  # «зебра» у поликлиники
        y = CURB_NEAR + 0.6 + k * 1.0
        s.span(28, y - 0.25, 0.02, 32, y + 0.25, 0.035, M["marking"])
    s.build()

    empty("lane_near", (0, LANE_NEAR, 0))
    empty("lane_far", (0, LANE_FAR, 0))
    empty("walk_near", (0, -4.6, 0.12))
    empty("walk_far", (0, 6.0, 0.12))


def street_furniture():
    mb = MB("street_furniture")
    trunks, crowns = MB("street_tree_trunks"), MB("street_tree_crowns")
    for k, x in enumerate(range(X0 + 4, X1, 16)):
        for y, arm in ((CURB_NEAR - 0.5, 1), (CURB_FAR + 0.5, -1)):  # фонари вдоль обоих тротуаров
            xx = x + (8 if arm < 0 else 0)
            mb.cyl((xx, y, 0.1), (xx, y, 6.2), 0.09, 0.06, M["dark"], n=8)
            mb.beam((xx, y, 6.1), (xx, y + arm * 1.2, 6.3), 0.06, 0.06, M["dark"])
            mb.box((xx, y + arm * 1.3, 6.2), (0.5, 0.3, 0.14), M["dark"])
            mb.box((xx, y + arm * 1.3, 6.11), (0.4, 0.22, 0.04), M["lamp"])
        # Деревья в кадках и живая изгородь на ближнем тротуаре
        tx = x + 8
        mb.span(tx - 0.8, -6.9, 0.12, tx + 0.8, -5.3, 0.55, M["curb"])
        tree(trunks, crowns, "birch" if k % 3 == 1 else "tree", tx, -6.1, s=0.85, z=0.55)
        mb.box((x + 2, -7.6, 0.45), (5.0, 0.9, 0.9), M["leaf"])
    for bx in (12, 58, 96, 150):  # скамейки
        mb.box((bx, -6.4, 0.45), (1.8, 0.45, 0.06), M["wood"])
        mb.box((bx, -6.62, 0.75), (1.8, 0.06, 0.4), M["wood"])
        for s in (-1, 1):
            mb.box((bx + s * 0.75, -6.45, 0.3), (0.08, 0.4, 0.4), M["dark"])
    # Остановка у поликлиники
    sx = 40
    mb.span(sx - 2.5, -6.9, 2.6, sx + 2.5, -5.3, 2.75, M["white"])
    mb.span(sx - 2.4, -6.85, 0.3, sx + 2.4, -6.8, 2.5, M["stop_glass"])
    for s in (-1, 1):
        mb.box((sx + s * 2.4, -6.85, 1.4), (0.08, 0.08, 2.6), M["metal"])
    mb.box((sx, -6.55, 0.5), (3.0, 0.4, 0.06), M["wood"])
    mb.box((sx + 2.9, -5.6, 2.8), (0.05, 0.6, 0.6), M["hoarding"])
    mb.cyl((sx + 2.9, -5.6, 0.1), (sx + 2.9, -5.6, 2.5), 0.04, 0.04, M["metal"], n=6)
    # Светофор у «зебры»
    for y, f in ((CURB_NEAR - 0.4, 1), (CURB_FAR + 0.4, -1)):
        mb.cyl((32.6, y, 0.1), (32.6, y, 3.2), 0.07, 0.07, M["dark"], n=6)
        mb.box((32.6, y, 3.5), (0.3, 0.3, 0.9), M["dark"])
        for z, c in ((3.8, "red"), (3.5, "hazard"), (3.2, "leaf_light")):
            mb.cyl((32.6, y - f * 0.16, z), (32.6, y - f * 0.2, z), 0.1, 0.1, M[c], n=8)
    mb.build()
    trunks.build()
    crowns.build()


def blink(name, parent, c, w, h, depth_axis="y"):
    """Отдельное стекло поверх окна — в игре оно поблёскивает"""
    mb = MB(name)
    size = (w, 0.03, h) if depth_axis == "y" else (0.03, w, h)
    mb.box(c, size, M["blink"])
    mb.build(parent=parent)


# ---------- 1. Жилые дома (как в сцене 1) ----------

def city_house(mb, x, yf, floors, roof, parent, tag, blink_count):
    """Дом из сцены 1, фасадом к улице; floors — 1 или 2 этажа"""
    w, d = 7.6, 6.0
    x0, x1, y0, y1 = x - w / 2, x + w / 2, yf, yf + d
    top = 3.0 if floors == 1 else 5.8
    mb.span(x0 - 0.12, y0 - 0.12, 0, x1 + 0.12, y1 + 0.12, 0.5, M["plinth"])
    mb.span(x0, y0, 0.4, x1, y1, top, M["plaster"])
    eave, ridge, over = top - 0.25, top + 1.75, 0.6
    for ye in (y0 - over, y1 + over):
        mb.beam((x, ye, eave), (x, (y0 + y1) / 2, ridge), w + 2 * over, 0.12, roof, side=(1, 0, 0))
    mb.beam((x0 - over, (y0 + y1) / 2, ridge + 0.04), (x1 + over, (y0 + y1) / 2, ridge + 0.04), 0.28, 0.16, roof)
    for xe, xo, s in ((x0, x0 + 0.15, -1), (x1, x1 - 0.15, 1)):
        gable(mb, xe - s * 0.02, xo, y0, y1, top, ridge - 0.12, M["gable"])
    rows = [1.75] if floors == 1 else [1.75, 4.45]
    panes = []
    for z in rows:
        for wx in (x - 2.6, x - 0.9, x + 2.6) if z == 1.75 else (x - 2.4, x, x + 2.4):
            window(mb, (wx, y0), (0, -1, 0), (1, 0, 0), z)
            panes.append((wx, z))
    dx = x + 0.9
    mb.box((dx, y0 - 0.03, 1.5), (1.0, 0.06, 2.0), M["door"])
    mb.span(dx - 0.95, y0 - 1.3, 0, dx + 0.95, y0, 0.45, M["concrete"])
    mb.beam((dx, y0, 2.68), (dx, y0 - 1.3, 2.5), 2.0, 0.08, roof, side=(1, 0, 0))
    mb.box((x - 1.5, y0 + 3.2, ridge + 0.2), (0.5, 0.5, 1.6), M["brick"])
    random.shuffle(panes)
    for k, (wx, z) in enumerate(panes[:blink_count]):
        blink(f"win_{tag}_{x:.0f}_{k}", parent, (wx, y0 - 0.06, z), 0.9, 1.1)


def build_houses():
    p = empty("bld_houses")
    mb = MB("houses")
    trunks, crowns = MB("houses_tree_trunks"), MB("houses_tree_crowns")
    for x, floors, roof in ((5, 1, M["roof"]), (15, 2, M["roof_red"]), (25, 1, M["roof_blue"])):
        city_house(mb, x, 12.5, floors, roof, p, "houses", 2)
        picket_fence(mb, (x - 4.8, 9.4), (x + 0.3, 9.4))
        picket_fence(mb, (x + 1.5, 9.4), (x + 4.8, 9.4))
        mb.span(x - 4.8, 8.6, 0, x + 4.8, 12.5, 0.03, M["lawn"])
        mb.span(x + 0.3, 9.2, 0, x + 1.5, 12.5, 0.05, M["paving_dark"])
        tree(trunks, crowns, "apple", x - 3.0, 10.9, s=0.8)
    mb.build(parent=p)
    trunks.build(parent=p)
    crowns.build(parent=p)
    empty("spot_houses", (15, 10.5, 10.5))


# ---------- 2. Поликлиника ----------

def build_clinic():
    p = empty("bld_clinic")
    mb = MB("clinic")
    x0, x1, y0, y1 = 33, 53, 11, 23
    floors, fh = 3, 3.4
    top = floors * fh
    mb.span(x0 - 0.2, y0 - 0.2, 0, x1 + 0.2, y1 + 0.2, 0.6, M["plinth"])
    mb.span(x0, y0, 0.5, x1, y1, top, M["white"])
    mb.span(x0 - 0.15, y0 - 0.15, top, x1 + 0.15, y1 + 0.15, top + 0.45, M["clinic_band"])
    for f in range(1, floors):
        mb.span(x0 - 0.05, y0 - 0.06, f * fh - 0.15, x1 + 0.05, y0, f * fh + 0.1, M["clinic_band"])
    panes = []
    for f in range(floors):
        zc = f * fh + 1.9
        for k in range(8):
            wx = x0 + 1.5 + k * 2.43
            if f == 0 and 40.5 < wx < 45.5:
                continue  # вход
            mb.box((wx, y0 - 0.03, zc), (1.5, 0.06, 1.5), M["glass"])
            mb.box((wx, y0 - 0.06, zc - 0.8), (1.7, 0.12, 0.08), M["white"])
            mb.box((wx, y0 - 0.05, zc), (0.06, 0.04, 1.5), M["white"])
            panes.append((wx, zc))
    # Вход: стеклянные двери, козырёк, пандус
    mb.box((43, y0 - 0.03, 1.7), (3.2, 0.06, 2.4), M["blink"])
    mb.box((43, y0 - 0.05, 1.7), (0.08, 0.06, 2.4), M["metal"])
    mb.span(40.5, y0 - 2.4, 3.1, 45.5, y0, 3.35, M["white"])
    for s in (-1, 1):
        mb.cyl((43 + s * 2.2, y0 - 2.2, 0.1), (43 + s * 2.2, y0 - 2.2, 3.1), 0.1, 0.1, M["metal"], n=8)
    mb.span(40.5, y0 - 2.4, 0, 45.5, y0, 0.25, M["paving_dark"])
    mb.span(45.5, y0 - 1.4, 0, 49.5, y0, 0.18, M["paving_dark"])
    # Знак: белый квадрат с красным крестом на фасаде
    mb.span(41.6, y0 - 0.12, 6.1, 44.4, y0 - 0.02, 8.9, M["white"])
    mb.span(42.6, y0 - 0.18, 6.4, 43.4, y0 - 0.1, 8.6, M["red"])
    mb.span(41.9, y0 - 0.18, 7.1, 44.1, y0 - 0.1, 7.9, M["red"])
    mb.build(parent=p)
    random.shuffle(panes)
    for k, (wx, z) in enumerate(panes[:4]):
        blink(f"win_clinic_{k}", p, (wx, y0 - 0.07, z), 1.4, 1.4)
    ambulance(p, (49.5, 7.9, 0))
    empty("spot_clinic", (43, 10.5, 13.6))


def ambulance(parent, pos):
    x, y, _ = pos
    mb = MB("ambulance")
    mb.span(x - 2.8, y - 1.0, 0.45, x + 1.6, y + 1.0, 2.6, M["white"])  # кузов
    mb.span(x + 1.6, y - 1.0, 0.45, x + 2.9, y + 1.0, 1.6, M["white"])  # капот
    mb.poly([(x + 1.6, y - 0.95, 1.6), (x + 2.6, y - 0.95, 1.6), (x + 1.6, y - 0.95, 2.4),
             (x + 1.6, y + 0.95, 1.6), (x + 2.6, y + 0.95, 1.6), (x + 1.6, y + 0.95, 2.4)],
            [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (0, 2, 5, 3)], M["car_glass"])
    mb.span(x - 2.81, y - 1.01, 1.0, x + 2.0, y + 1.01, 1.25, M["red"])
    mb.span(x - 1.0, y - 1.02, 1.6, x - 0.2, y - 1.0, 2.4, M["red"])
    mb.span(x - 1.3, y - 1.02, 1.85, x + 0.1, y - 1.0, 2.15, M["red"])
    mb.span(x + 0.8, y - 0.4, 2.6, x + 1.4, y + 0.4, 2.8, M["hoarding"])  # мигалка
    for wx in (x - 1.9, x + 2.0):
        for s in (-1, 1):
            mb.cyl((wx, y + s * 0.85, 0.38), (wx, y + s * 1.02, 0.38), 0.38, 0.38, M["tire"], n=12)
    mb.build(parent=parent)


# ---------- 3. Пожарная часть ----------

def build_fire_station():
    p = empty("bld_fire")
    mb = MB("fire_station")
    x0, x1, y0, y1 = 58, 73, 11, 25
    top = 8.2
    mb.span(x0, y0, 0, x1, y1, top, M["fire_brick"])
    mb.span(x0 - 0.15, y0 - 0.15, top, x1 + 0.15, y1 + 0.15, top + 0.5, M["white"])
    mb.span(x0 - 0.05, y0 - 0.08, 4.6, x1 + 0.05, y0, 5.0, M["white"])
    for gx in (60.8, 65.5, 70.2):  # трое ворот: белая рама, красные секции
        mb.span(gx - 1.9, y0 - 0.12, 0, gx + 1.9, y0 - 0.02, 4.4, M["white"])
        mb.span(gx - 1.65, y0 - 0.16, 0.05, gx + 1.65, y0 - 0.08, 4.15, M["gate_red"])
        for k in range(1, 7):
            mb.span(gx - 1.65, y0 - 0.19, k * 0.6, gx + 1.65, y0 - 0.15, k * 0.6 + 0.05, M["white"])
        mb.span(gx - 1.2, y0 - 0.19, 2.6, gx + 1.2, y0 - 0.17, 3.1, M["glass"])
    panes = []
    for wx in (59.8, 62.3, 64.8, 67.3, 69.8, 72.0):
        mb.box((wx, y0 - 0.03, 6.6), (1.3, 0.06, 1.5), M["glass"])
        mb.box((wx, y0 - 0.06, 5.75), (1.5, 0.12, 0.08), M["white"])
        panes.append((wx, 6.6))
    # Табличка «01» не пишем текстом — красный щит с белой полосой над воротами
    mb.span(62.5, y0 - 0.14, 7.55, 68.5, y0 - 0.04, 8.15, M["gate_red"])
    mb.span(62.7, y0 - 0.16, 7.8, 68.3, y0 - 0.14, 7.9, M["white"])
    # Рукавосушильная башня
    tx0, tx1, ty0, ty1, th = 74, 78, 13, 17, 19
    mb.span(tx0, ty0, 0, tx1, ty1, th, M["fire_brick"])
    for z in range(3, th, 4):
        mb.box(((tx0 + tx1) / 2, ty0 - 0.03, z + 1), (1.0, 0.06, 1.3), M["glass"])
        mb.span(tx0 - 0.05, ty0 - 0.06, z - 0.2, tx1 + 0.05, ty0, z, M["white"])
    for s in (-1, 1):
        for t in (-1, 1):
            mb.box(((tx0 + tx1) / 2 + s * 1.85, (ty0 + ty1) / 2 + t * 1.85, th + 1.0), (0.25, 0.25, 2.0), M["white"])
    mb.span(tx0 - 0.4, ty0 - 0.4, th + 2.0, tx1 + 0.4, ty1 + 0.4, th + 2.3, M["gate_red"])
    mb.cyl(((tx0 + tx1) / 2, (ty0 + ty1) / 2, th + 2.3), ((tx0 + tx1) / 2, (ty0 + ty1) / 2, th + 3.6), 2.6, 0, M["gate_red"], n=4)
    mb.cyl(((tx0 + tx1) / 2, (ty0 + ty1) / 2, th + 3.5), ((tx0 + tx1) / 2, (ty0 + ty1) / 2, th + 6.5), 0.04, 0.04, M["metal"], n=5)
    mb.box(((tx0 + tx1) / 2 + 0.45, (ty0 + ty1) / 2, th + 6.1), (0.9, 0.03, 0.55), M["red"])
    mb.span(x0, 8.6, 0, x1, y0, 0.05, M["paving_dark"])  # площадка перед воротами
    mb.build(parent=p)
    for k, (wx, z) in enumerate(panes[1::2]):
        blink(f"win_fire_{k}", p, (wx, y0 - 0.07, z), 1.2, 1.4)
    fire_truck(p, (66.0, 9.3, 0))
    empty("spot_fire", (66, 10.5, 12.5))


def fire_truck(parent, pos):
    x, y, _ = pos
    mb = MB("fire_truck")
    mb.span(x - 4.0, y - 1.15, 0.6, x + 1.6, y + 1.15, 2.9, M["red"])          # кузов с отсеками
    mb.span(x + 1.6, y - 1.15, 0.6, x + 3.6, y + 1.15, 2.8, M["red"])          # кабина
    mb.span(x + 2.4, y - 1.17, 1.8, x + 3.5, y + 1.17, 2.6, M["car_glass"])
    mb.span(x + 3.6, y - 1.1, 0.5, x + 3.7, y + 1.1, 0.9, M["metal"])
    mb.span(x - 4.01, y - 1.16, 1.4, x + 3.61, y + 1.16, 1.55, M["white"])
    for k in range(4):  # шторки отсеков
        mb.span(x - 3.7 + k * 1.3, y - 1.17, 1.65, x - 2.6 + k * 1.3, y - 1.15, 2.7, M["metal"])
    mb.beam((x - 3.8, y, 3.1), (x + 1.4, y, 3.4), 0.6, 0.25, M["metal"])  # лестница
    for k in range(9):
        mb.box((x - 3.5 + k * 0.6, y, 3.35), (0.05, 0.6, 0.05), M["white"])
    mb.span(x + 2.0, y - 0.45, 2.8, x + 2.5, y + 0.45, 3.0, M["hoarding"])
    for wx in (x - 2.8, x - 1.4, x + 2.6):
        for s in (-1, 1):
            mb.cyl((wx, y + s * 0.95, 0.5), (wx, y + s * 1.2, 0.5), 0.5, 0.5, M["tire"], n=12)
    mb.build(parent=parent)


# ---------- 4. Бизнес-центр ----------

def build_business():
    p = empty("bld_business")
    mb = MB("business_center")
    x0, x1, y0, y1, h = 86, 104, 13, 29, 46
    mb.span(x0, y0, 0, x1, y1, h, M["tower_glass"])
    for k in range(13):  # вертикальные импосты на фасаде и боках
        x = x0 + k * 1.5
        mb.span(x - 0.07, y0 - 0.25, 5.2, x + 0.07, y0, h, M["mullion"])
    for k in range(11):
        y = y0 + k * 1.6
        for xs in (x0, x1):
            mb.span(xs - 0.2, y - 0.07, 5.2, xs + 0.2, y + 0.07, h, M["mullion"])
    for z in range(8, h, 4):  # межэтажные пояса
        mb.span(x0 - 0.05, y0 - 0.12, z - 0.12, x1 + 0.05, y0, z + 0.12, M["mullion"])
    mb.span(x0 + 1.5, y0 + 1.5, h, x1 - 1.5, y1 - 1.5, h + 4, M["tower_glass_dark"])  # корона
    mb.span(x0 + 1.3, y0 + 1.3, h + 4, x1 - 1.3, y1 - 1.3, h + 4.4, M["mullion"])
    mb.cyl((95, 21, h + 4.4), (95, 21, h + 12), 0.15, 0.05, M["metal"], n=6)
    # Подиум с вестибюлем и козырьком
    mb.span(x0 - 2, y0 - 1, 0, x1 + 2, y0 + 6, 5, M["tower_glass_dark"])
    mb.span(x0 - 2.3, y0 - 3.0, 5, x1 + 2.3, y0 + 6.2, 5.5, M["mullion"])
    for x in (89, 95, 101):
        mb.cyl((x, y0 - 2.6, 0.1), (x, y0 - 2.6, 5), 0.15, 0.15, M["metal"], n=8)
    mb.cyl((95, y0 - 1.2, 0.1), (95, y0 - 1.2, 3.0), 1.3, 1.3, M["blink"], n=12)  # вращающаяся дверь
    mb.span(x0 - 4, 8.6, 0, x1 + 4, y0, 0.06, M["paving_dark"])  # площадь
    flags = (M["hoarding"], M["white"], M["clinic_band"])
    for x, fl in zip((84, 86.5, 89), flags):  # флагштоки
        mb.cyl((x, 9.6, 0), (x, 9.6, 9.0), 0.07, 0.05, M["metal"], n=6)
        mb.span(x + 0.05, 9.58, 7.3, x + 2.0, 9.62, 8.8, fl)
    for x in (98, 102.5):  # клумбы
        mb.span(x - 1.2, 9.4, 0, x + 1.2, 11.2, 0.5, M["curb"])
        mb.blob((x, 10.3, 0.7), 0.9, M["leaf_light"], scale=(1.2, 0.9, 0.5), bump=0.2)
    mb.build(parent=p)
    for k in range(10):  # бликующие панели на фасаде
        x = x0 + 0.75 + random.randrange(12) * 1.5
        z = 7 + random.randrange(9) * 4
        blink(f"win_business_{k}", p, (x, y0 - 0.06, z), 1.3, 3.5)
    empty("spot_business", (95, 10.5, 30))


# ---------- 5. Стройплощадка с башенным краном ----------

def build_construction():
    p = empty("bld_construction")
    mb = MB("construction_site")
    # Ограждение из синих щитов с белой полосой, ворота открыты
    for xa, xb in ((108, 113), (118, 140)):
        mb.span(xa, 9.35, 0, xb, 9.45, 2.3, M["hoarding"])
        mb.span(xa, 9.3, 1.9, xb, 9.32, 2.1, M["white"])
        for x in range(xa, xb + 1, 3):
            mb.box((x, 9.4, 1.2), (0.12, 0.2, 2.4), M["metal"])
    for x, rot in ((113, -60), (118, 60)):
        a = rad(rot)
        hinge = V((x, 9.4, 0))
        tip = hinge + V((math.cos(rad(0 if rot < 0 else 180) + a) * 2.4, math.sin(rad(0 if rot < 0 else 180) + a) * 2.4, 0))
        mb.beam(hinge + V((0, 0, 1.15)), tip + V((0, 0, 1.15)), 2.3, 0.08, M["hoarding"], side=(0, 0, 1))
    mb.span(108, 8.6, 0, 140, 34, 0.04, M["paving_dark"])  # площадка — укатанный грунт/щебень
    mb.box((112, 9.25, 2.9), (2.6, 0.06, 1.2), M["white"])  # паспорт объекта у ворот

    # Каркас здания: плиты перекрытий, колонны; внизу кирпичное заполнение, сверху открыто
    x0, x1, y0, y1, fh = 116, 132, 14, 26, 3.2
    for f in range(8):
        z = f * fh
        mb.span(x0, y0, z, x1, y1, z + 0.25, M["frame"])  # на верхнем перекрытии колонны только слева — этаж строится
        for cx in (x0 + 0.2, (x0 + x1) / 2, x1 - 0.2, x0 + 5.3, x1 - 5.3):
            for cy in (y0 + 0.2, (y0 + y1) / 2, y1 - 0.2):
                if f < 7 or (cx < (x0 + x1) / 2 + 0.1):
                    mb.span(cx - 0.2, cy - 0.2, z + 0.25, cx + 0.2, cy + 0.2, z + fh, M["frame"])
        if f < 3:  # кирпичная кладка с проёмами окон на фасаде
            for k in range(4):
                xa = x0 + 0.4 + k * 3.9
                mb.span(xa, y0 - 0.05, z + 0.25, xa + 0.8, y0 + 0.25, z + fh, M["brick"])
                mb.span(xa + 0.8, y0 - 0.05, z + 0.25, xa + 3.5, y0 + 0.25, z + 0.95, M["brick"])
                mb.span(xa + 0.8, y0 - 0.05, z + 2.55, xa + 3.5, y0 + 0.25, z + fh, M["brick"])
    for k in range(10):
        x = x0 + 9 + k * 0.7
        mb.box((x, y0 + 0.3, 22.4 + 0.7), (0.04, 0.04, 1.4), M["rebar"])
    # Строительные леса на фасаде (4 яруса)
    for k in range(9):
        x = x0 + k * 2.0
        for yy in (y0 - 1.3, y0 - 0.4):
            mb.box((x, yy, 6.6), (0.06, 0.06, 13.2), M["scaffold"])
    for lv in range(1, 5):
        z = lv * 3.2
        mb.span(x0, y0 - 1.4, z, x1, y0 - 0.3, z + 0.06, M["boards"])
        mb.span(x0, y0 - 1.35, z + 1.0, x1, y0 - 1.29, z + 1.06, M["scaffold"])
    for k in range(8):
        x = x0 + k * 2.0
        mb.beam((x, y0 - 1.35, 0.2), (x + 2.0, y0 - 1.35, 3.2), 0.05, 0.05, M["scaffold"])
    # Бытовки и материалы
    for bx, col in ((134, M["hoarding"]), (137, M["white"])):
        mb.span(bx - 1.2, 11, 0, bx + 1.2, 14.0, 2.6, col)
        mb.box((bx, 10.98, 1.6), (0.9, 0.04, 0.8), M["glass"])
    for k in range(3):
        mb.span(110 + k * 1.4, 12, 0, 111.1 + k * 1.4, 13.1, 0.15, M["boards"])
        mb.span(110.05 + k * 1.4, 12.05, 0.15, 111.05 + k * 1.4, 13.05, 1.0, M["brick"])
    for k in range(12):
        mb.beam((110 + k * 0.08, 15, 0.1 + k * 0.03), (115.5 + k * 0.08, 15.5, 0.1), 0.04, 0.04, M["rebar"])
    mb.build(parent=p)

    build_crane(p, (136.5, 22.5))
    empty("spot_construction", (124, 10.5, 26))


def lattice(mb, a, b, w, m, n=None):
    """Решётчатая секция крана: 4 пояса и раскосы между точками a и b"""
    a, b = V(a), V(b)
    d = b - a
    length = d.length
    t = d.normalized()
    u = V((0, 0, 1)).cross(t) if abs(t.z) < 0.9 else V((1, 0, 0))
    u.normalize()
    v = t.cross(u)
    corners = [u * s * w / 2 + v * q * w / 2 for s in (-1, 1) for q in (-1, 1)]
    for c in corners:
        mb.beam(a + c, b + c, 0.12, 0.12, m)
    n = n or max(2, round(length / w))
    for k in range(n):
        p0, p1 = a + t * (length * k / n), a + t * (length * (k + 1) / n)
        for i, j in ((0, 1), (1, 3), (3, 2), (2, 0)):
            mb.beam(p0 + corners[i], p1 + corners[j], 0.06, 0.06, m)


def build_crane(parent, base):
    x, y = base
    H = 33.0  # высота опорно-поворотного устройства: стрела и груз проходят выше каркаса (25,6 м)
    mb = MB("crane_mast")
    mb.span(x - 2.2, y - 2.2, 0, x + 2.2, y + 2.2, 0.8, M["concrete"])
    lattice(mb, (x, y, 0.8), (x, y, H), 1.8, M["crane"])
    mb.build(parent=parent)

    # Поворотная часть: всё строится в мировых координатах, начало координат — в точке поворота
    pivot = V((x, y, H))
    slew = MB("crane_slew")
    slew.span(x - 1.3, y - 1.3, H, x + 1.3, y + 1.3, H + 0.8, M["crane"])
    slew.span(x - 1.2, y - 2.6, H + 0.5, x + 0.6, y - 1.0, H + 2.6, M["crane"])  # кабина крановщика
    slew.span(x - 1.25, y - 2.65, H + 1.2, x + 0.1, y - 2.6, H + 2.4, M["glass"])
    jl, cl = 30.0, 9.0
    lattice(slew, (x - 1.0, y, H + 1.4), (x - jl, y, H + 1.4), 1.2, M["crane"])   # стрела
    lattice(slew, (x + 1.0, y, H + 1.4), (x + cl, y, H + 1.4), 1.2, M["crane"])   # противовесная консоль
    for k in range(4):
        slew.span(x + cl - 3.6 + k * 0.9, y - 0.9, H + 0.2, x + cl - 2.8 + k * 0.9, y + 0.9, H + 2.0, M["counterweight"])
    lattice(slew, (x, y, H + 0.8), (x, y, H + 8.0), 1.4, M["crane"])  # оголовок
    for tip in ((x - jl * 0.7, y, H + 2.0), (x + cl, y, H + 2.0)):  # тяги
        slew.beam((x, y, H + 8.0), tip, 0.08, 0.08, M["dark"])
    slew_obj = slew.build(parent=parent, pivot=pivot)

    # Тележка с крюком и грузом — ребёнок поворотной части, в игре ездит вдоль стрелы
    tx = x - 12.0
    tr = MB("crane_trolley")
    tr.span(tx - 0.6, y - 0.7, H + 0.55, tx + 0.6, y + 0.7, H + 0.8, M["dark"])
    tr.beam((tx, y, H + 0.55), (tx, y, H - 4.4), 0.05, 0.05, M["dark"])
    tr.span(tx - 0.3, y - 0.3, H - 5.0, tx + 0.3, y + 0.3, H - 4.4, M["crane"])
    for s in (-1, 1):
        tr.beam((tx, y, H - 5.0), (tx + s * 1.0, y, H - 6.0), 0.04, 0.04, M["dark"])
    tr.span(tx - 1.2, y - 0.8, H - 7.0, tx + 1.2, y + 0.8, H - 6.0, M["boards"])
    tr.span(tx - 1.1, y - 0.7, H - 6.0, tx + 1.1, y + 0.7, H - 5.3, M["brick"])
    tr.build(parent=slew_obj, pivot=(tx, y, H + 0.7))


# ---------- 6. Завод ----------

def build_factory():
    p = empty("bld_factory")
    mb = MB("factory")
    x0, x1, y0, y1, h = 146, 170, 15, 33, 8.5
    mb.span(x0, y0, 0, x1, y1, h, M["cladding"])
    mb.span(x0 - 0.05, y0 - 0.06, 0, x1 + 0.05, y0, 1.2, M["factory_wall"])
    mb.span(x0 - 0.05, y0 - 0.08, 6.0, x1 + 0.05, y0 - 0.02, 7.3, M["glass"])  # ленточное остекление
    for k in range(13):
        x = x0 + k * 2.0
        mb.span(x - 0.08, y0 - 0.1, 6.0, x + 0.08, y0 - 0.04, 7.3, M["mullion"])
    # Шедовая кровля: зубцы с коньками вдоль Y, остекление на вертикальной грани
    teeth = 4
    for k in range(teeth):
        xa = x0 + k * (x1 - x0) / teeth
        xb = xa + (x1 - x0) / teeth
        hb = h + 2.6
        for yy, sgn in ((y0, -1), (y1, 1)):
            mb.poly([(xa, yy, h), (xb, yy, h), (xb, yy, hb)], [(0, 1, 2)], M["factory_wall"])
        mb.poly([(xa, y0, h), (xb, y0, hb), (xb, y1, hb), (xa, y1, h)], [(0, 1, 2, 3)], M["factory_roof"])
        mb.poly([(xb, y0, h), (xb, y1, h), (xb, y1, hb), (xb, y0, hb)], [(0, 1, 2, 3)], M["glass"])
    # Ворота цеха с сигнальной окантовкой
    for gx in (157, 165):
        mb.span(gx - 2.5, y0 - 0.14, 0, gx + 2.5, y0 - 0.04, 5.3, M["hazard"])
        mb.span(gx - 2.2, y0 - 0.18, 0.05, gx + 2.2, y0 - 0.1, 5.0, M["metal"])
        for k in range(1, 9):
            mb.span(gx - 2.2, y0 - 0.2, k * 0.55, gx + 2.2, y0 - 0.17, k * 0.55 + 0.04, M["dark"])
    # Административный корпус
    ox0, ox1 = 146, 153
    mb.span(ox0, 11, 0, ox1, y0, 7.0, M["brick"])
    mb.span(ox0 - 0.1, 10.9, 7.0, ox1 + 0.1, y0, 7.4, M["white"])
    panes = []
    for z in (2.0, 5.2):
        for wx in (147.4, 149.5, 151.6):
            mb.box((wx, 10.97, z), (1.3, 0.06, 1.4), M["glass"])
            mb.box((wx, 10.94, z - 0.75), (1.5, 0.1, 0.08), M["white"])
            panes.append((wx, z))
    mb.box((149.5, 10.97, 0.95), (1.2, 0.06, 1.9), M["door"])
    # Резервуары и трубопровод
    for ty in (19.0, 25.0):
        mb.cyl((174, ty, 0), (174, ty, 9), 2.0, 2.0, M["tank"], n=14)
        mb.cyl((174, ty, 9), (174, ty, 10.4), 2.0, 0, M["tank"], n=14)
        for z in (3, 6):
            mb.cyl((174, ty, z), (174, ty, z + 0.12), 2.05, 2.05, M["metal"], n=14)
        mb.span(172.0, ty - 0.25, 0.3, 172.05, ty + 0.25, 9.0, M["dark"])
    for py in (19.0, 25.0):
        mb.beam((170, py, 6.5), (172.1, py, 6.5), 0.4, 0.4, M["metal"])
    mb.beam((170.5, 17, 6.5), (170.5, 30, 6.5), 0.35, 0.35, M["metal"])
    # Труба котельной: красно-белые пояса
    cx, cy, ch = 177.5, 31.0, 32.0
    bands = 8
    for k in range(bands):
        z0, z1 = k * ch / bands, (k + 1) * ch / bands
        r0, r1 = 1.7 - 0.75 * z0 / ch, 1.7 - 0.75 * z1 / ch
        mb.cyl((cx, cy, z0), (cx, cy, z1), r0, r1, M["chimney_red"] if k % 2 == 0 else M["chimney_white"], n=14)
    mb.cyl((cx, cy, ch), (cx, cy, ch + 0.4), 1.05, 1.05, M["dark"], n=14)
    # Забор и площадка
    for xa, xb in ((142, 156), (162, 182)):
        mb.span(xa, 9.36, 1.8, xb, 9.44, 1.9, M["metal"])
        mb.span(xa, 9.36, 0.25, xb, 9.44, 0.32, M["metal"])
        for k in range(int((xb - xa) / 0.25)):
            mb.box((xa + k * 0.25, 9.4, 1.05), (0.03, 0.03, 1.7), M["metal"])
    mb.span(142, 8.6, 0, 182, 36, 0.04, M["paving_dark"])
    mb.build(parent=p)
    for k, (wx, z) in enumerate(panes[::2]):
        blink(f"win_factory_{k}", p, (wx, 10.92, z), 1.2, 1.3)
    for k in range(4):
        blink(f"win_factory_band_{k}", p, (x0 + 3 + k * 6, y0 - 0.1, 6.65), 1.8, 1.2)
    empty("smoke_src", (cx, cy, ch + 0.5))
    empty("spot_factory", (158, 10.5, 15))


# ---------- Город на фоне: дома среднего плана и силуэты высоток ----------

def build_backdrop():
    mid = MB("city_mid_blocks")
    blocks = [(-38, 16, 22, "block_a"), (-14, 14, 30, "block_b"), (8, 18, 19, "block_c"), (40, 14, 26, "block_b"),
              (64, 12, 33, "block_a"), (116, 14, 15, "block_c"), (150, 16, 21, "block_b"), (192, 18, 28, "block_a"),
              (216, 14, 18, "block_c")]
    for x, w, h, m in blocks:
        y0 = 78 + random.uniform(-3, 5)  # средний план — заметно дальше зданий-организаций
        h *= 0.75
        mid.span(x - w / 2, y0, 0, x + w / 2, y0 + 12, h, M[m])
        mid.span(x - w / 2 - 0.2, y0 - 0.2, h, x + w / 2 + 0.2, y0 + 12.2, h + 0.5, M["white"])
        for z in range(2, int(h) - 1, 3):  # сетка окон
            for k in range(int(w / 2.2)):
                wx = x - w / 2 + 1.1 + k * 2.2
                mid.box((wx, y0 - 0.03, z + 0.4), (1.1, 0.06, 1.3), M["glass"])
    mid.build()

    sky = MB("city_skyline")
    mats = ("sky_a", "sky_b", "sky_c")
    x = X0 - 120
    while x < X1 + 140:
        w = random.uniform(9, 22)
        h = random.uniform(22, 78)
        y0 = random.uniform(110, 170)
        m = M[random.choice(mats)]
        sky.span(x, y0, 0, x + w, y0 + w * 0.8, h, m)
        if random.random() < 0.35:  # ступенчатая верхушка / шпиль
            sky.span(x + w * 0.2, y0 + w * 0.15, h, x + w * 0.8, y0 + w * 0.65, h + random.uniform(5, 12), m)
        if random.random() < 0.2:
            sky.cyl((x + w / 2, y0 + w * 0.4, h), (x + w / 2, y0 + w * 0.4, h + 16), 0.5, 0.0, m, n=5)
        x += w + random.uniform(-3, 6)
    sky.build()


# ---------- Образцы машин и пешеходов (игра их клонирует) ----------

def extrude_y(mb, prof, y0, y1, m):
    """Выпуклый профиль в плоскости XZ, вытянутый по Y"""
    n = len(prof)
    pts = [(x, y0, z) for x, z in prof] + [(x, y1, z) for x, z in prof]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    mb.poly(pts, faces, m)


def wheels(mb, xs, half_w, r):
    for x in xs:
        for s in (-1, 1):
            mb.cyl((x, s * (half_w - 0.2), r), (x, s * (half_w + 0.02), r), r, r, M["tire"], n=12)
            mb.cyl((x, s * (half_w + 0.02), r), (x, s * (half_w + 0.04), r), r * 0.55, r * 0.55, M["metal"], n=10)


def car_template(kind):
    root = empty(f"car_tpl_{kind}")
    mb = MB(f"car_{kind}_body")
    if kind in ("sedan", "hatch"):
        L = 4.4 if kind == "sedan" else 3.8
        hw = 0.88
        mb.span(-L / 2, -hw, 0.32, L / 2, hw, 0.95, M["car_body"])
        cab = [(-1.3, 0.95), (1.0, 0.95), (0.4, 1.48), (-1.0, 1.48)] if kind == "sedan" else \
              [(-1.75, 0.95), (0.8, 0.95), (0.25, 1.55), (-1.7, 1.55)]
        extrude_y(mb, cab, -hw + 0.08, hw - 0.08, M["car_glass"])
        top = 1.48 if kind == "sedan" else 1.55
        mb.span(cab[3][0] + 0.05, -hw + 0.06, top, cab[2][0] - 0.05, hw - 0.06, top + 0.06, M["car_body"])
        mb.span(-0.12, -hw + 0.05, 0.95, 0.12, hw - 0.05, top, M["car_body"])  # средняя стойка
        for s in (-1, 1):
            mb.span(L / 2 - 0.05, s * 0.55 - 0.18, 0.62, L / 2 + 0.02, s * 0.55 + 0.18, 0.8, M["headlight"])
            mb.span(-L / 2 - 0.02, s * 0.6 - 0.15, 0.65, -L / 2 + 0.05, s * 0.6 + 0.15, 0.82, M["taillight"])
        mb.span(-L / 2 - 0.05, -hw, 0.3, -L / 2 + 0.2, hw, 0.48, M["dark"])
        mb.span(L / 2 - 0.2, -hw, 0.3, L / 2 + 0.05, hw, 0.48, M["dark"])
        wheels(mb, (-L / 2 + 0.85, L / 2 - 0.85), hw, 0.33)
    elif kind == "bus":
        L, hw = 11.0, 1.25
        mb.span(-L / 2, -hw, 0.4, L / 2, hw, 3.1, M["bus"])
        mb.span(-L / 2 + 0.3, -hw - 0.02, 1.6, L / 2 - 0.4, hw + 0.02, 2.7, M["car_glass"])
        mb.span(L / 2 - 0.02, -hw + 0.1, 1.2, L / 2 + 0.02, hw - 0.1, 2.85, M["car_glass"])
        mb.span(-L / 2 - 0.01, -hw - 0.01, 0.4, L / 2 + 0.01, hw + 0.01, 0.85, M["white"])
        mb.span(-L / 2 + 0.5, -hw + 0.1, 3.1, L / 2 - 1.5, hw - 0.1, 3.35, M["metal"])
        for k in range(10):
            x = -L / 2 + 0.8 + k * 1.05
            mb.span(x - 0.04, -hw - 0.04, 1.6, x + 0.04, hw + 0.04, 2.7, M["bus"])
        for s in (-1, 1):
            mb.span(L / 2 - 0.03, s * 0.85 - 0.2, 0.6, L / 2 + 0.03, s * 0.85 + 0.2, 0.85, M["headlight"])
        wheels(mb, (-L / 2 + 2.2, L / 2 - 2.2), hw, 0.5)
    else:  # truck
        hw = 1.15
        mb.span(-3.6, -hw, 0.7, 1.4, hw, 3.4, M["truck_box"])
        mb.span(1.5, -hw, 0.6, 3.4, hw, 2.6, M["car_body"])
        mb.span(2.6, -hw - 0.02, 1.7, 3.35, hw + 0.02, 2.45, M["car_glass"])
        mb.span(3.4, -hw + 0.1, 1.7, 3.42, hw - 0.1, 2.45, M["car_glass"])
        mb.span(-3.6, -hw, 0.45, 3.45, hw, 0.75, M["dark"])
        mb.span(-3.65, -0.9, 1.4, -3.6, 0.9, 3.2, M["metal"])
        wheels(mb, (-2.4, -1.2, 2.5), hw, 0.48)
    mb.build(parent=root)
    return root


def ped_template(i, coat, legs, skirt=False, backpack=False):
    root = empty(f"ped_tpl_{i}")
    body = MB(f"ped{i}_body")
    hip, sh = 0.92, 1.42
    if skirt:
        body.cyl((0, 0, 0.45), (0, 0, 0.98), 0.27, 0.16, coat, n=10)
    body.cyl((0, 0, 0.88), (0, 0, sh + 0.04), 0.17, 0.15, coat, n=10)
    body.cyl((0, 0, sh), (0, 0, sh + 0.1), 0.05, 0.05, M["skin"], n=6)
    body.blob((0.01, 0, sh + 0.21), 0.11, M["skin"], scale=(1, 0.9, 1.1), bump=0.02)
    body.blob((-0.02, 0, sh + 0.27), 0.115, M["hair"], scale=(1, 0.95, 0.75), bump=0.03)
    if backpack:
        body.span(-0.3, -0.14, 1.0, -0.14, 0.14, 1.38, M["hoarding"])
    body.build(parent=root)
    for side, s in (("L", 1), ("R", -1)):
        leg = MB(f"ped{i}_leg_{side}")
        leg.cyl((0, s * 0.09, hip), (0, s * 0.09, 0.1), 0.065, 0.055, M["skin"] if skirt else legs, n=6)
        leg.span(-0.07, s * 0.09 - 0.05, 0, 0.16, s * 0.09 + 0.05, 0.1, M["dark"])
        leg.build(parent=root, pivot=(0, s * 0.09, hip))
        arm = MB(f"ped{i}_arm_{side}")
        arm.cyl((0, s * 0.21, sh), (0, s * 0.23, 0.95), 0.05, 0.045, coat, n=6)
        arm.blob((0, s * 0.23, 0.91), 0.045, M["skin"], bump=0.02)
        arm.build(parent=root, pivot=(0, s * 0.21, sh))
    return root


def build_templates():
    roots = [car_template(k) for k in ("sedan", "hatch", "bus", "truck")]
    roots += [ped_template(0, mat("Куртка", "#3E6FA8", rough=0.9), mat("Джинсы", "#2F3A4E", rough=0.9)),
              ped_template(1, mat("Пальто", "#B04A6A", rough=0.9), None, skirt=True),
              ped_template(2, mat("Худи", "#E0A33A", rough=0.9), mat("Брюки", "#4A4F57", rough=0.9), backpack=True),
              ped_template(3, mat("Пиджак", "#55606E", rough=0.9), mat("Брюки тёмные", "#2B2F36", rough=0.9))]
    for k, r in enumerate(roots):  # убираем образцы далеко за кадр
        r.location = (TEMPLATES_X - k * 20, 0, 0)


# ---------- Сборка ----------

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    city_materials()
    build_street()
    street_furniture()
    build_houses()
    build_clinic()
    build_fire_station()
    build_business()
    build_construction()
    build_factory()
    build_backdrop()
    build_templates()
    empty("cam_min", (20, 0, 0))
    empty("cam_max", (166, 0, 0))

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_extras=True, export_apply=True)


build()
print("Готово:", OUT_GLB, OUT_BLEND)
