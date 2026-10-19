"""
Локация 4 «Серверная»: помещение с окном; посередине — холодный коридор: два длинных ряда серверных стоек
(server_rack.glb — prep_static.py) фасадами друг к другу, в торце коридора у левой стены — ещё стойки, в проходе
перфорированные плитки, над ним линии светильников. У правой стены — два монтёра за компьютерами
(monter_za_compom.glb). Фальшпол из плиток 60 × 60 см, светлые стены, потолок со светильниками, металлическая дверь, окно
с подоконником и радиатором. За окном двор: квартал gorodskie_doma.glb и деревья из локации 2.

Запуск (из корня проекта):
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/build_server.py

Результат:
    public/models/server.glb   — сцена для игры (http://localhost:5173/server)
    blender/server_base.blend  — исходник; скрипт перезаписывает его при каждом запуске

Оси Blender: X — вдоль окна, Y — от двери (−Y) к окну (+Y), Z — вверх; пол помещения на z = 0.
Имена, которые читает игра, — как в build_city.py; свойство no_shadow — стекло не отбрасывает тень,
чтобы солнце светило в окно; lamp_<n> — точечный свет светильника (src/server/ambient.ts).
"""

import math
import os
import random
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
LOGO_PNG = os.path.join(ROOT, "logo_ktl.png")
# Логотип и под ним надпись KAZAKHTELECOM на стене с окном (+Y), справа от окна: центр по x, низ надписи
# над полом, ширина надписи; высота логотипа; зазор между ними, м
SIGN_X, SIGN_Z, SIGN_W, SIGN_LOGO_H, SIGN_GAP = 4.25, 1.35, 3.0, 1.0, 0.14
SIGN_RES = 400  # пикселей на метр
SHKAF_POS = (3.2, 1.0)  # x на стене у двери (−Y), высота низа над полом: шкаф и кронштейн — пустые (нарушение)

W, D, H = 13.0, 10.0, 3.6        # помещение: ширина по X, глубина по Y, высота
WALL = 0.25                      # толщина стен
TILE = 0.6                       # плитка фальшпола
WINDOW_X = (-2.0, 2.0)           # проём окна в стене +Y
WINDOW_Z = (0.9, 2.6)
DOOR_X = (4.5, 5.5)              # проём двери в стене −Y
DOOR_H = 2.1
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
# Рабочие места у правой стены (x = W/2): стол монитором к стене, монтёр спиной к комнате. В файле монитор на −Y,
# край стола с монитором — в 0,71 м от центра модели; поворот на 90° ставит −Y модели на +X сцены (к стене)
DESK_EDGE = 0.71
# — за рядом у окна, чтобы от входа коридор был виден целиком
DESKS = [(W / 2 - 0.05 - DESK_EDGE, y, math.pi / 2) for y in (2.6, 4.0)]
# Потолочные светильники 1,2 × 0,3 м: две линии над коридором и по линии над проходами за рядами
PANELS = ([(x, y) for x in np.arange(-5.4, 5.5, 1.5) for y in (-0.55, 0.55)]
          + [(x, y) for x in np.arange(-4.5, 5.0, 3.0) for y in (-3.6, 3.6)])
LAMPS = [(x, 0.0) for x in (-4.5, -1.5, 1.5, 4.5)] + [(x, y) for x in (-3.0, 3.0) for y in (-3.6, 3.6)]  # точечный свет
PERF_RES = 256  # пикселей на плитку в текстуре перфорированной плитки

random.seed(4)


def materials():
    return dict(
        wall=mat("Стена", "#EEF0F2", rough=0.9),
        skirting=mat("Плинтус", "#7D8389", rough=0.6),
        ceiling=mat("Потолок", "#F1F2F3", rough=0.95),
        tile=mat("Плитка фальшпола", "#E2E5E8", rough=0.5),
        tile2=mat("Плитка фальшпола тёмная", "#D9DCE0", rough=0.5),
        perf=perf_mat(),
        seam=mat("Шов фальшпола", "#4A4F55", rough=0.8),
        frame=mat("Рама ПВХ", "#F4F5F6", rough=0.4),
        sill=mat("Подоконник", "#ECEDEE", rough=0.35),
        glass=glass_mat(),
        radiator=mat("Радиатор", "#EEF0F2", rough=0.4, metal=0.2),
        door=mat("Дверь металлическая", "#7E8790", rough=0.5, metal=0.5),
        handle=mat("Ручка", "#2B2E33", rough=0.4, metal=0.6),
        lamp=city.glow(mat("Светильник", "#FFFFFF", rough=0.3), "#F4F8FF", 4.0),
        lamp_rim=mat("Рамка светильника", "#D6D9DC", rough=0.5),
        outside=mat("Двор", "#7DA65A", rough=0.95),
        asphalt=mat("Асфальт двора", "#6B6F74", rough=0.95),
    )


def glass_mat():
    m = mat("Стекло окна", "#BFD9EA", rough=0.05)
    principled(m.node_tree).inputs["Alpha"].default_value = 0.18
    m.surface_render_method = "BLENDED"
    return m


def perf_mat():
    """Перфорированная плитка холодного коридора: светлая, с сеткой тёмных отверстий и сплошной каймой"""
    n = PERF_RES
    X, Y = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n)
    step = 1 / 22
    hole = ((np.hypot((X % step) - step / 2, (Y % step) - step / 2) < step * 0.3)
            & (abs(X - 0.5) < 0.43) & (abs(Y - 0.5) < 0.43))
    px = np.ones((n, n, 4), np.float32)
    px[:, :, :3] = np.where(hole[..., None], (0.22, 0.24, 0.26), (0.86, 0.88, 0.9))
    img = bpy.data.images.new("perf_tile", n, n)
    img.pixels.foreach_set(px.ravel())
    img.pack()
    m = bpy.data.materials.new("Плитка перфорированная")
    m.use_nodes = True
    b = principled(m.node_tree)
    tex = m.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    m.node_tree.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.45
    b.inputs["Metallic"].default_value = 0.3
    return m


def build_floor(M):
    """Фальшпол: плитки с зазором, под ними тёмное основание — зазоры читаются как швы. В коридоре между рядами —
    перфорированные плитки (свой меш с UV 0..1 на каждую плитку)"""
    base = MB("floor_base")
    base.span(-W / 2, -D / 2, -0.06, W / 2, D / 2, -0.01, M["seam"])
    base.build()
    mb = MB("raised_floor")
    nx, ny = int(W / TILE + 0.5), int(D / TILE + 0.5)
    tw, td = W / nx, D / ny
    verts, faces = [], []
    for i in range(nx):
        for j in range(ny):
            x0, y0 = -W / 2 + i * tw + 0.006, -D / 2 + j * td + 0.006
            x1, y1 = x0 + tw - 0.012, y0 + td - 0.012
            if abs((y0 + y1) / 2) < AISLE / 2 - 0.4 and x0 > ROW_X0 + RACK_D:
                k = len(verts)
                verts += [(x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0)]
                faces.append((k, k + 1, k + 2, k + 3))
                mb.span(x0, y0, -0.03, x1, y1, -0.002, M["tile"])  # тело плитки под перфорированной гранью
                continue
            m = M["tile"] if (i + j) % 2 else M["tile2"]
            mb.span(x0, y0, -0.03, x1, y1, 0.0, m)
    mb.build()
    me = bpy.data.meshes.new("aisle_perf")
    me.from_pydata(verts, [], faces)
    uv = me.uv_layers.new()
    for n, loop in enumerate(uv.data):
        loop.uv = ((0, 0), (1, 0), (1, 1), (0, 1))[n % 4]
    me.materials.append(M["perf"])
    o = bpy.data.objects.new("aisle_perf", me)
    bpy.context.collection.objects.link(o)


def wall_with_opening(mb, axis_y, x_open, z_open, m):
    """Стена вдоль X на y = axis_y (наружная грань — дальше от центра) с проёмом x_open × z_open"""
    s = 1 if axis_y > 0 else -1
    y0, y1 = sorted((axis_y, axis_y + s * WALL))
    (xa, xb), (za, zb) = x_open, z_open
    mb.span(-W / 2 - WALL, y0, 0, xa, y1, H, m)
    mb.span(xb, y0, 0, W / 2 + WALL, y1, H, m)
    if za > 0:
        mb.span(xa, y0, 0, xb, y1, za, m)
    mb.span(xa, y0, zb, xb, y1, H, m)


def build_walls(M):
    walls = MB("room_walls")  # не wall_*: рамка всех стен — вся комната; из неё не пускает зона walk_min / walk_max
    wall_with_opening(walls, D / 2, WINDOW_X, WINDOW_Z, M["wall"])
    wall_with_opening(walls, -D / 2, DOOR_X, (0, DOOR_H), M["wall"])
    for x in (-W / 2, W / 2):
        s = 1 if x > 0 else -1
        x0, x1 = sorted((x, x + s * WALL))
        walls.span(x0, -D / 2 - WALL, 0, x1, D / 2 + WALL, H, M["wall"])
    walls.build()
    sk = MB("skirting")  # плинтус по периметру, кроме проёма двери
    for y in (-D / 2, D / 2):
        s = 1 if y > 0 else -1
        for xa, xb in ((-W / 2, DOOR_X[0]), (DOOR_X[1], W / 2)) if y < 0 else ((-W / 2, W / 2),):
            sk.span(xa, y - s * 0.02, 0, xb, y, 0.08, M["skirting"])
    for x in (-W / 2, W / 2):
        s = 1 if x > 0 else -1
        sk.span(x - s * 0.02, -D / 2, 0, x, D / 2, 0.08, M["skirting"])
    sk.build()


def build_ceiling(M):
    c = MB("ceiling")
    c.span(-W / 2 - WALL, -D / 2 - WALL, H, W / 2 + WALL, D / 2 + WALL, H + 0.1, M["ceiling"])
    c.build()
    lamps = MB("ceiling_lamps")
    for x, y in PANELS:
        lamps.span(x - 0.63, y - 0.18, H - 0.03, x + 0.63, y + 0.18, H, M["lamp_rim"])
        lamps.span(x - 0.6, y - 0.15, H - 0.035, x + 0.6, y + 0.15, H - 0.03, M["lamp"])
    lamps.build()
    for n, (x, y) in enumerate(LAMPS):
        empty(f"lamp_{n}", (x, y, H - 0.15))


def build_window(M):
    (xa, xb), (za, zb) = WINDOW_X, WINDOW_Z
    y = D / 2 + WALL / 2  # рама посередине стены
    fr = MB("window_frame")
    t = 0.07
    for x in (xa, xb, (xa + xb) / 2):  # стойки и импост
        fr.span(x - t / 2, y - 0.04, za, x + t / 2, y + 0.04, zb, M["frame"])
    for z in (za, zb):
        fr.span(xa, y - 0.04, z - t / 2, xb, y + 0.04, z + t / 2, M["frame"])
    fr.build()
    g = MB("window_glass")
    g.span(xa, y - 0.005, za, xb, y + 0.005, zb, M["glass"])
    g.build()["no_shadow"] = 1
    sill = MB("wall_window_sill")  # подоконник и радиатор под окном
    sill.span(xa - 0.1, D / 2 - 0.25, za - 0.04, xb + 0.1, D / 2 + 0.02, za, M["sill"])
    for k in range(int((xb - xa - 0.4) / 0.21)):
        x = xa + 0.25 + k * 0.21
        sill.span(x - 0.04, D / 2 - 0.12, 0.2, x + 0.04, D / 2 - 0.04, 0.75, M["radiator"])
    sill.build()


def build_door(M):
    (xa, xb) = DOOR_X
    y = -D / 2 - WALL / 2
    d = MB("wall_door")
    d.span(xa - 0.06, y - 0.15, 0, xa, y + 0.15, DOOR_H + 0.06, M["frame"])
    d.span(xb, y - 0.15, 0, xb + 0.06, y + 0.15, DOOR_H + 0.06, M["frame"])
    d.span(xa - 0.06, y - 0.15, DOOR_H, xb + 0.06, y + 0.15, DOOR_H + 0.06, M["frame"])
    d.span(xa, y - 0.03, 0.01, xb, y + 0.03, DOOR_H, M["door"])
    d.span(xa + 0.08, y + 0.03, 1.0, xa + 0.22, y + 0.07, 1.05, M["handle"])  # ручка изнутри
    d.build()


def build_outside(M):
    """Двор за окном: газон, дорожка, квартал и деревья — чтобы в окне был вид, а не пустое небо"""
    g = MB("ground")
    g.span(-300, -300, -0.3, 300, 300, -0.25, M["outside"])
    g.span(-40, D / 2 + 6, -0.25, 40, D / 2 + 10, -0.24, M["asphalt"])
    g.build()
    city.place_model(city.DOMA_GLB, "doma_yard", (4.0, D / 2 + 14 + city.DOMA_SIZE[1] / 2), 0, base_z=-0.25,
                     solid=False, smooth=True)
    # Деревья и кусты из локации 2 — сквер между окном и дорожкой и за дорожкой; ближе 7 м в окно видны
    # только стволы, поэтому первый ряд — в 7–9 м от стены
    trees, kusty = [], []
    for row, (y0, n) in enumerate(((D / 2 + 7.5, 11), (D / 2 + 13, 9))):
        for k in range(n):
            x = -22 + k * 44 / (n - 1) + random.uniform(-1.2, 1.2) + row * 2
            trees.append((random.choice(("tree_bereza", "tree_bereza", "tree_topol", "tree_el")), x,
                          y0 + random.uniform(-1, 1), -0.25, random.uniform(0.8, 1.05), random.uniform(0, 2 * math.pi),
                          None))
    for k in range(14):
        x = -20 + k * 3.1 + random.uniform(-0.5, 0.5)
        kusty.append((random.choice(("kusty_para", "kust_na_podlozhke", "cvetnik_3", "kusty_para")), x,
                      D / 2 + 3.2 + random.uniform(-0.4, 0.4), -0.4, 1.0, random.uniform(0, 2 * math.pi), None))
    city.clone_parts(city.DEREVYA_GLB, trees)
    city.clone_parts(city.KUSTY_GLB, kusty)


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
    build_floor(M)
    build_walls(M)
    build_ceiling(M)
    build_window(M)
    build_door(M)
    build_sign(*sign)
    place_copies(RACK_GLB, "wall_server", RACKS)
    place_copies(DESK_GLB, "wall_desk", DESKS)
    place_tushit()
    # Пожарный шкаф на стене у двери, фасадом в комнату (в файле фасад на −Y)
    city.place_model(SHKAF_GLB, "wall_pozh_shkaf", (SHKAF_POS[0], -D / 2 + 0.16), math.pi, base_z=SHKAF_POS[1],
                     smooth=True)
    build_outside(M)

    empty("spawn_A", (DOOR_X[1], -0.4, 0))  # вошёл в дверь и повернул к коридору; монтёр с ведром — до x 4,75
    empty("goal_B", (ROW_X0 + RACK_D + 1.3, 0.0, 0))    # в конце коридора, перед стойками в торце
    m = 0.45  # от стен — радиус игрока с запасом
    empty("walk_min", (-W / 2 + m, -D / 2 + m, 0))
    empty("walk_max", (W / 2 - m, D / 2 - m - 0.25, 0))  # у окна мешает подоконник

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_extras=True, export_apply=True)


build()
print("Готово:", OUT_GLB, OUT_BLEND)
