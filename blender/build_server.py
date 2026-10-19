"""
Локация 4 «Серверная»: помещение без окон. Стены — из модели servernaya.glb: её угол (две стены с кабельными
лотками; prep_servernaya.py → servernaya_ugol.glb) стоит четырьмя зеркальными копиями, вместе — замкнутая комната.
Пол — куски фальшпола с решётками pol_dlya_servernoi.glb (prep_pol.py → pol_servernoi.glb). Посередине — холодный коридор: два длинных ряда серверных стоек (server_rack.glb —
prep_static.py) фасадами друг к другу, в торце коридора у левой стены — ещё стойки, над ним линии светильников.
У правой стены — два монтёра за компьютерами (monter_za_compom.glb). Потолок со светильниками, металлическая дверь.

Запуск (из корня проекта):
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/build_server.py

Результат:
    public/models/server.glb   — сцена для игры (http://localhost:5173/server)
    blender/server_base.blend  — исходник; скрипт перезаписывает его при каждом запуске

Оси Blender: X — вдоль коридора, Y — от двери (−Y) к дальней стене (+Y), Z — вверх; пол помещения на z = 0.
Имена, которые читает игра, — как в build_city.py; lamp_<n> — точечный свет светильника (src/server/ambient.ts).
"""

import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import build_city as city  # noqa: E402
from lowpoly import MB, empty, mat, principled  # noqa: E402
from prep_furgon import bilinear, logo_mask, render_text_mask  # noqa: E402

ROOT = city.ROOT
OUT_GLB = os.path.join(ROOT, "public", "models", "server.glb")
OUT_BLEND = os.path.join(ROOT, "blender", "server_base.blend")
RACK_GLB = os.path.join(ROOT, "blender", "assets", "server_rack.glb")
DESK_GLB = os.path.join(ROOT, "blender", "assets", "monter_za_compom.glb")
TUSHIT_GLB = os.path.join(ROOT, "blender", "assets", "monter_tushit_server.glb")
SHKAF_GLB = os.path.join(ROOT, "blender", "assets", "pozh_shkaf.glb")
ROOM_GLB = os.path.join(ROOT, "blender", "assets", "servernaya_ugol.glb")
POL_GLB = os.path.join(ROOT, "blender", "assets", "pol_servernoi.glb")  # кусок фальшпола (prep_pol.py)
LOGO_PNG = os.path.join(ROOT, "logo_ktl.png")
# Логотип и под ним надпись KAZAKHTELECOM на дальней стене (+Y): центр по x, низ надписи
# над полом, ширина надписи; высота логотипа; зазор между ними, м
# (между пилястрами стены модели на x = 1,2 и 4,8 и ниже кабельных лотков)
SIGN_X, SIGN_Z, SIGN_W, SIGN_LOGO_H, SIGN_GAP = 3.0, 1.3, 2.6, 0.9, 0.12
SIGN_RES = 400  # пикселей на метр
SHKAF_POS = (3.2, 1.0)  # x на стене −Y, высота низа над полом: шкаф и кронштейн — пустые (нарушение)

# Угол из servernaya_ugol.glb: наружный угол стен в начале координат, угол занимает x ∈ [−ROOM_HALF[0], 0],
# y ∈ [−ROOM_HALF[1], 0]; внутренние грани стен — в INNER от наружных (prep_servernaya.py)
ROOM_HALF = (6.45, 5.85)
INNER = (0.26, 0.18)
W, D, H = 2 * (ROOM_HALF[0] - INNER[0]), 2 * (ROOM_HALF[1] - INNER[1]), 3.6  # внутри: 12,38 × 11,34 м
# Двери — в стене модели на +X при y = ±DOOR_Y (из-за отражения их две); игрок входит в ту, что на −Y.
# На той же стене при y = ±1,6 — электрощиты, выступают на 0,34 м
DOOR_Y = 3.15
# Стойки 0,94 × 0,93 м, высота 2 м. Холодный коридор шириной AISLE вдоль X по оси y = 0: от левой стены
# к двери. Ряд у двери (−Y) — фасадом к +Y, ряд у окна — фасадом к −Y, по ROW_N стоек, от торца коридора
# до x = ROW_X0 + ROW_N·RACK_W; в торце у левой стены — END_N стоек фасадом к +X, задние стенки — в 0,3 м от стены.
# (x центра, y центра, поворот): модель смотрит фасадом на −Y; π — фасадом на +Y, π/2 — на +X
RACK_W, RACK_D = 0.95, 0.93
AISLE = 2.2
ROW_N, END_N = 10, 2
ROW_X0 = -W / 2 + 0.3
ROW_Y = AISLE / 2 + RACK_D / 2
RACKS = ([(ROW_X0 + (k + 0.5) * RACK_W, -ROW_Y, math.pi) for k in range(ROW_N)]
         + [(ROW_X0 + (k + 0.5) * RACK_W, ROW_Y, 0.0) for k in range(ROW_N)]
         + [(ROW_X0 + RACK_D / 2, (k - (END_N - 1) / 2) * RACK_W, math.pi / 2) for k in range(END_N)])
# Вместо крайней стойки ряда у двери (на входе в коридор) — сцена «монтёр льёт воду в стойку, из стойки дым».
# Стойка в этой модели крупнее: 1,14 м по X файла, 1,16 м по Y; центр (0,63; 0,04), фасад к −Y, как у обычных
# стоек; монтёр — сбоку (−X файла). Поворот тот же, что у ряда (π): фасадом в коридор, монтёр — у торца ряда,
# лицом к входу. Задняя стенка — на одной линии с рядом, край — вплотную к соседней стойке
TUSHIT_RACK = (0.63, 0.04)
TUSHIT_SIZE = (1.14, 1.16)
TUSHIT_RZ = math.pi
TUSHIT_SMOKE = [(0.63, -0.5, 1.75), (0.45, -0.5, 1.35), (0.63, 0.04, 2.02)]  # фасад и верх стойки, в координатах файла
_front_x, _front_y, _ = RACKS.pop(ROW_N - 1)  # ряд у двери, последнее место
TUSHIT_CENTER = (_front_x - RACK_W / 2 + TUSHIT_SIZE[0] / 2, _front_y - RACK_D / 2 + TUSHIT_SIZE[1] / 2)
# Рабочие места у стены −Y за рядом стоек, между пилястрами x = −4,8 и −1,2: стол монитором к стене, монтёр
# спиной к комнате. В файле монитор на −Y, край стола с монитором — в 0,71 м от центра модели
DESK_EDGE = 0.71
DESKS = [(x, -D / 2 + 0.05 + DESK_EDGE, 0.0) for x in (-3.6, -2.0)]
# Потолочные светильники 1,2 × 0,3 м: две линии над коридором и по линии над проходами за рядами
PANELS = ([(x, y) for x in np.arange(-5.4, 5.5, 1.5) for y in (-0.55, 0.55)]
          + [(x, y) for x in np.arange(-4.5, 5.0, 3.0) for y in (-3.6, 3.6)])
# Пол — куски 3,0 × 3,6 м (столбцы решёток вдоль X, в 0,9 м от середины куска — у фасадов стоек коридора),
# сетка с центром в середине комнаты, под стенами — с запасом
POL_SIZE = (3.0, 3.6)
POLS = [(i * POL_SIZE[0], j * POL_SIZE[1]) for i in range(-2, 3) for j in range(-2, 3)]
LAMPS = [(x, 0.0) for x in (-4.5, -1.5, 1.5, 4.5)] + [(x, y) for x in (-3.0, 3.0) for y in (-3.6, 3.6)]  # точечный свет

def materials():
    return dict(
        ceiling=mat("Потолок", "#F1F2F3", rough=0.95),
        lamp=city.glow(mat("Светильник", "#FFFFFF", rough=0.3), "#F4F8FF", 4.0),
        lamp_rim=mat("Рамка светильника", "#D6D9DC", rough=0.5),
    )


def build_room():
    """Четыре копии угла (меш и текстуры общие), отражённые по X и/или Y: каждая — под пустышкой room_m<n>
    с масштабом ±1, стыкуются открытыми краями по осям x = 0 и y = 0"""
    first = city.place_model(ROOM_GLB, "room_q0", ROOM_HALF, 0, solid=False, smooth=True)
    root0 = first[0].parent
    root0.location.z = 0  # верх пола модели — на нуле, плита пола ниже
    for n, (sx, sy) in enumerate(((1, 1), (-1, 1), (1, -1), (-1, -1))):
        holder = empty(f"room_m{n}", (0, 0, 0))
        holder.scale = (sx, sy, 1)
        r = root0
        if n:
            r = root0.copy()
            r.name = f"room_q{n}"
            bpy.context.collection.objects.link(r)
            for o in first:
                c = o.copy()
                c.parent = r
                bpy.context.collection.objects.link(c)
        r.parent = holder


def build_floor():
    """Куски пола — копии одной модели (меш и текстуры общие)"""
    first = city.place_model(POL_GLB, "pol_0", POLS[0], 0, solid=False)
    root0 = first[0].parent
    root0.location.z = 0  # верх плиток на нуле
    for n, (x, y) in enumerate(POLS[1:], 1):
        r = root0.copy()
        r.name = f"pol_{n}"
        r.location = (x, y, 0)
        bpy.context.collection.objects.link(r)
        for o in first:
            c = o.copy()
            c.parent = r
            bpy.context.collection.objects.link(c)


def build_ceiling(M):
    c = MB("ceiling")
    c.span(-ROOM_HALF[0], -ROOM_HALF[1], H, ROOM_HALF[0], ROOM_HALF[1], H + 0.1, M["ceiling"])
    c.build()
    lamps = MB("ceiling_lamps")
    for x, y in PANELS:
        lamps.span(x - 0.63, y - 0.18, H - 0.03, x + 0.63, y + 0.18, H, M["lamp_rim"])
        lamps.span(x - 0.6, y - 0.15, H - 0.035, x + 0.6, y + 0.15, H - 0.03, M["lamp"])
    lamps.build()
    for n, (x, y) in enumerate(LAMPS):
        empty(f"lamp_{n}", (x, y, H - 0.15))


def place_copies(path, prefix, spots):
    """Копии одной модели (меш и текстуры общие) по местам (x, y, поворот); каждая — препятствие"""
    first = None
    for i, (x, y, rz) in enumerate(spots):
        name = f"{prefix}_{i}"
        if first is None:
            first = city.place_model(path, name, (x, y), rz, smooth=True)
            continue
        root = first[0].parent.copy()
        root.name = name
        root.location.x, root.location.y = x, y
        root.rotation_euler.z = rz
        bpy.context.collection.objects.link(root)
        for o in first:
            c = o.copy()
            c.parent = root
            bpy.context.collection.objects.link(c)


def place_tushit():
    c, s = math.cos(TUSHIT_RZ), math.sin(TUSHIT_RZ)
    rot = lambda x, y: (x * c - y * s, x * s + y * c)
    rx, ry = rot(*TUSHIT_RACK)
    ox, oy = TUSHIT_CENTER[0] - rx, TUSHIT_CENTER[1] - ry
    city.place_model(TUSHIT_GLB, "wall_server_voda", (ox, oy), TUSHIT_RZ, smooth=True)
    for n, (x, y, z) in enumerate(TUSHIT_SMOKE):  # откуда идёт дым (src/server/ambient.ts)
        dx, dy = rot(x, y)
        empty(f"smoke_src_{n}", (ox + dx, oy + dy, z))


def sign_pixels():
    """Картинка логотипа с надписью: синий по прозрачному (RGBA, строка 0 — низ). До сброса сцены:
    render_text_mask рендерит надпись в своей сцене"""
    text = render_text_mask()
    logo, blue = logo_mask(LOGO_PNG)
    th = SIGN_W * text.shape[0] / text.shape[1]
    lw = SIGN_LOGO_H * logo.shape[1] / logo.shape[0]
    H = th + SIGN_GAP + SIGN_LOGO_H
    w, h = int(SIGN_W * SIGN_RES), int(H * SIGN_RES)
    X, Z = np.meshgrid((np.arange(w) + 0.5) / SIGN_RES, (np.arange(h) + 0.5) / SIGN_RES)
    a = np.maximum(bilinear(text, X / SIGN_W, Z / th),
                   bilinear(logo, (X - (SIGN_W - lw) / 2) / lw, (Z - th - SIGN_GAP) / SIGN_LOGO_H))
    px = np.zeros((h, w, 4), np.float32)
    px[:, :, :3] = blue
    px[:, :, 3] = np.clip(a, 0, 1)
    return px, H


def build_sign(px, height):
    """Наклейка на внутренней грани стены с окном — прямоугольник с картинкой, смотрит в комнату (−Y)"""
    h, w = px.shape[:2]
    img = bpy.data.images.new("ktl_wall_sign", w, h, alpha=True)
    img.pixels.foreach_set(px.ravel())
    img.pack()
    m = bpy.data.materials.new("Логотип на стене")
    m.use_nodes = True
    b = principled(m.node_tree)
    tex = m.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    m.node_tree.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    m.node_tree.links.new(tex.outputs["Alpha"], b.inputs["Alpha"])
    b.inputs["Roughness"].default_value = 0.6
    m.surface_render_method = "BLENDED"
    x0, x1 = SIGN_X - SIGN_W / 2, SIGN_X + SIGN_W / 2
    z0, z1 = SIGN_Z, SIGN_Z + height
    y = D / 2 - 0.006
    me = bpy.data.meshes.new("wall_sign")
    me.from_pydata([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], [], [(0, 1, 2, 3)])  # нормаль к −Y
    uv = me.uv_layers.new()
    for loop, co in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = co
    me.materials.append(m)
    o = bpy.data.objects.new("ktl_wall_sign", me)
    o["no_shadow"] = 1
    bpy.context.collection.objects.link(o)


def build():
    sign = sign_pixels()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    M = materials()
    build_room()
    build_floor()
    build_ceiling(M)
    build_sign(*sign)
    place_copies(RACK_GLB, "wall_server", RACKS)
    place_copies(DESK_GLB, "wall_desk", DESKS)
    place_tushit()
    # Пожарный шкаф на стене −Y, фасадом в комнату (в файле фасад на −Y)
    city.place_model(SHKAF_GLB, "wall_pozh_shkaf", (SHKAF_POS[0], -D / 2 + 0.16), math.pi, base_z=SHKAF_POS[1],
                     smooth=True)

    empty("spawn_A", (W / 2 - 1.0, -DOOR_Y, 0))  # вошёл в дверь модели; монтёр с ведром — до x 4,75, y ≥ −2,04
    empty("goal_B", (ROW_X0 + RACK_D + 1.3, 0.0, 0))    # в конце коридора, перед стойками в торце
    m = 0.45  # от стен — радиус игрока с запасом
    empty("walk_min", (-W / 2 + m, -D / 2 + m, 0))
    empty("walk_max", (W / 2 - m, D / 2 - m, 0))

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_extras=True, export_apply=True)


build()
print("Готово:", OUT_GLB, OUT_BLEND)
