"""
Локация 4 «Серверная»: помещение с окном и четырьмя рядами серверных стоек вдоль левой стены
(server_rack.glb — prep_static.py); у правой стены — два монтёра за компьютерами (monter_za_compom.glb).
Фальшпол из плиток 60 × 60 см, светлые стены, потолок со светильниками, металлическая дверь, окно
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

sys.path.insert(0, os.path.dirname(__file__))
import build_city as city  # noqa: E402
from lowpoly import MB, empty, mat, principled  # noqa: E402

ROOT = city.ROOT
OUT_GLB = os.path.join(ROOT, "public", "models", "server.glb")
OUT_BLEND = os.path.join(ROOT, "blender", "server_base.blend")
RACK_GLB = os.path.join(ROOT, "blender", "assets", "server_rack.glb")
DESK_GLB = os.path.join(ROOT, "blender", "assets", "monter_za_compom.glb")
TUSHIT_GLB = os.path.join(ROOT, "blender", "assets", "monter_tushit_server.glb")

W, D, H = 16.0, 12.0, 3.6        # помещение: ширина по X, глубина по Y, высота
WALL = 0.25                      # толщина стен
TILE = 0.6                       # плитка фальшпола
WINDOW_X = (-2.0, 2.0)           # проём окна в стене +Y
WINDOW_Z = (0.9, 2.6)
DOOR_X = (5.5, 6.5)              # проём двери в стене −Y
DOOR_H = 2.1
# Стойки 0,94 × 0,93 м, высота 2 м: 4 ряда по 4 вдоль левой стены (x = −W/2), ряды идут по Y, все стойки
# фасадом к +X — к двери и окну; первый ряд — спиной в 0,3 м от стены, между рядами проходы по 1,4 м.
# (x центра, y центра, поворот): модель смотрит фасадом на −Y, поворот на 90° — фасадом на +X
RACK_W, RACK_D = 0.95, 0.93
RACK_AISLE = 1.4
RACKS = [(-W / 2 + 0.3 + RACK_D / 2 + r * (RACK_D + RACK_AISLE), (k - 1.5) * RACK_W, math.pi / 2)
         for r in range(4) for k in range(4)]
# Вместо крайней стойки переднего ряда (со стороны двери) — сцена «монтёр льёт воду в стойку, из стойки дым».
# Стойка в этой модели крупнее: 1,14 м по X файла, 1,16 м по Y; центр (0,63; 0,04), фасад к −Y, как у обычных
# стоек; монтёр — сбоку (−X файла). Поворот тот же, что у ряда: фасадом в проход, монтёр — у торца ряда.
# Задняя стенка — на одной линии с рядом, край — вплотную к соседней стойке
TUSHIT_RACK = (0.63, 0.04)
TUSHIT_SIZE = (1.14, 1.16)
TUSHIT_RZ = math.pi / 2
TUSHIT_SMOKE = [(0.63, -0.5, 1.75), (0.45, -0.5, 1.35), (0.63, 0.04, 2.02)]  # фасад и верх стойки, в координатах файла
_front_x, _front_y, _ = RACKS.pop(12)  # ряд r = 3, место k = 0
TUSHIT_CENTER = (_front_x - RACK_D / 2 + TUSHIT_SIZE[1] / 2, _front_y + RACK_W / 2 - TUSHIT_SIZE[0] / 2)
# Рабочие места у правой стены (x = W/2): стол монитором к стене, монтёр спиной к комнате. В файле монитор на −Y,
# край стола с монитором — в 0,71 м от центра модели; поворот на 90° ставит −Y модели на +X сцены (к стене)
DESK_EDGE = 0.71
DESKS = [(W / 2 - 0.05 - DESK_EDGE, y, math.pi / 2) for y in (-0.9, 0.9)]
LAMPS = [(x, y) for x in (-5.0, 0.0, 5.0) for y in (-3.5, 0.0, 3.5)]  # потолочные светильники 60 × 60 см

random.seed(4)


def materials():
    return dict(
        wall=mat("Стена", "#E4E7EA", rough=0.9),
        skirting=mat("Плинтус", "#7D8389", rough=0.6),
        ceiling=mat("Потолок", "#F1F2F3", rough=0.95),
        tile=mat("Плитка фальшпола", "#C9CDD1", rough=0.6),
        tile2=mat("Плитка фальшпола тёмная", "#BEC2C7", rough=0.6),
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


def build_floor(M):
    """Фальшпол: плитки с зазором, под ними тёмное основание — зазоры читаются как швы"""
    base = MB("floor_base")
    base.span(-W / 2, -D / 2, -0.06, W / 2, D / 2, -0.01, M["seam"])
    base.build()
    mb = MB("raised_floor")
    nx, ny = int(W / TILE + 0.5), int(D / TILE + 0.5)
    for i in range(nx):
        for j in range(ny):
            x0, y0 = -W / 2 + i * W / nx, -D / 2 + j * D / ny
            m = M["tile"] if (i + j) % 2 else M["tile2"]
            mb.span(x0 + 0.006, y0 + 0.006, -0.03, x0 + W / nx - 0.006, y0 + D / ny - 0.006, 0.0, m)
    mb.build()


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
    for n, (x, y) in enumerate(LAMPS):
        lamps.span(x - 0.31, y - 0.31, H - 0.03, x + 0.31, y + 0.31, H, M["lamp_rim"])
        lamps.span(x - 0.28, y - 0.28, H - 0.035, x + 0.28, y + 0.28, H - 0.03, M["lamp"])
        empty(f"lamp_{n}", (x, y, H - 0.15))
    lamps.build()


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
    trees = []
    for k in range(9):
        x = -16 + k * 4 + random.uniform(-0.8, 0.8)
        trees.append((random.choice(("tree_bereza", "tree_topol", "tree_el")), x, D / 2 + 4 + random.uniform(-0.5, 0.5),
                      -0.25, random.uniform(0.7, 0.95), random.uniform(0, 2 * math.pi), None))
    city.clone_parts(city.DEREVYA_GLB, trees)


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


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    M = materials()
    build_floor(M)
    build_walls(M)
    build_ceiling(M)
    build_window(M)
    build_door(M)
    place_copies(RACK_GLB, "wall_server", RACKS)
    place_copies(DESK_GLB, "wall_desk", DESKS)
    place_tushit()
    build_outside(M)

    empty("spawn_A", (sum(DOOR_X) / 2, -D / 2 + 2.8, 0))  # перед дверью, чтобы камере за спиной хватало места
    empty("goal_B", (0.0, D / 2 - 0.9, 0))    # у окна
    m = 0.45  # от стен — радиус игрока с запасом
    empty("walk_min", (-W / 2 + m, -D / 2 + m, 0))
    empty("walk_max", (W / 2 - m, D / 2 - m - 0.25, 0))  # у окна мешает подоконник

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_extras=True, export_apply=True)


build()
print("Готово:", OUT_GLB, OUT_BLEND)
