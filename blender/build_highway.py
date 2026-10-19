"""
Локация 5 «Трасса»: загородная двухполосная трасса днём. Вдоль неё — ВЛ 10 кВ на бетонных опорах; одна опора
упала поперёк обочины верхом на полосу трассы, провода от соседних опор тянутся к ней и лежат на асфальте. По сторонам — деревья
и кусты из локации 2 (derevya.glb, kusty.glb).

Запуск (из корня проекта):
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/build_highway.py

Результат:
    public/models/highway.glb   — сцена для игры (http://localhost:5173/highway)
    blender/highway_base.blend  — исходник; скрипт перезаписывает его при каждом запуске

Оси Blender: X — вдоль трассы, Y — поперёк (линия на −Y), Z — вверх. Имена, которые читает игра, — как в build_city.py.
"""

import math
import os
import random
import sys

import bpy
from mathutils import Vector as V

sys.path.insert(0, os.path.dirname(__file__))
import build_city as city  # noqa: E402
from lowpoly import M, MB, empty, mat, principled  # noqa: E402

ROOT = city.ROOT
OUT_GLB = os.path.join(ROOT, "public", "models", "highway.glb")
OUT_BLEND = os.path.join(ROOT, "blender", "highway_base.blend")
VAN_GLB = os.path.join(ROOT, "blender", "assets", "furgonkt_van.glb")  # фургон Казахтелекома из локации 1
TRAKTOR_GLB = os.path.join(ROOT, "blender", "assets", "traktor_kabeleukladchik.glb")
ZEMLYA_GLB = os.path.join(ROOT, "blender", "assets", "zemlya_trava.glb")  # плитка газона (prep_zemlya.py)
TRAVA_TOP = os.path.join(ROOT, "blender", "assets", "trava_top.jpg")      # та же плитка сверху — дальняя земля
ASFALT_GLB = os.path.join(ROOT, "blender", "assets", "asfalt.glb")        # кусок дороги с бордюрами (prep_asfalt.py)

X0, X1 = -260, 300           # трасса по X
ROAD = 3.6                   # полуширина проезжей части
SHOULDER = 5.4               # край обочины
# Дорога — плитки asfalt.glb подряд вдоль X: асфальт ±ROAD с белыми краевыми линиями, бордюры с травой до ±CURB;
# за бордюром до SHOULDER — гравий. Поверхность асфальта на ROAD_Z
ASFALT_LEN = 9.75
ASFALT_STEP = 9.7            # чуть меньше длины плитки — без щелей
CURB = 4.3
ROAD_Z = 0.03
LINE_Y = -9.5                # ось ВЛ
POLE_XS = list(range(-200, 281, 40))
POLE_H = 10.0
ARM_Z = 9.3
PHASES = (-0.7, 0.0, 0.7)    # три провода 10 кВ по траверсе
SAG = 1.1
WIRE_R = 0.02
FALLEN_X = 40                # эта опора упала
FALLEN_TOP = V((35.0, -1.6, 0.12))  # куда лёг её верх — на ближнюю полосу трассы

# Плитки газона 6 × 6,42 м — вдоль маршрута игрока по обе стороны трассы; дальше — плоская земля с текстурой
# той же плитки (повтор каждые TILE_TOP м). Шаг чуть меньше плитки — края плиток неровные, щелей не остаётся
TILE_STEP = (5.85, 6.25)
TILE_X = (-66, 84)
TILE_ROWS = [-1, -2, -3, 1, 2]    # ряды от края обочины: −Y — сторона линии, +Y — за встречной полосой
TILE_TOP = 6.0 * 0.8
VAN_POS = (-22.0, -5.6)  # целиком за бордюром дороги
# Кабелеукладчик за линией ВЛ (справа по ходу игрока), идёт вдоль трассы барабаном вперёд (+X); за ножом —
# полоса вскопанной земли с кабелем
TRAKTOR_POS = (-2.0, -14.5)
TRAKTOR_LEN = 7.3
TRENCH_FROM = -60.0       # фургон мастера на обочине перед точкой A, мордой по ходу движения (+X)

random.seed(5)


def materials():
    city.city_materials()
    M["gravel"] = mat("Обочина", "#9A9284", rough=1.0)
    M["pole"] = mat("Бетон опоры", "#A9A6A0", rough=0.9)
    M["porcelain"] = mat("Изолятор", "#E9EEF2", rough=0.25)
    M["wire"] = mat("Провод", "#3F4246", rough=0.45, metal=0.7)
    M["post"] = mat("Столбик", "#F2F2F0", rough=0.6)


def build_ground():
    """Дальняя земля — один большой прямоугольник с текстурой газона, повторённой каждые TILE_TOP м"""
    m = bpy.data.materials.new("Газон")
    m.use_nodes = True
    b = principled(m.node_tree)
    tex = m.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(TRAVA_TOP)
    m.node_tree.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
    x0, x1, y0, y1 = X0 - 300, X1 + 300, -400, 400
    me = bpy.data.meshes.new("ground")
    me.from_pydata([(x0, y0, -0.01), (x1, y0, -0.01), (x1, y1, -0.01), (x0, y1, -0.01)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for loop, (x, y) in zip(uv.data, ((x0, y0), (x1, y0), (x1, y1), (x0, y1))):
        loop.uv = (x / TILE_TOP, y / TILE_TOP)
    me.materials.append(m)
    bpy.context.collection.objects.link(bpy.data.objects.new("ground", me))

    # Плитки — копии одной модели (меш и текстуры общие), повёрнуты на 0/90/180/270°, чтобы не было рисунка
    first = None
    n = 0
    for row in TILE_ROWS:
        s = 1 if row > 0 else -1
        y = s * (SHOULDER - 0.1 + (abs(row) - 0.5) * TILE_STEP[1])
        x = TILE_X[0]
        while x <= TILE_X[1]:
            name, rz = f"zemlya_{n}", random.choice((0, 1, 2, 3)) * math.pi / 2
            n += 1
            if first is None:
                first = city.place_model(ZEMLYA_GLB, name, (x, y), rz, base_z=0, solid=False)
                root0 = first[0].parent
                root0.location.z = 0  # поверхность газона на нуле, грунт ниже
            else:
                r = root0.copy()
                r.name = name
                r.location = (x, y, 0)
                r.rotation_euler.z = rz
                bpy.context.collection.objects.link(r)
                for o in first:
                    c = o.copy()
                    c.parent = r
                    bpy.context.collection.objects.link(c)
            x += TILE_STEP[0]
    print("плиток газона:", n)


def build_road():
    # Плитки дороги — копии одной модели (меш и текстуры общие); через одну развёрнуты на 180°, чтобы
    # камешки на асфальте и трава на бордюрах не шли одинаковым рисунком
    first = None
    for n in range(int((X1 - X0) / ASFALT_STEP) + 1):
        x = X0 + ASFALT_LEN / 2 + n * ASFALT_STEP
        name, rz = f"asfalt_{n}", math.pi * (n % 2)
        if first is None:
            first = city.place_model(ASFALT_GLB, name, (x, 0), rz, solid=False)
            root0 = first[0].parent
            root0.location.z = ROAD_Z  # поверхность асфальта на ROAD_Z, грунт плитки — под землёй
            continue
        r = root0.copy()
        r.name = name
        r.location = (x, 0, ROAD_Z)
        r.rotation_euler.z = rz
        bpy.context.collection.objects.link(r)
        for o in first:
            c = o.copy()
            c.parent = r
            bpy.context.collection.objects.link(c)
    r = MB("road")
    for s in (-1, 1):
        y0, y1 = sorted((s * CURB, s * SHOULDER))
        r.span(X0, y0, 0.0, X1, y1, 0.02, M["gravel"])
    for x in range(X0, X1, 12):  # прерывистая осевая — краевые линии есть на плитке
        r.span(x, -0.07, ROAD_Z, x + 6, 0.07, ROAD_Z + 0.004, M["marking"])
    r.build()
    posts = MB("road_posts")  # сигнальные столбики по краю обочины
    for s in (-1, 1):
        for x in range(X0 + 5, X1, 25):
            p = (x + (12 if s > 0 else 0), s * (SHOULDER - 0.2))
            posts.box((*p, 0.5), (0.12, 0.12, 1.0), M["post"])
            posts.box((p[0], p[1] - s * 0.065, 0.85), (0.08, 0.01, 0.16), M["hazard"])
    posts.build()


def wire(mb, pts):
    for a, b in zip(pts, pts[1:]):
        mb.cyl(a, b, WIRE_R, WIRE_R, M["wire"], n=5)


def sagging(a, b, n=14, sag=SAG):
    return [a.lerp(b, k / n) - V((0, 0, sag * 4 * (k / n) * (1 - k / n))) for k in range(n + 1)]


def insulator(x, dy):
    return V((x, LINE_Y + dy, ARM_Z + 0.25))


def pole(mb, base, top, arm_dir):
    """Опора от base до top; траверса поперёк линии (arm_dir — направление траверсы), изоляторы сверху"""
    mb.cyl(base, top, 0.17, 0.11, M["pole"], n=6)
    up = (top - base).normalized()
    arm_c = base + up * (ARM_Z - 0.05)
    mb.beam(arm_c - arm_dir * 1.0, arm_c + arm_dir * 1.0, 0.1, 0.1, M["metal"])
    tips = []
    for dy in PHASES:
        p = arm_c + arm_dir * dy + up * 0.05
        mb.cyl(p, p + up * 0.12, 0.05, 0.05, M["metal"], n=6)
        mb.cyl(p + up * 0.12, p + up * 0.25, 0.08, 0.05, M["porcelain"], n=8)
        tips.append(p + up * 0.25)
    return tips


def build_line():
    mb = MB("power_line")
    for i, x in enumerate(POLE_XS):
        if x == FALLEN_X:
            continue
        p = MB(f"wall_pole_{i}")
        pole(p, V((x, LINE_Y, 0)), V((x, LINE_Y, POLE_H)), V((0, 1, 0)))
        p.build()
    for a, b in zip(POLE_XS, POLE_XS[1:]):
        if FALLEN_X in (a, b):
            continue
        for dy in PHASES:
            wire(mb, sagging(insulator(a, dy), insulator(b, dy)))
    mb.build()


def build_fallen():
    """Упавшая опора: сломана у основания (пенёк с торчащей арматурой), лежит верхом к трассе.
    Провода от соседних опор провисают до земли и лежат на ней — осмотр издалека, не ближе 8 м"""
    base = V((FALLEN_X, LINE_Y, 0.0))
    stump = MB("pole_stump")
    stump.cyl(base, base + V((0, 0, 0.6)), 0.17, 0.165, M["pole"], n=6)
    for k in range(5):
        a = k * 2 * math.pi / 5
        p = base + V((math.cos(a) * 0.1, math.sin(a) * 0.1, 0.6))
        stump.cyl(p, p + V((math.cos(a) * 0.15, math.sin(a) * 0.15, 0.25 + 0.1 * (k % 2))), 0.012, 0.012, M["rebar"], n=4)
    stump.build()

    lie_base = base + V((-0.4, 0.6, 0.17))
    d = (FALLEN_TOP - lie_base).normalized()
    top = lie_base + d * (POLE_H - 0.6)
    arm = V((-d.y, d.x, 0)).normalized()  # траверса легла плашмя
    mb = MB("item_pole-down")
    tips = pole(mb, lie_base, top, arm)
    for t in tips:  # изоляторы лежат на земле
        t.z = max(t.z, 0.1)
    mb.build()["inspect_range"] = 8.0

    wires = MB("item_wires-ground")
    for nb in (FALLEN_X - 40, FALLEN_X + 40):
        for dy, t in zip(PHASES, tips):
            a = insulator(nb, dy)
            # провод опускается от соседней опоры и последние метры лежит на земле
            touch = t.lerp(a, 0.35)
            touch.z = 0.04
            # висит от изолятора и плавно ложится на землю у места касания: z = h·(1 − k)²
            pts = [a.lerp(touch, k / 12) for k in range(12)]
            for k, p in enumerate(pts):
                p.z = 0.04 + (a.z - 0.04) * (1 - k / 12) ** 2
            pts += [touch, t]
            wire(wires, pts)
    wires.build()["inspect_range"] = 8.0


def build_trees():
    trees, kusty = [], []
    for side in (-1, 1):
        x = X0
        while x < X1:
            x += random.uniform(5, 11)
            near = 20 if side < 0 else 9  # справа по ходу (−Y) — лесополоса за линией и кабелеукладчиком
            y = side * random.uniform(near, near + 9)
            trees.append((random.choice(("tree_bereza", "tree_bereza", "tree_topol", "tree_el", "tree_el")), x, y, 0.0,
                          random.uniform(0.8, 1.15), random.uniform(0, 2 * math.pi), None))
            if random.random() < 0.6:  # лесополоса — второй ряд
                trees.append((random.choice(("tree_el", "tree_bereza")), x + random.uniform(-3, 3),
                              y + side * random.uniform(8, 16), 0.0, random.uniform(0.9, 1.3),
                              random.uniform(0, 2 * math.pi), None))
            if random.random() < 0.35:
                kusty.append((random.choice(("kusty_para", "kust_na_podlozhke")), x + random.uniform(-2, 2),
                              side * (random.uniform(7, near - 1) if side > 0 else random.uniform(18, 21)), -0.15, 1.0, random.uniform(0, 2 * math.pi), None))
    city.clone_parts(city.DEREVYA_GLB, trees)
    city.clone_parts(city.KUSTY_GLB, kusty)


def place_traktor():
    city.place_model(TRAKTOR_GLB, "wall_traktor", TRAKTOR_POS, math.pi / 2, smooth=True)  # −Y модели → +X сцены
    soil = mat("Вскопанная земля", "#5B4330", rough=1.0)
    tail = TRAKTOR_POS[0] - TRAKTOR_LEN / 2 + 0.4  # нож-плуг
    mb = MB("trench")
    mb.span(TRENCH_FROM, TRAKTOR_POS[1] - 0.35, -0.02, tail, TRAKTOR_POS[1] + 0.35, 0.06, soil)
    for x in range(int(TRENCH_FROM), int(tail), 2):  # отвалы земли по краям
        for s in (-1, 1):
            mb.blob((x + random.uniform(0, 1.5), TRAKTOR_POS[1] + s * 0.45, 0.05), random.uniform(0.18, 0.3), soil,
                    scale=(1.6, 1, 0.5), seg=6, rings=4)
    mb.build()


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    materials()
    build_ground()
    build_road()
    build_line()
    build_fallen()
    build_trees()
    place_traktor()
    city.place_model(VAN_GLB, "wall_van", VAN_POS, math.pi, smooth=True)  # rz = π — мордой на +X, как в локации 1

    empty("spawn_A", (-30.0, -SHOULDER + 0.6, 0))  # на обочине со стороны линии
    empty("goal_B", (FALLEN_X - 32.0, -SHOULDER + 0.6, 0))  # ~15 м до проводов на земле, провод над ней — выше 4 м
    empty("walk_min", (-80, -16, 0))
    empty("walk_max", (130, 9, 0))

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_extras=True, export_apply=True)


build()
print("Готово:", OUT_GLB, OUT_BLEND)
