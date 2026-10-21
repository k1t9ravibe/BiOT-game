"""
Сельский ландшафт для режима ходьбы: рельеф, грунтовая дорога, газон, усадьба, заборы, деревья,
ВЛ 10 кВ вдоль дороги (бетонные опоры, изоляторы, провода).
Фургон, КТПН с монтёром, сумка с огнетушителем, посторонние и усадьба берутся готовыми из blender/assets
(furgonkt_van.glb, ktpn_monter.glb, sumka_ognetushitel.glb, muzhik_pes_pacan.glb, усадьбы aul_dom1.glb /
aul_dom2.glb, магазин, детская площадка, машины — их готовят prep_furgon.py, prep_ktpn.py, prep_static.py),
грунтовка — плитки selskaya_doroga.glb (prep_doroga.py). Газон — сгенерированная плитка zemlya_trava.glb
с кочками травы и камнями на ровной части и её вид сверху trava_top.jpg на всём рельефе (prep_zemlya.py).
АТС и людей сюда не ставим: их добавляют вручную в Blender, места помечены пустышками place_*.

Запуск (из корня проекта):
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/build_landscape.py

Результат:
    public/models/landscape.glb   — сцена для игры, смотреть на http://localhost:5173/walk?scene=landscape
    blender/landscape_base.blend  — исходник. Скрипт перезаписывает его при каждом запуске, поэтому
                                    свою работу сохраняйте под другим именем (File → Save As → village.blend).

Ограничения движка (src/walk/engine.ts): игрок ходит по плоскости z = 0 в квадрате ±24 м,
поэтому центр 60×60 м ровный, а холмы начинаются за его границей.
Имена объектов — как в build_t1.py: wall_* и свойство solid = 1 — препятствия, spawn_A / goal_B — старт и финиш.
"""

import math
import os
import random

import bmesh
import bpy
from mathutils import Matrix
from mathutils import Vector as V
from mathutils import noise

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_GLB = os.path.join(ROOT, "public", "models", "landscape.glb")
OUT_BLEND = os.path.join(ROOT, "blender", "landscape_base.blend")
VAN_GLB = os.path.join(ROOT, "blender", "assets", "furgonkt_van.glb")
KTPN_GLB = os.path.join(ROOT, "blender", "assets", "ktpn_monter.glb")
SUMKA_GLB = os.path.join(ROOT, "blender", "assets", "sumka_ognetushitel.glb")
MUZHIK_GLB = os.path.join(ROOT, "blender", "assets", "muzhik_pes_pacan.glb")
DUKEN_GLB = os.path.join(ROOT, "blender", "assets", "duken.glb")
PLOSHADKA_GLB = os.path.join(ROOT, "blender", "assets", "detskaya_ploshadka.glb")
VAZ07_GLB = os.path.join(ROOT, "blender", "assets", "vaz07.glb")  # легковые мордой к −X модели
AUDI_GLB = os.path.join(ROOT, "blender", "assets", "audi.glb")
VAZ14_GLB = os.path.join(ROOT, "blender", "assets", "vaz14.glb")
DOROGA_GLB = os.path.join(ROOT, "blender", "assets", "selskaya_doroga.glb")  # плитка грунтовки (prep_doroga.py)
DEREVYA_GLB = os.path.join(ROOT, "blender", "assets", "derevya.glb")  # tree_bereza, tree_topol, tree_el (prep_trees.py)
AUL_GLB = {"aul1": os.path.join(ROOT, "blender", "assets", "aul_dom1.glb"),   # усадьба 17,65 × 18,57 м
           "aul2": os.path.join(ROOT, "blender", "assets", "aul_dom2.glb")}   # усадьба 14,96 × 14,92 м
ZEMLYA_GLB = os.path.join(ROOT, "blender", "assets", "zemlya_trava.glb")  # плитка газона (prep_zemlya.py)
TRAVA_TOP = os.path.join(ROOT, "blender", "assets", "trava_top.jpg")      # та же плитка сверху — текстура рельефа

random.seed(7)
rad = math.radians

SIZE = 160        # сторона участка земли, м
CELLS = 140       # клеток сетки рельефа по стороне
FLAT = 30         # до этого расстояния от центра земля строго ровная
ROAD_Y = -10      # ось грунтовой дороги (идёт вдоль X)
ROAD_TILE = (12.8, 0.02)  # шаг плиток selskaya_doroga (13,04 × 6 м — чуть внахлёст) и высота полотна над землёй
# Аульные усадьбы aul_dom1 / aul_dom2 (дом, сараи, огород, забор на земляной подложке), воротами к дороге;
# подложка чуть утоплена в землю. Полуразмеры по X и Y модели
AUL_HALF = {"aul1": (8.83, 9.29), "aul2": (7.48, 7.46)}
AUL_SINK = 0.1
YARD = (3.5, 0.3, 18.5, 15.2)  # участок ближней усадьбы (aul2 правее детской площадки): x0, y0, x1, y1
CAR_POS = (-2.0, ROAD_Y + 3.4)  # фургон на обочине вдоль дороги, у него — точка B
KTPN_POS = (-13.0, -2.4)  # КТПН у дороги, левее фургона, ~20 м от дома, двери к дороге
# Фасад и правый край корпуса КТПН: от них стоят сумка с огнетушителем и посторонние. Корпус ktpn_monter.glb
# 3,44 × 2,69 м стоит от правого края влево и от фасада назад; распахнутые створки выходят к дороге на ~1 м,
# правая — ещё на ~0,9 м вправо; монтёр стоит в проёме
KTPN_FRONT_Y = KTPN_POS[1] - 2.2
KTPN_RIGHT_X = KTPN_POS[0] + 2.17
KTPN_SIZE = (3.44, 2.69)
# Магазин duken.glb (9 × 6,9 м) за КТПН, вывеской и дверью к дороге; фасад на y = 6 — между ним и КТПН парковка
DUKEN_POS = (-11.5, 9.45)
DUKEN_HALF = (4.5, 3.45)
# Детская площадка detskaya_ploshadka.glb (8,1 × 9,6 м) правее магазина, до забора усадьбы, входом к дороге
PLOSHADKA_POS = (-2.0, 10.8)
PLOSHADKA_HALF = (4.05, 4.8)
# ВАЗ-2107 перед магазином мордой к нему, на обочине левее КТПН — Audi и ВАЗ-2114
CARS = [(VAZ07_GLB, "wall_vaz07", (-8.4, 2.2), -math.pi / 2),  # мордой к магазину
        (AUDI_GLB, "wall_audi", (-29.0, ROAD_Y + 3.3), math.pi),               # мордой по +X вдоль дороги
        (VAZ14_GLB, "wall_vaz14", (-35.0, ROAD_Y + 3.3), math.pi)]
CAR_HALF = (2.3, 1.1)  # полуразмеры легковой вдоль и поперёк
# Усадьбы у дороги, виды через одну: x, y, поворот, вид; при rz = 0 ворота смотрят на дорогу с севера, при π —
# с юга, из-за жердевого забора. Первая — ближняя, на участке YARD. Под каждой рельеф выровнен в площадку
FAR_HOUSES = [((YARD[0] + YARD[2]) / 2, YARD[1] + AUL_HALF["aul2"][1], 0, "aul2"),
              (-47, ROAD_Y + 4.5 + AUL_HALF["aul1"][1], 0, "aul1"),
              (42, ROAD_Y + 4.5 + AUL_HALF["aul2"][1], 0, "aul2"),
              (-31, ROAD_Y - 4.8 - AUL_HALF["aul2"][1], math.pi, "aul2"),
              (52, ROAD_Y - 4.8 - AUL_HALF["aul1"][1], math.pi, "aul1")]
PAD_MARGIN, PAD_BLEND = 1.5, 4.0  # ровная кромка вокруг дома и ширина плавного перехода к склону, м
# Плитки газона zemlya_trava.glb (6 × 6,42 м, поверхность на z = 0): шаг чуть меньше плитки — края неровные, щелей
# не остаётся. Кладутся только на ровную часть (|x|, |y| ≤ TILE_LIMIT), чуть выше земли, чтобы не мерцали.
# Рельеф под ними и вокруг покрыт видом плитки сверху, повторённым каждые TILE_TOP м
TILE_HALF = (3.0, 3.21)
TILE_STEP = (5.85, 6.25)
TILE_LIMIT = 26.0
TILE_Z = 0.012
TILE_TOP = 6.0 * 0.8


# ---------- Цвета и материалы ----------

def srgb(h):
    """#RRGGBB → линейный цвет (так его ждёт glTF)"""
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def principled(nt):
    """Узел Principled BSDF; ищем по типу — в русском интерфейсе Blender он называется иначе"""
    return next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")


def mat(name, hex_color, rough=0.85, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = principled(m.node_tree)
    col = (*srgb(hex_color), 1)
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    m.diffuse_color = col
    return m


def vcol_mat(name, rough=0.95):
    """Материал, цвет которого берётся из цвета вершин (атрибут Col): земля, дорога, трава"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = principled(nt)
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Col"
    nt.links.new(vc.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    return m


M = {}


def materials():
    M.update(
        ground=vcol_mat("Земля"),
        plaster=mat("Побелка", "#EEEAE0"),
        plinth=mat("Цоколь", "#7E8288"),
        roof=mat("Кровля", "#3F7A6A", rough=0.5, metal=0.3),
        roof_shed=mat("Шифер", "#8E949A", rough=0.7),
        trim=mat("Наличники", "#F7F7F2", rough=0.6),
        shutter=mat("Ставни", "#2F6FB8", rough=0.6),
        gable=mat("Фронтон", "#5A8FC0", rough=0.7),
        glass=mat("Стекло", "#2D4B6E", rough=0.15),
        door=mat("Дверь", "#6B4026", rough=0.7),
        brick=mat("Кирпич", "#A65A3C"),
        concrete=mat("Бетон", "#9A9D a2".replace(" ", "")),
        wood=mat("Дерево", "#8A6440"),
        wood_dark=mat("Тёмное дерево", "#5E4630"),
        wood_old=mat("Старое дерево", "#8C8170"),
        ladder=mat("Лестница", "#C99A4B"),
        picket=mat("Штакетник", "#4F86C6", rough=0.7),
        stone=mat("Камень", "#B3AA9A"),
        soil=mat("Грядки", "#5B4430"),
        sprout=mat("Всходы", "#5FA83A"),
        bark=mat("Кора", "#5A4232"),
        birch=mat("Берёза", "#E9E5DA"),
        birch_mark=mat("Берёза пятна", "#2E2B28"),
        leaf=mat("Листва", "#4F8A2E"),
        leaf_light=mat("Листва светлая", "#7DB247"),
        pine=mat("Хвоя", "#2F5E33"),
        apple=mat("Яблоки", "#C8322B", rough=0.5),
    )


# ---------- Построитель мешей: много деталей в одном объекте, без bpy.ops ----------

# Грани куба; вершина i: бит 0 → +x, бит 1 → +y, бит 2 → +z
BOX_FACES = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]


class MB:
    def __init__(self, name):
        self.name = name
        self.v, self.c, self.f, self.fm, self.mats = [], [], [], [], []

    def _mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def poly(self, pts, faces, m, cols=None):
        base = len(self.v)
        self.v += [tuple(p) for p in pts]
        self.c += cols or [None] * len(pts)
        mi = self._mi(m)
        for f in faces:
            self.f.append(tuple(base + i for i in f))
            self.fm.append(mi)

    def box(self, c, size, m, rz=0.0, axes=None):
        """Брусок с центром c и размерами size; rz — поворот вокруг вертикали, axes — свои оси (правая тройка)"""
        if axes is None:
            cz, sz = math.cos(rz), math.sin(rz)
            axes = (V((cz, sz, 0)), V((-sz, cz, 0)), V((0, 0, 1)))
        ax, ay, az = axes
        hx, hy, hz = (s / 2 for s in size)
        c = V(c)
        pts = [c + ax * (hx if i & 1 else -hx) + ay * (hy if i & 2 else -hy) + az * (hz if i & 4 else -hz) for i in range(8)]
        self.poly(pts, BOX_FACES, m)

    def beam(self, p1, p2, w, d, m, side=None):
        """Брусок между точками p1 и p2 сечением w×d; side — направление ширины"""
        p1, p2 = V(p1), V(p2)
        z = p2 - p1
        length = z.length
        z.normalize()
        x = V(side) if side else (V((0, 0, 1)).cross(z) if abs(z.z) < 0.99 else V((1, 0, 0)))
        x = (x - z * x.dot(z)).normalized()
        self.box((p1 + p2) / 2, (w, d, length), m, axes=(x, z.cross(x), z))

    def cyl(self, p1, p2, r1, r2, m, n=8):
        """Цилиндр или конус (r2 = 0) от p1 до p2"""
        p1, p2 = V(p1), V(p2)
        z = (p2 - p1).normalized()
        x = V((1, 0, 0)) if abs(z.x) < 0.9 else V((0, 1, 0))
        x = (x - z * x.dot(z)).normalized()
        y = z.cross(x)
        ring = [x * math.cos(2 * math.pi * i / n) + y * math.sin(2 * math.pi * i / n) for i in range(n)]
        pts = [p1 + d * r1 for d in ring]
        if r2 == 0:
            pts.append(p2)
            faces = [(i, (i + 1) % n, n) for i in range(n)]
        else:
            pts += [p2 + d * r2 for d in ring]
            faces = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
            faces.append(tuple(range(n, 2 * n)))
        faces.append(tuple(reversed(range(n))))
        self.poly(pts, faces, m)

    def blob(self, c, r, m, scale=(1, 1, 1), seg=8, rings=6, bump=0.15):
        """Неровная сфера — крона дерева, куст"""
        c = V(c)
        pts = [c + V((0, 0, -r * scale[2]))]
        for i in range(1, rings):
            phi = math.pi * i / rings - math.pi / 2
            for j in range(seg):
                th = 2 * math.pi * j / seg
                k = r * (1 + random.uniform(-bump, bump))
                pts.append(c + V((math.cos(phi) * math.cos(th) * k * scale[0],
                                  math.cos(phi) * math.sin(th) * k * scale[1],
                                  math.sin(phi) * k * scale[2])))
        pts.append(c + V((0, 0, r * scale[2])))
        top = len(pts) - 1
        ringv = lambda i, j: 1 + (i - 1) * seg + j % seg
        faces = [(0, ringv(1, j + 1), ringv(1, j)) for j in range(seg)]
        for i in range(1, rings - 1):
            faces += [(ringv(i, j), ringv(i, j + 1), ringv(i + 1, j + 1), ringv(i + 1, j)) for j in range(seg)]
        faces += [(top, ringv(rings - 1, j), ringv(rings - 1, j + 1)) for j in range(seg)]
        self.poly(pts, faces, m)

    def build(self, smooth_shade=False, recalc=True, solid=False):
        me = bpy.data.meshes.new(self.name)
        me.from_pydata(self.v, [], self.f)
        for m in self.mats:
            me.materials.append(m)
        me.polygons.foreach_set("material_index", self.fm)
        if any(c is not None for c in self.c):
            attr = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
            flat = []
            for c in self.c:
                flat += [*(c or (1, 1, 1)), 1.0]
            attr.data.foreach_set("color", flat)
            try:
                me.color_attributes.active_color = attr
            except AttributeError:
                pass
        if recalc:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(me)
            bm.free()
        me.polygons.foreach_set("use_smooth", [smooth_shade] * len(me.polygons))
        me.update()
        o = bpy.data.objects.new(self.name, me)
        bpy.context.collection.objects.link(o)
        if solid:
            o["solid"] = 1
        return o


def empty(name, loc):
    o = bpy.data.objects.new(name, None)
    o.empty_display_type = "PLAIN_AXES"
    o.empty_display_size = 1.0
    o.location = loc
    bpy.context.collection.objects.link(o)
    return o


# ---------- Рельеф ----------

def nz(x, y, s, off=0.0):
    return noise.noise(V((x / s, y / s, off)))


def height_raw(x, y):
    """Высота земли без площадок под домами: ровный центр, холмы за его границей, долина под дорогой"""
    edge = max(abs(x), abs(y)) + 4 * nz(x, y, 30, 0.5)
    f = smooth(FLAT, FLAT + 22, edge)
    if f == 0:
        return 0.0
    valley = smooth(3, 14, abs(y - ROAD_Y))
    hills = 5 + 9 * (0.5 + 0.5 * nz(x, y, 35, 1.7)) + 2.5 * nz(x, y, 12, 3.1)
    return f * valley * hills


def pad_distance(x, y, house):
    """Насколько точка дальше от стен дома (по осям дома), чем ровная кромка площадки; внутри — 0"""
    hx, hy, rz, kind = house
    c, s = math.cos(rz), math.sin(rz)
    lx, ly = (x - hx) * c + (y - hy) * s, -(x - hx) * s + (y - hy) * c
    dx = max(0.0, abs(lx) - AUL_HALF[kind][0] - PAD_MARGIN)
    dy = max(0.0, abs(ly) - AUL_HALF[kind][1] - PAD_MARGIN)
    return math.hypot(dx, dy)


# Площадка — на уровне самой низкой точки под домом: в гору дом врезан в выемку, под гору склон не отсыпается
PAD_LEVELS = [min(height_raw(h[0] + dx, h[1] + dy) for dx in range(-10, 11) for dy in range(-10, 11)
                  if pad_distance(h[0] + dx, h[1] + dy, h) == 0) for h in FAR_HOUSES]


def height(x, y):
    """Высота земли с ровными площадками под дальними домами"""
    h = height_raw(x, y)
    for house, level in zip(FAR_HOUSES, PAD_LEVELS):
        d = pad_distance(x, y, house)
        if d < PAD_BLEND:
            h = level + (h - level) * smooth(0, PAD_BLEND, d)
    return h


def build_ground():
    """Рельеф с текстурой газона trava_top.jpg (вид сверху плитки zemlya_trava), повторённой каждые TILE_TOP м"""
    m = bpy.data.materials.new("Газон")
    m.use_nodes = True
    b = principled(m.node_tree)
    tex = m.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(TRAVA_TOP)
    m.node_tree.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95

    mb = MB("ground")
    n = CELLS + 1
    step = SIZE / CELLS
    pts = [(x, y, height(x, y)) for y in (-SIZE / 2 + j * step for j in range(n))
           for x in (-SIZE / 2 + i * step for i in range(n))]
    faces = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i) for j in range(CELLS) for i in range(CELLS)]
    mb.poly(pts, faces, m)
    o = mb.build(smooth_shade=True, recalc=False)
    uv = o.data.uv_layers.new()
    for loop, l in zip(uv.data, o.data.loops):
        x, y, _ = pts[l.vertex_index]
        loop.uv = (x / TILE_TOP, y / TILE_TOP)
    return o


def build_road():
    """Грунтовка вдоль X — плитки selskaya_doroga.glb подряд (меш и текстуры общие), через одну развёрнуты на 180°,
    чтобы рисунок не повторялся; полотно чуть над землёй (рельеф под дорогой ровный)"""
    first, x, n = None, -SIZE / 2, 0
    while x - ROAD_TILE[0] / 2 < SIZE / 2:
        name, rz = f"road_{n}", math.pi * (n % 2)
        if first is None:
            first = place_model(DOROGA_GLB, name, (x, ROAD_Y), rz, solid=False, fit_logos=False)
            root0 = first[0].parent
            root0.location.z = ROAD_TILE[1]
        else:
            r = root0.copy()
            r.name = name
            r.location = (x, ROAD_Y, ROAD_TILE[1])
            r.rotation_euler.z = rz
            bpy.context.collection.objects.link(r)
            for o in first:
                c = o.copy()
                c.parent = r
                bpy.context.collection.objects.link(c)
        x, n = x + ROAD_TILE[0], n + 1


# ---------- Газон: плитки zemlya_trava ----------

def tile_blocked(x, y):
    """Плитка с центром (x, y) не кладётся, если задевает грунтовку или если её центр — под усадьбой (у неё своя
    трава), магазином, детской площадкой или машиной. Вокруг КТПН газон есть"""
    hx, hy = TILE_HALF
    if y - hy < ROAD_Y + 3.0 and y + hy > ROAD_Y - 3.0:  # грунтовка с камнями по краям
        return True
    zones = [
        YARD,
        (CAR_POS[0] - 2.9, CAR_POS[1] - 1.25, CAR_POS[0] + 2.9, CAR_POS[1] + 1.25),
        (DUKEN_POS[0] - DUKEN_HALF[0], DUKEN_POS[1] - DUKEN_HALF[1], DUKEN_POS[0] + DUKEN_HALF[0], DUKEN_POS[1] + DUKEN_HALF[1]),
        (PLOSHADKA_POS[0] - PLOSHADKA_HALF[0], PLOSHADKA_POS[1] - PLOSHADKA_HALF[1],
         PLOSHADKA_POS[0] + PLOSHADKA_HALF[0], PLOSHADKA_POS[1] + PLOSHADKA_HALF[1]),
    ]
    for _, _, (cx, cy), rz in CARS:
        ax, ay = CAR_HALF if abs(math.cos(rz)) > 0.5 else CAR_HALF[::-1]
        zones.append((cx - ax, cy - ay, cx + ax, cy + ay))
    return any(x0 < x < x1 and y0 < y < y1 for x0, y0, x1, y1 in zones)


def build_grass_tiles():
    """Плитки — копии одной модели (меш и текстуры общие), повёрнуты на 0/90/180/270°, чтобы не было рисунка.
    Ряды идут от обочин дороги в обе стороны"""
    rows = []
    y = ROAD_Y + 3.0 + TILE_HALF[1]
    while y + TILE_HALF[1] <= TILE_LIMIT:
        rows.append(y)
        y += TILE_STEP[1]
    y = ROAD_Y - 3.0 - TILE_HALF[1]
    while y - TILE_HALF[1] >= -TILE_LIMIT:
        rows.append(y)
        y -= TILE_STEP[1]
    rng = random.Random(11)  # свой генератор: раскладка деревьев и прочего от плиток не зависит
    first, n = None, 0
    for y in rows:
        x = -TILE_LIMIT + TILE_HALF[0]
        while x + TILE_HALF[0] <= TILE_LIMIT:
            if not tile_blocked(x, y):
                name, rz = f"zemlya_{n}", rng.choice((0, 1, 2, 3)) * math.pi / 2
                n += 1
                if first is None:
                    first = place_model(ZEMLYA_GLB, name, (x, y), rz, solid=False, fit_logos=False)
                    root0 = first[0].parent
                    root0.location.z = TILE_Z  # поверхность газона чуть над землёй, грунт плитки — под ней
                else:
                    r = root0.copy()
                    r.name = name
                    r.location = (x, y, TILE_Z)
                    r.rotation_euler.z = rz
                    bpy.context.collection.objects.link(r)
                    for o in first:
                        c = o.copy()
                        c.parent = r
                        bpy.context.collection.objects.link(c)
            x += TILE_STEP[0]
    print("плиток газона:", n)


# ---------- Заборы (каждый прямой участок — отдельный объект, чтобы коллизия была узкой) ----------

def board_fence(name, a, b):
    """Сплошной дощатый забор 1.8 м"""
    mb = MB(name)
    a, b = V((*a, 0)), V((*b, 0))
    length = (b - a).length
    t = (b - a).normalized()
    n = V((0, 0, 1)).cross(t)
    rz = math.atan2(t.y, t.x)
    for k in range(int(length / 2.5) + 1):
        mb.box(a + t * min(length, k * 2.5) + n * 0.1 + V((0, 0, 0.95)), (0.12, 0.12, 1.9), M["wood_dark"], rz=rz)
    for k in range(int(length / 0.21)):
        h = 1.8 + random.uniform(-0.04, 0.04)
        mb.box(a + t * (0.1 + k * 0.21) + V((0, 0, h / 2 + 0.05)), (0.19, 0.025, h), M["wood"] if k % 5 else M["wood_old"], rz=rz)
    return mb.build()


def rail_fence(name, a, b):
    """Жердевой забор у дороги: столбы по рельефу и две жерди с провисом"""
    mb = MB(name)
    a, b = V((*a, 0)), V((*b, 0))
    length = (b - a).length
    t = (b - a).normalized()
    steps = max(1, round(length / 3))
    tops = []
    for k in range(steps + 1):
        p = a + t * (length * k / steps)
        p.z = height(p.x, p.y)
        lean = V((random.uniform(-0.06, 0.06), random.uniform(-0.06, 0.06), 0))
        mb.cyl(p - V((0, 0, 0.3)), p + V((0, 0, 1.25)) + lean, 0.07, 0.06, M["wood_old"], n=6)
        tops.append(p + lean * 0.5)
    for z in (0.55, 1.05):
        for p, q in zip(tops, tops[1:]):
            mid = (p + q) / 2 + V((0, 0, z - random.uniform(0.02, 0.07)))
            mb.cyl(p + V((0, 0, z)), mid, 0.045, 0.045, M["wood_old"], n=5)
            mb.cyl(mid, q + V((0, 0, z)), 0.045, 0.045, M["wood_old"], n=5)
    return mb.build()


def build_fences():
    # Глухой забор соседнего участка и жерди вдоль дороги
    board_fence("wall_fence_neighbor_1", (-24, 18), (-12, 18))
    board_fence("wall_fence_neighbor_2", (-12, 18), (0, 18))
    for i, x in enumerate(range(-60, 60, 12)):
        rail_fence(f"{'wall_' if -24 <= x < 24 else ''}fence_rail_{i}", (x, ROAD_Y - 3.8), (x + 12, ROAD_Y - 3.8))


# ---------- Деревья ----------

TREE_KINDS = {"birch": "tree_bereza", "tree": "tree_topol", "pine": "tree_el"}


def build_trees():
    """Деревья — наши derevya.glb (берёза, тополь, ель; меш и текстуры общие), каждое со случайным поворотом.
    У ближних к игроку — ещё ствол-препятствие wall_trunk_* внутри ствола модели"""
    near = [("birch", -19.5, 14), ("birch", -26, 4), ("tree", 22.5, 4), ("birch", 22, 15), ("tree", -14, -20),
            ("birch", 15, -19), ("tree", -21, 21), ("pine", 21, -21)]
    spots = []
    for i, (kind, x, y) in enumerate(near):
        spots.append((kind, x, y, random.uniform(0.9, 1.15)))
        trunk = MB(f"wall_trunk_{i}")
        trunk.cyl(V((x, y, height(x, y) - 0.2)), V((x, y, height(x, y) + 2.0)), 0.12, 0.1, M["bark"], n=6)
        trunk.build()

    # Дальние деревья на холмах
    placed = 0
    while placed < 70:
        a = random.uniform(0, 2 * math.pi)
        r = random.uniform(30, 68)
        x, y = math.cos(a) * r, math.sin(a) * r
        if abs(y - ROAD_Y) < 6 or max(abs(x), abs(y)) < 27 or any(pad_distance(x, y, h) < 1 for h in FAR_HOUSES):
            continue
        spots.append((random.choice(["pine", "pine", "birch", "tree"]), x, y, random.uniform(0.9, 1.4)))
        placed += 1

    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=DEREVYA_GLB)
    tpl = {o.name.split(".")[0]: o for o in set(bpy.data.objects) - before if o.type == "MESH"}
    # Модели сохранены с осью Z вверх, импорт поворачивает их как glTF с осью Y — возвращаем, как в place_model;
    # начало координат каждого дерева — у основания ствола
    fix = Matrix.Rotation(rad(-90), 4, "X")
    local = {k: Matrix.Translation(-o.matrix_world.translation) @ o.matrix_world for k, o in tpl.items()}
    for i, (kind, x, y, sc) in enumerate(spots):
        k = TREE_KINDS[kind]
        o = tpl[k].copy()
        o.name = f"{k}_{i}"
        bpy.context.collection.objects.link(o)
        o.matrix_world = (Matrix.Translation((x, y, height(x, y) - 0.1)) @ Matrix.Rotation(random.uniform(0, 2 * math.pi), 4, "Z")
                          @ Matrix.Scale(sc, 4) @ fix @ local[k])
    for o in tpl.values():
        bpy.data.objects.remove(o)

    # Кусты вдоль соседского забора
    bushes = MB("bushes")
    for x, y in [(-22, 16.8), (-18.5, 16.9), (-9, 16.8), (-4, 16.7)]:
        for _ in range(3):
            bushes.blob((x + random.uniform(-0.5, 0.5), y + random.uniform(-0.3, 0.3), 0.4), random.uniform(0.5, 0.75),
                        M["leaf"], scale=(1.2, 1, 0.8))
    bushes.build()


# ---------- Дальние дома у дороги ----------

def build_far_houses():
    """Усадьбы FAR_HOUSES: одна модель на вид, копии делят меш и текстуры, поэтому сцена не растёт в размере"""
    first = {}
    for i, (x, y, rz, kind) in enumerate(FAR_HOUSES):
        name, z = f"wall_dom_{kind}_{i}", PAD_LEVELS[i] - AUL_SINK
        if kind not in first:
            meshes = place_model(AUL_GLB[kind], name, (x, y), rz, base_z=z, fit_logos=False)
            root0 = meshes[0].parent
            first[kind] = (meshes, root0, root0.location.z - z)
            continue
        meshes, root0, dz = first[kind]
        root = root0.copy()
        root.name = name
        root.location = (x, y, z + dz)
        root.rotation_euler.z = rz
        bpy.context.collection.objects.link(root)
        for o in meshes:
            c = o.copy()  # данные меша общие
            c.parent = root
            bpy.context.collection.objects.link(c)


# ---------- ВЛ 10 кВ вдоль дороги ----------

LINE_Y = ROAD_Y - 3.0  # опоры по другую сторону дороги от КТПН, между обочиной и жердевым забором
POLE_XS = [KTPN_POS[0] + 25 * k for k in range(-2, 4)]  # пролёт 25 м, одна опора — напротив КТПН
POLE_H = 9.0  # высота опоры над землёй


def insulator(mb, base, steel, porcelain):
    """Штыревой изолятор: стальной штырь и фарфоровая «юбка». Возвращает точку крепления провода"""
    b = V(base)
    mb.cyl(b, b + V((0, 0, 0.09)), 0.018, 0.018, steel, n=6)
    for z0, z1, r0, r1 in ((0.09, 0.13, 0.075, 0.07), (0.13, 0.20, 0.05, 0.05), (0.20, 0.24, 0.07, 0.065), (0.24, 0.30, 0.04, 0.03)):
        mb.cyl(b + V((0, 0, z0)), b + V((0, 0, z1)), r0, r1, porcelain, n=10)
    return b + V((0, 0, 0.27))


def build_power_line():
    """Опоры ВЛ 10 кВ из центрифугированного бетона: траверса с подкосами, три изолятора (два на траверсе,
    один на макушке), три провода с провисом. Ствол каждой опоры — отдельный объект-препятствие"""
    concrete = mat("Бетон опор", "#A7A9A4", rough=0.9)
    steel = mat("Траверса", "#4B5056", rough=0.5, metal=0.6)
    porcelain = mat("Изоляторы", "#E9E6DC", rough=0.3)
    wire = mat("Провод", "#2A2B2D", rough=0.5, metal=0.5)

    hw = MB("power_line_hardware")
    phases = []  # по опорам: три точки крепления проводов
    for i, x in enumerate(POLE_XS):
        z0 = height(x, LINE_Y)
        top = z0 + POLE_H
        pole = MB(f"power_pole_{i}")
        pole.cyl((x, LINE_Y, z0 - 0.4), (x, LINE_Y, top), 0.17, 0.10, concrete, n=8)
        pole.build(solid=True)

        arm_z = top - 0.7
        hw.box((x, LINE_Y, arm_z), (0.08, 1.9, 0.08), steel)  # траверса поперёк линии
        hw.box((x + 0.06, LINE_Y, arm_z - 0.05), (0.04, 0.24, 0.3), steel)  # хомут
        for s in (-1, 1):
            hw.beam((x, LINE_Y, arm_z - 0.75), (x, LINE_Y + s * 0.7, arm_z - 0.04), 0.035, 0.035, steel)
        hw.box((x, LINE_Y, top + 0.06), (0.16, 0.16, 0.12), steel)  # оголовок под верхний изолятор
        phases.append([insulator(hw, (x, LINE_Y + s * 0.85, arm_z + 0.04), steel, porcelain) for s in (-1, 1)]
                      + [insulator(hw, (x, LINE_Y, top + 0.12), steel, porcelain)])
    hw.build()

    wires = MB("power_line_wires")
    for a_pts, b_pts in zip(phases, phases[1:]):
        for a, b in zip(a_pts, b_pts):
            sag, n = 0.55, 12
            pts = [a + (b - a) * (k / n) - V((0, 0, 4 * sag * (k / n) * (1 - k / n))) for k in range(n + 1)]
            for p, q in zip(pts, pts[1:]):
                wires.beam(p, q, 0.022, 0.022, wire)
    wires.build()


# ---------- Объекты задания у КТПН: посторонние в опасной зоне, огнетушитель ----------

def build_bystanders():
    """Посторонние у открытой КТПН — нарушение «Люди и животные в опасной зоне»: мужчина присел рядом с мальчиком
    и собакой. Стоят на обочине слева от КТПН, за левой створкой, и все смотрят на КТПН"""
    place_model(MUZHIK_GLB, "item_people-animals", (KTPN_RIGHT_X - KTPN_SIZE[0] - 1.2, KTPN_FRONT_Y - 1.8),
                rad(138),  # лицом к середине КТПН
                solid=False, fit_logos=False,
                inspect=3.0)  # видно с дороги, подходить вплотную не нужно


def build_extinguisher():
    """Сумка монтёра с инструментом и огнетушитель у правого угла КТПН — правильно, отвлекающий вариант"""
    place_model(SUMKA_GLB, "item_extinguisher-ok", (KTPN_RIGHT_X + 1.6, KTPN_FRONT_Y - 0.6), 0,  # правее створки, лицом к дороге
                solid=False, fit_logos=False)


# ---------- Готовые модели: фургон, КТПН, сумка с огнетушителем, посторонние ----------

def unmirror_decal(o, center):
    """Если наклейка читается зеркально для зрителя снаружи, переворачивает её UV по горизонтали"""
    me, mw = o.data, o.matrix_world
    uv = me.uv_layers.active.data
    poly = me.polygons[0]
    loops = list(poly.loop_indices)
    pts = [mw @ me.vertices[me.loops[i].vertex_index].co for i in loops]
    us = [uv[i].uv.x for i in loops]
    du = pts[us.index(max(us))] - pts[us.index(min(us))]
    n = (mw.to_3x3() @ poly.normal).normalized()
    if n.dot(sum(pts, V()) / len(pts) - center) < 0:
        n = -n  # нормаль наружу от центра фургона
    right = (-n).cross(V((0, 0, 1)))  # «вправо» для зрителя, который смотрит на борт
    if du.dot(right) < 0:
        for l in uv:
            l.uv.x = 1 - l.uv.x


def fit_decal_aspect(o):
    """Вписывает наклейку в её прямоугольник с пропорциями картинки, чтобы логотип не был растянут"""
    img = next((n.image for m in o.data.materials if m and m.node_tree
                for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None)
    if not img or not img.size[1]:
        return
    vs = [v.co for v in o.data.vertices]
    lo = V([min(c[i] for c in vs) for i in range(3)])
    hi = V([max(c[i] for c in vs) for i in range(3)])
    size = hi - lo
    flat = min(range(3), key=lambda i: size[i])  # ось толщины наклейки
    up = 1  # в импортированной модели (ещё до поворота) высота — локальная −Y, ширина — X или Z
    across = next(i for i in range(3) if i not in (flat, up))
    want = img.size[0] / img.size[1]
    k = want / (size[across] / size[up])
    mid = (lo + hi) / 2
    for v in o.data.vertices:
        if k < 1:
            v.co[across] = mid[across] + (v.co[across] - mid[across]) * k
        else:
            v.co[up] = mid[up] + (v.co[up] - mid[up]) / k


def place_model(path, name, pos, rz, scale=1.0, base_z=0.0, solid=True, fit_logos=True, smooth=False, drop=(),
                inspect=None):
    """Ставит готовую модель из blender/assets нижней точкой на высоту base_z в точку pos, повернув на rz
    вокруг вертикали. Файлы этих моделей сохранены с осью Z вверх (а glTF ждёт Y), низ не всегда на нуле,
    логотипы бывают зеркальными или растянутыми — всё поправляется здесь. solid — модель целиком препятствие.
    При rz = 0 сторона модели, которая в файле смотрит на −Y, смотрит на −Y сцены (к дороге).
    drop — имена деталей, которые надо убрать; smooth — гладкое затенение (иначе экспорт раздувает файл)"""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in [o for o in new if o.name in drop]:
        new.remove(o)
        bpy.data.objects.remove(o)
    root = empty(name, (*pos, 0))
    root.rotation_euler = (rad(-90), 0, rz)  # сначала встаёт вертикально, потом поворачивается
    root.scale = (scale,) * 3
    if solid:
        root["solid"] = 1
    if inspect:
        root["inspect_range"] = inspect  # свой радиус осмотра для объекта задания (item_*)
    for o in new:
        if o.parent is None:
            o.parent = root
    bpy.context.view_layer.update()
    meshes = [o for o in new if o.type == "MESH"]
    root.location.z += base_z - min((o.matrix_world @ v.co).z for o in meshes for v in o.data.vertices)
    bpy.context.view_layer.update()
    center = root.matrix_world.translation
    for o in meshes:
        if "logo" in o.name.lower() and o.data.uv_layers:
            if fit_logos:
                fit_decal_aspect(o)
            unmirror_decal(o, center)
        if smooth:
            o.data.polygons.foreach_set("use_smooth", [True] * len(o.data.polygons))
            o.data.set_sharp_from_angle(angle=rad(40))
    return meshes


# ---------- Сборка ----------

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    materials()

    build_ground()
    build_road()
    build_grass_tiles()
    build_fences()
    build_trees()
    build_far_houses()
    build_power_line()
    build_bystanders()
    build_extinguisher()

    # Точки маршрута: старт на дороге, финиш у калитки
    empty("spawn_A", (-20.0, ROAD_Y, 0))  # западнее КТПН: маршрут идёт мимо КТПН к фургону
    empty("goal_B", (CAR_POS[0], CAR_POS[1] - 2.1, 0))  # на дороге у борта фургона
    # Места для объектов, которые добавляются вручную (игра их не использует)
    empty("place_ats", (-8.0, 7.0, 0))
    # Объекты задания «Улица у КТПН» (public/walk-tasks.json) называются item_<id карточки>
    place_model(VAN_GLB, "item_van-ok", CAR_POS, math.pi)  # мордой по +X вдоль дороги
    # КТПН дверями к дороге, вокруг нет ограждения. Монтёр — часть той же модели, поэтому один объект на четыре
    # карточки: не ограждена зона, без каски и в одиночку (нарушения), в диэлектрических ботах (правильно)
    place_model(KTPN_GLB, "item_zone-unfenced+no-helmet+alone+boots-ok", (KTPN_RIGHT_X, KTPN_FRONT_Y), 0,
                inspect=3.5)  # монтёр в проёме — осматривается от створок
    empty("place_worker", (-1.0, -4.0, 0))
    place_model(DUKEN_GLB, "wall_duken", DUKEN_POS, 0, fit_logos=False)  # магазин за КТПН, вывеской к дороге
    place_model(PLOSHADKA_GLB, "wall_ploshadka", PLOSHADKA_POS, 0, fit_logos=False)  # входом к дороге
    for path, name, pos, rz in CARS:
        place_model(path, name, pos, rz, fit_logos=False, smooth=True)

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_extras=True, export_apply=True)


build()
print("Готово:", OUT_GLB, OUT_BLEND)
