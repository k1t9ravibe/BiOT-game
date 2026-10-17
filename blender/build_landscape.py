"""
Сельский ландшафт для режима ходьбы: рельеф, грунтовая дорога, трава, дом с двором, заборы, лестница, деревья,
ВЛ 10 кВ вдоль дороги (бетонные опоры, изоляторы, провода).
Фургон, КТПН, монтёр и сумка с огнетушителем берутся готовыми из blender/assets (furgonkt_van.glb, ktpn1.glb,
monter_wires.glb, sumka_ognetushitel.glb — их готовят prep_furgon.py, prep_ktpn.py, prep_monter.py, prep_sumka.py).
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
KTPN_GLB = os.path.join(ROOT, "blender", "assets", "ktpn1.glb")
MONTER_GLB = os.path.join(ROOT, "blender", "assets", "monter_wires.glb")
SUMKA_GLB = os.path.join(ROOT, "blender", "assets", "sumka_ognetushitel.glb")

random.seed(7)
rad = math.radians

SIZE = 160        # сторона участка земли, м
CELLS = 140       # клеток сетки рельефа по стороне
FLAT = 30         # до этого расстояния от центра земля строго ровная
ROAD_Y = -10      # ось грунтовой дороги (идёт вдоль X)
PATH_X = 10.25    # тропинка от дороги к калитке и крыльцу
YARD = (3, 0, 19, 15)  # двор: x0, y0, x1, y1
GATE = (9.5, 11.0)     # проём калитки по X на передней стороне двора
CAR_POS = (-2.0, ROAD_Y + 3.4)  # фургон на обочине вдоль дороги, у него — точка B
KTPN_POS = (-13.0, -2.4)  # КТПН у дороги, левее фургона, ~20 м от дома, двери к дороге
# Фасад и правый край КТПН: к ним привязаны огнетушитель и посторонние. Корпус ktpn1.glb 4,6 × 1,84 м стоит
# от правого края влево и от фасада назад, распахнутая левая створка выходит к дороге на ~1,4 м
KTPN_FRONT_Y = KTPN_POS[1] - 2.2
KTPN_RIGHT_X = KTPN_POS[0] + 3.07
KTPN_SIZE = (4.6, 1.84)
PLACE_KTPN = False  # КТПН и монтёр пока убраны из сцены — ждём другую модель


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
        grass=vcol_mat("Трава"),
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


def height(x, y):
    """Высота земли: ровный центр, холмы за его границей, долина под дорогой"""
    edge = max(abs(x), abs(y)) + 4 * nz(x, y, 30, 0.5)
    f = smooth(FLAT, FLAT + 22, edge)
    if f == 0:
        return 0.0
    valley = smooth(3, 14, abs(y - ROAD_Y))
    hills = 5 + 9 * (0.5 + 0.5 * nz(x, y, 35, 1.7)) + 2.5 * nz(x, y, 12, 3.1)
    return f * valley * hills


G1, G2, G3 = srgb("#5E9F37"), srgb("#77B545"), srgb("#4A8A2C")
DRY = srgb("#A7B25A")
DIRT, DIRT_DARK, DIRT_GRASS = srgb("#9C7B55"), srgb("#76593B"), srgb("#8E9550")


def grass_color(x, y, h):
    c = lerp(G1, G2, 0.5 + 0.9 * nz(x, y, 9, 4.2))
    c = lerp(c, G3, smooth(0.25, 0.6, nz(x, y, 4, 7.7)))
    return lerp(c, DRY, h / 18 + 0.25 * smooth(0.3, 0.7, nz(x, y, 20, 9.3)))


def build_ground():
    mb = MB("ground")
    n = CELLS + 1
    step = SIZE / CELLS
    pts, cols = [], []
    for j in range(n):
        for i in range(n):
            x, y = -SIZE / 2 + i * step, -SIZE / 2 + j * step
            h = height(x, y)
            c = grass_color(x, y, h)
            # Под дорогой — грунт (сама колея — отдельный объект road)
            road = abs(y - ROAD_Y) + 0.5 * nz(x, y, 3, 5.5)
            c = lerp(DIRT, c, smooth(2.0, 3.4, road))
            # Утоптанная земля у калитки
            c = lerp(DIRT_GRASS, c, smooth(1.0, 2.5, math.hypot(x - PATH_X, y + 0.3)))
            pts.append((x, y, h))
            cols.append(c)
    faces = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i) for j in range(CELLS) for i in range(CELLS)]
    mb.poly(pts, faces, M["ground"], cols)
    return mb.build(smooth_shade=True, recalc=False)


def build_road():
    """Грунтовка вдоль X: две колеи и травяная полоса посередине"""
    mb = MB("road")
    profile = [(-2.3, DIRT_GRASS), (-1.25, DIRT), (-0.85, DIRT_DARK), (-0.45, DIRT), (0.0, DIRT_GRASS),
               (0.45, DIRT), (0.85, DIRT_DARK), (1.25, DIRT), (2.3, DIRT_GRASS)]
    xs = [x for x in range(-SIZE // 2, SIZE // 2 + 1)]
    pts, cols = [], []
    for x in xs:
        wob = 0.4 * nz(x, 0, 6, 2.2)
        for k, (v, c) in enumerate(profile):
            edge = k in (0, len(profile) - 1)
            y = ROAD_Y + v + wob + (0.35 * nz(x, v, 2.5, 6.6) if edge else 0)
            pts.append((x, y, 0.004 if edge else 0.012))
            cols.append(lerp(c, srgb("#6F8F40"), 0.25 + 0.3 * nz(x, v, 3, 8.8)) if c is DIRT_GRASS else c)
    w = len(profile)
    faces = [(r * w + k + 1, r * w + k, (r + 1) * w + k, (r + 1) * w + k + 1) for r in range(len(xs) - 1) for k in range(w - 1)]
    mb.poly(pts, faces, M["ground"], cols)
    return mb.build(smooth_shade=True, recalc=False)


# ---------- Трава и цветы ----------

def blocked_for_grass(x, y):
    if abs(y - ROAD_Y) < 2.6:
        return True
    if 6.3 < x < 15.6 and 4.0 < y < 12.8:   # дом с крыльцом
        return True
    if 15.6 < x < 18.4 and 10.8 < y < 14.2:  # сарай
        return True
    if abs(x - PATH_X) < 0.8 and -8 < y < 4.6:  # тропинка
        return True
    if 14.3 < x < 18.4 and 0.7 < y < 4.1:   # грядки
        return True
    if abs(x - CAR_POS[0]) < 2.9 and abs(y - CAR_POS[1]) < 1.25:  # место машины, трава не пробьёт кузов
        return True
    if PLACE_KTPN and -KTPN_SIZE[0] - 0.3 < x - KTPN_RIGHT_X < 0.3 and -0.3 < y - KTPN_FRONT_Y < KTPN_SIZE[1] + 0.3:  # КТПН
        return True
    return False


def build_grass():
    mb = MB("grass")
    dark, light, tall = srgb("#3E7A26"), srgb("#8CC455"), srgb("#9DB955")

    def tuft(x, y, hmin, hmax, blades, tip):
        z = height(x, y)
        for _ in range(blades):
            a = random.uniform(0, math.pi)
            w = random.uniform(0.04, 0.07)
            h = random.uniform(hmin, hmax)
            px, py = x + random.uniform(-0.12, 0.12), y + random.uniform(-0.12, 0.12)
            dx, dy = math.cos(a) * w / 2, math.sin(a) * w / 2
            lx, ly = random.uniform(-0.3, 0.3) * h, random.uniform(-0.3, 0.3) * h
            mb.poly([(px - dx, py - dy, z), (px + dx, py + dy, z), (px + lx, py + ly, z + h)], [(0, 1, 2)],
                    M["grass"], [dark, dark, lerp(light, tip, random.random())])

    placed = 0
    while placed < 3000:
        x, y = random.uniform(-34, 34), random.uniform(-34, 34)
        if blocked_for_grass(x, y):
            continue
        tuft(x, y, 0.15, 0.4, 4, light)
        placed += 1

    # Высокая трава вдоль заборов и обочин
    x0, y0, x1, y1 = YARD
    lines = [((x0, y0), (GATE[0], y0)), ((GATE[1], y0), (x1, y0)), ((x0, y0), (x0, y1)), ((x1, y0), (x1, y1)),
             ((x0, y1), (x1, y1)), ((-30, ROAD_Y - 3.6), (30, ROAD_Y - 3.6)), ((-30, ROAD_Y + 2.9), (30, ROAD_Y + 2.9))]
    for (ax, ay), (bx, by) in lines:
        length = math.hypot(bx - ax, by - ay)
        for _ in range(int(length * 4)):
            t = random.random()
            x = ax + (bx - ax) * t + random.uniform(-0.35, 0.35)
            y = ay + (by - ay) * t + random.uniform(-0.35, 0.35)
            if not blocked_for_grass(x, y) or abs(y - ROAD_Y) > 2.6:
                tuft(x, y, 0.35, 0.8, 5, tall)

    # Полевые цветы: стебель и головка
    heads = [srgb(h) for h in ("#FFFFFF", "#F4D23C", "#B07CD8", "#F5F0C8")]
    placed = 0
    while placed < 260:
        x, y = random.uniform(-30, 30), random.uniform(-30, 30)
        if blocked_for_grass(x, y) or (YARD[0] < x < YARD[2] and YARD[1] < y < YARD[3]):
            continue
        z, h, s = height(x, y), random.uniform(0.25, 0.45), random.uniform(0.05, 0.08)
        c = random.choice(heads)
        mb.poly([(x - 0.01, y, z), (x + 0.01, y, z), (x, y, z + h)], [(0, 1, 2)], M["grass"], [dark, dark, dark])
        mb.poly([(x - s, y, z + h), (x, y - s, z + h), (x + s, y, z + h), (x, y + s, z + h)], [(0, 1, 2, 3)],
                M["grass"], [c] * 4)
        placed += 1
    return mb.build(recalc=False)


# ---------- Дом ----------

def window(mb, p, n, t, zc, w=1.0, h=1.2, shutters=True):
    """Окно на стене: p — точка на поверхности стены (x, y), n — наружу, t — вдоль стены"""
    n, t = V(n), V(t)
    axes = (t, V((0, 0, 1)).cross(t), V((0, 0, 1)))
    at = lambda along, out, z: V((p[0], p[1], z)) + t * along + n * out
    mb.box(at(0, 0.02, zc), (w, 0.04, h), M["glass"], axes=axes)
    # Рама, перекладины, подоконник, наличник сверху
    mb.box(at(0, 0.05, zc + h / 2 + 0.04), (w + 0.16, 0.08, 0.08), M["trim"], axes=axes)
    mb.box(at(0, 0.08, zc - h / 2 - 0.03), (w + 0.3, 0.16, 0.06), M["trim"], axes=axes)
    for s in (-1, 1):
        mb.box(at(s * (w / 2 + 0.04), 0.05, zc), (0.08, 0.08, h + 0.16), M["trim"], axes=axes)
    mb.box(at(0, 0.04, zc), (0.05, 0.06, h), M["trim"], axes=axes)
    mb.box(at(0, 0.04, zc + h * 0.22), (w, 0.06, 0.05), M["trim"], axes=axes)
    mb.box(at(0, 0.06, zc + h / 2 + 0.2), (w + 0.4, 0.06, 0.2), M["trim"], axes=axes)
    if shutters:
        for s in (-1, 1):
            mb.box(at(s * (w / 2 + 0.33), 0.05, zc), (0.5, 0.04, h + 0.12), M["shutter"], axes=axes)
            mb.box(at(s * (w / 2 + 0.33), 0.08, zc), (0.36, 0.02, 0.06), M["trim"], axes=axes)


def gable(mb, x, xo, y0, y1, z0, z1, material):
    """Треугольный фронтон между x и xo (толщина) над стеной y0..y1"""
    ym = (y0 + y1) / 2
    pts = [(x, y0, z0), (x, y1, z0), (x, ym, z1), (xo, y0, z0), (xo, y1, z0), (xo, ym, z1)]
    mb.poly(pts, [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)], material)


def build_house():
    """Сельский дом 8×6 м: побелённые стены, синие ставни, двускатная крыша, крыльцо с навесом"""
    mb = MB("wall_house")
    x0, x1, y0, y1 = 7.0, 15.0, 6.0, 12.0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    wall_top, eave, ridge, over = 3.0, 2.75, 4.75, 0.6

    mb.box((cx, cy, 0.25), (x1 - x0 + 0.24, y1 - y0 + 0.24, 0.5), M["plinth"])
    mb.box((cx, cy, (0.4 + wall_top) / 2), (x1 - x0, y1 - y0, wall_top - 0.4), M["plaster"])

    # Крыша: два ската, конёк, фронтоны с чердачным окном
    for ye in (y0 - over, y1 + over):
        mb.beam((cx, ye, eave), (cx, cy, ridge), x1 - x0 + 2 * over, 0.12, M["roof"], side=(1, 0, 0))
    mb.beam((x0 - over, cy, ridge + 0.04), (x1 + over, cy, ridge + 0.04), 0.28, 0.16, M["roof"])
    for x, xo, s in ((x0, x0 + 0.15, -1), (x1, x1 - 0.15, 1)):
        gable(mb, x - s * 0.02, xo, y0, y1, wall_top, ridge - 0.12, M["gable"])
        window(mb, (x - s * 0.02, cy), (s, 0, 0), (0, 1, 0), 3.65, w=0.55, h=0.55, shutters=False)

    # Окна: три на фасаде, по одному сбоку, два сзади
    for wx in (8.3, 10.2, 14.0):
        window(mb, (wx, y0), (0, -1, 0), (1, 0, 0), 1.75)
    window(mb, (x0, 10.3), (-1, 0, 0), (0, 1, 0), 1.75)
    window(mb, (x1, 8.5), (1, 0, 0), (0, 1, 0), 1.75)
    for wx in (9.0, 13.0):
        window(mb, (wx, y1), (0, 1, 0), (1, 0, 0), 1.75)

    # Дверь и крыльцо с навесом
    dx = 12.1
    mb.box((dx, y0 - 0.03, 1.5), (1.0, 0.06, 2.0), M["door"])
    mb.box((dx + 0.35, y0 - 0.08, 1.45), (0.06, 0.06, 0.12), M["trim"])
    for s in (-1, 1):
        mb.box((dx + s * 0.56, y0 - 0.05, 1.55), (0.1, 0.08, 2.1), M["trim"])
    mb.box((dx, y0 - 0.05, 2.62), (1.22, 0.08, 0.1), M["trim"])
    mb.box((dx, y0 - 0.7, 0.25), (1.9, 1.4, 0.5), M["concrete"])
    mb.box((dx, y0 - 1.55, 0.165), (1.9, 0.3, 0.33), M["concrete"])
    mb.box((dx, y0 - 1.85, 0.085), (1.9, 0.3, 0.17), M["concrete"])
    for s in (-1, 1):
        mb.box((dx + s * 0.85, y0 - 1.3, 1.55), (0.1, 0.1, 2.1), M["wood"])
    mb.beam((dx, y0, 2.68), (dx, y0 - 1.55, 2.5), 2.1, 0.08, M["roof"], side=(1, 0, 0))

    # Скамейка у стены, труба
    for bx in (8.65, 9.85):
        mb.box((bx, y0 - 0.3, 0.22), (0.08, 0.3, 0.44), M["wood_dark"])
    mb.box((9.25, y0 - 0.3, 0.46), (1.6, 0.36, 0.05), M["wood"])
    mb.box((9.5, 10.2, 4.45), (0.5, 0.5, 1.9), M["brick"])
    mb.box((9.5, 10.2, 5.43), (0.62, 0.62, 0.08), M["concrete"])
    return mb.build(solid=True)


def build_shed():
    """Дощатый сарай с односкатной крышей"""
    mb = MB("wall_shed")
    x0, x1, y0, y1 = 15.8, 18.2, 11.0, 14.0
    mb.box(((x0 + x1) / 2, (y0 + y1) / 2, 1.1), (x1 - x0, y1 - y0, 2.2), M["wood_dark"])
    for i in range(9):  # доски обшивки на фасаде
        mb.box((x0 + 0.13 + i * 0.27, y0 - 0.02, 1.1), (0.2, 0.03, 2.2), M["wood"])
    mb.beam(((x0 + x1) / 2, y0 - 0.4, 2.55), ((x0 + x1) / 2, y1 + 0.3, 2.15), x1 - x0 + 0.5, 0.06, M["roof_shed"], side=(1, 0, 0))
    mb.box((16.6, y0 - 0.05, 0.95), (0.9, 0.04, 1.9), M["wood_old"])
    mb.box((16.95, y0 - 0.09, 1.0), (0.08, 0.04, 0.2), M["plinth"])
    return mb.build(solid=True)


def build_ladder():
    """Деревянная лестница 3.5 м приставлена к боковой стене дома под углом 75°"""
    mb = MB("ladder")
    length, angle, wall_x, y = 3.5, rad(75), 7.0, 7.6
    run, rise = length * math.cos(angle), length * math.sin(angle)
    for s in (-1, 1):
        mb.beam((wall_x - run, y + s * 0.24, 0), (wall_x - 0.04, y + s * 0.24, rise), 0.07, 0.05, M["ladder"], side=(0, 1, 0))
    for k in range(1, 12):
        t = k * 0.3 / length
        x, z = wall_x - run + run * t, rise * t
        mb.beam((x, y - 0.24, z), (x, y + 0.24, z), 0.045, 0.045, M["ladder"])
    return mb.build(solid=True)


def build_yard_details():
    """Дорожка из плит, грядки, поленница"""
    mb = MB("yard")
    y = -8.0
    while y < 4.3:
        mb.box((PATH_X + random.uniform(-0.08, 0.08), y, 0.02), (random.uniform(0.6, 0.75), random.uniform(0.38, 0.48), 0.04),
               M["stone"], rz=random.uniform(-0.12, 0.12))
        y += 0.55
    for by in (1.2, 2.4, 3.6):
        mb.box((16.35, by, 0.08), (3.6, 0.8, 0.16), M["soil"])
        for k in range(10):
            sx = 14.8 + k * 0.35
            mb.cyl((sx, by, 0.16), (sx + random.uniform(-0.04, 0.04), by, 0.32), 0.05, 0, M["sprout"], n=4)
    for row in range(4):
        for k in range(7 - row):
            x = 16.7 + k * 0.26 + row * 0.13
            z = 0.12 + row * 0.22
            mb.cyl((x, 7.4, z), (x, 8.7, z), 0.12, 0.12, M["wood"] if (k + row) % 3 else M["wood_old"], n=7)
    return mb.build(solid=False)


# ---------- Заборы (каждый прямой участок — отдельный объект, чтобы коллизия была узкой) ----------

def picket_fence(name, a, b):
    """Штакетник: столбы, две прожилины, острые штакетины"""
    mb = MB(name)
    a, b = V((*a, 0)), V((*b, 0))
    d = b - a
    length = d.length
    t = d.normalized()
    n = V((0, 0, 1)).cross(t)
    posts = max(1, round(length / 2.4))
    for k in range(posts + 1):
        p = a + t * (length * k / posts)
        mb.box(p + V((0, 0, 0.7)), (0.1, 0.1, 1.4), M["wood_dark"], rz=math.atan2(t.y, t.x))
    for z in (0.35, 1.05):
        mb.beam(a + n * 0.07 + V((0, 0, z)), b + n * 0.07 + V((0, 0, z)), 0.08, 0.04, M["wood"])
    count = int(length / 0.17)
    for k in range(count):
        p = a + t * (0.085 + k * 0.17) + n * 0.1
        h = 1.25 + 0.03 * math.sin(k * 1.7)
        w = 0.045
        prof = [(-w, 0.08), (w, 0.08), (w, h), (0, h + 0.07), (-w, h)]
        pts = [p + t * u + V((0, 0, z)) + n * off for off in (-0.012, 0.012) for (u, z) in prof]
        faces = [(0, 1, 2, 3, 4), (9, 8, 7, 6, 5)] + [(i, (i + 1) % 5, 5 + (i + 1) % 5, 5 + i) for i in range(5)]
        mb.poly(pts, faces, M["picket"])
    return mb.build()


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
    x0, y0, x1, y1 = YARD
    picket_fence("wall_fence_front_l", (x0, y0), (GATE[0], y0))
    picket_fence("wall_fence_front_r", (GATE[1], y0), (x1, y0))
    picket_fence("wall_fence_left", (x0, y1), (x0, y0))
    picket_fence("wall_fence_right", (x1, y0), (x1, y1))
    picket_fence("wall_fence_back", (x1, y1), (x0, y1))

    # Калитка открыта внутрь двора, сквозь неё можно пройти
    mb = MB("gate")
    hinge = V((GATE[0] + 0.05, y0 + 0.05, 0))
    t = V((math.cos(rad(80)), math.sin(rad(80)), 0))
    n = V((0, 0, 1)).cross(t)
    w = GATE[1] - GATE[0] - 0.15
    for z in (0.35, 1.05):
        mb.beam(hinge + V((0, 0, z)), hinge + t * w + V((0, 0, z)), 0.08, 0.04, M["wood"])
    for k in range(int(w / 0.17)):
        p = hinge + t * (0.08 + k * 0.17) + n * 0.03
        mb.box(p + V((0, 0, 0.7)), (0.09, 0.024, 1.25), M["picket"], rz=math.atan2(t.y, t.x))
    mb.build()

    # Глухой забор соседнего участка и жерди вдоль дороги
    board_fence("wall_fence_neighbor_1", (-24, 18), (-12, 18))
    board_fence("wall_fence_neighbor_2", (-12, 18), (0, 18))
    for i, x in enumerate(range(-60, 60, 12)):
        rail_fence(f"{'wall_' if -24 <= x < 24 else ''}fence_rail_{i}", (x, ROAD_Y - 3.8), (x + 12, ROAD_Y - 3.8))


# ---------- Деревья ----------

def tree(mb_trunk, mb_crown, kind, x, y, s=1.0):
    z = height(x, y)
    base = V((x, y, z - 0.2))
    if kind == "birch":
        top = base + V((random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), 6.5 * s))
        mb_trunk.cyl(base, top, 0.16 * s, 0.07 * s, M["birch"], n=7)
        for k in range(5):
            h = random.uniform(0.5, 3.5) * s
            mb_trunk.box(base.lerp(top, h / (6.5 * s)) + V((0, 0, 0)), (0.3 * s, 0.3 * s, 0.05), M["birch_mark"], rz=random.uniform(0, 3))
        for k in range(3):
            mb_crown.blob(base.lerp(top, 0.62 + 0.13 * k) + V((random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5), 0)),
                          1.5 * s, M["leaf_light"], scale=(1, 1, 1.35), bump=0.2)
    elif kind == "pine":
        mb_trunk.cyl(base, base + V((0, 0, 3 * s)), 0.2 * s, 0.12 * s, M["bark"], n=6)
        for k in range(3):
            r = (2.0 - k * 0.5) * s
            mb_crown.cyl(base + V((0, 0, (1.6 + k * 1.6) * s)), base + V((0, 0, (4.2 + k * 1.6) * s)), r, 0, M["pine"], n=8)
    else:  # лиственное дерево; apple — яблоня во дворе
        h = (3.0 if kind == "apple" else 4.0) * s
        mb_trunk.cyl(base, base + V((0, 0, h)), 0.2 * s, 0.13 * s, M["bark"], n=7)
        r = (1.5 if kind == "apple" else 2.0) * s
        for k in range(4):
            off = V((random.uniform(-0.8, 0.8), random.uniform(-0.8, 0.8), random.uniform(0, 1.0))) * s
            mb_crown.blob(base + V((0, 0, h)) + off, r * random.uniform(0.75, 1.0), M["leaf"], scale=(1, 1, 0.85), bump=0.2)
        if kind == "apple":
            for k in range(14):
                a = random.uniform(0, 2 * math.pi)
                p = base + V((math.cos(a) * r * 1.05, math.sin(a) * r * 1.05, h + random.uniform(-0.3, 0.6)))
                mb_crown.blob(p, 0.09, M["apple"], seg=5, rings=3, bump=0)


def build_trees():
    # Рядом с игроком: у каждого дерева свой ствол-препятствие, кроны общим объектом
    near = [("birch", -16, 12), ("birch", -19, 4), ("tree", 22.5, 4), ("birch", 22, 15), ("tree", -14, -20),
            ("birch", 15, -19), ("apple", 5.0, 2.6), ("apple", 4.8, 12.8), ("tree", -21, 21), ("pine", 21, -21)]
    crowns = MB("tree_crowns")
    for i, (kind, x, y) in enumerate(near):
        trunk = MB(f"wall_trunk_{i}")
        tree(trunk, crowns, kind, x, y, random.uniform(0.9, 1.15))
        trunk.build()
    crowns.build()

    # Дальние деревья на холмах — один объект
    far_t, far_c = MB("trees_far_trunks"), MB("trees_far_crowns")
    placed = 0
    while placed < 70:
        a = random.uniform(0, 2 * math.pi)
        r = random.uniform(30, 68)
        x, y = math.cos(a) * r, math.sin(a) * r
        if abs(y - ROAD_Y) < 6 or max(abs(x), abs(y)) < 27:
            continue
        kind = random.choice(["pine", "pine", "birch", "tree"])
        tree(far_t, far_c, kind, x, y, random.uniform(0.9, 1.4))
        placed += 1
    far_t.build()
    far_c.build()

    # Кусты вдоль соседского забора и у дома
    bushes = MB("bushes")
    for x, y in [(-22, 16.8), (-18.5, 16.9), (-9, 16.8), (-4, 16.7), (3.8, 5.8), (18.2, 6.0), (6.2, 13.9)]:
        for _ in range(3):
            bushes.blob((x + random.uniform(-0.5, 0.5), y + random.uniform(-0.3, 0.3), 0.4), random.uniform(0.5, 0.75),
                        M["leaf"], scale=(1.2, 1, 0.8))
    bushes.build()


# ---------- Дальние дома у дороги ----------

def build_far_houses():
    roofs = [M["roof"], mat("Кровля красная", "#8E3E3E", rough=0.5, metal=0.3), mat("Кровля синяя", "#3E5E8E", rough=0.5, metal=0.3)]
    for i, (x, y, rz) in enumerate([(-44, -3.5, 0), (42, -3, 0), (-36, -17.5, math.pi), (52, -17, math.pi)]):
        mb = MB(f"house_far_{i}")
        z = min(height(x + dx, y + dy) for dx in (-3.5, 3.5) for dy in (-3, 3))
        c, s = math.cos(rz), math.sin(rz)
        rot = lambda dx, dy, dz: (x + dx * c - dy * s, y + dx * s + dy * c, z + dz)
        mb.box(rot(0, 0, 0.0), (7.2, 5.8, 1.6), M["plinth"], rz=rz)
        mb.box(rot(0, 0, 2.0), (7, 5.6, 2.4), M["plaster"], rz=rz)
        for sy in (-1, 1):
            mb.beam(rot(0, sy * 3.3, 3.0), rot(0, 0, 4.7), 7.8, 0.12, roofs[i % 3], side=(c, s, 0))
        for ex in (-3.5, 3.5):
            pts = [rot(ex, -2.8, 3.2), rot(ex, 2.8, 3.2), rot(ex, 0, 4.6)]
            mb.poly(pts, [(0, 1, 2)], M["gable"])
        for wx in (-1.8, 1.8):
            mb.box(rot(wx, -2.82, 2.1), (1.0, 0.06, 1.1), M["glass"], rz=rz)
            for sx in (-1, 1):
                mb.box(rot(wx + sx * 0.78, -2.84, 2.1), (0.45, 0.04, 1.15), M["shutter"], rz=rz)
        mb.build()


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

def villager(mb, base, facing):
    """Сельская жительница в платке и длинной юбке, ~1,65 м; facing — угол взгляда (0 — по +Y)"""
    c, s = math.cos(facing), math.sin(facing)
    at = lambda dx, dy, dz: V(base) + V((dx * c - dy * s, dx * s + dy * c, dz))
    skin, scarf = mat("Кожа", "#E9C3A0", rough=0.8), mat("Платок", "#C7354A", rough=0.9)
    blouse, skirt = mat("Кофта", "#6F8FBF", rough=0.9), mat("Юбка", "#3E3550", rough=0.9)
    shoes = mat("Обувь", "#2A2421", rough=0.8)
    for sx in (-1, 1):
        mb.cyl(at(sx * 0.08, 0, 0), at(sx * 0.08, 0, 0.3), 0.045, 0.04, skin, n=6)
        mb.box(at(sx * 0.08, 0.04, 0.03), (0.09, 0.2, 0.06), shoes, rz=facing)
    mb.cyl(at(0, 0, 0.25), at(0, 0, 0.98), 0.3, 0.17, skirt, n=12)  # юбка расширяется книзу
    mb.cyl(at(0, 0, 0.95), at(0, 0, 1.42), 0.17, 0.15, blouse, n=10)
    for sx in (-1, 1):
        mb.cyl(at(sx * 0.2, 0, 1.38), at(sx * 0.24, 0.12, 0.98), 0.05, 0.045, blouse, n=6)  # руки чуть вперёд
        mb.blob(at(sx * 0.24, 0.13, 0.94), 0.045, skin, bump=0.02)
    mb.cyl(at(0, 0, 1.42), at(0, 0, 1.5), 0.05, 0.05, skin, n=6)
    mb.blob(at(0, 0.01, 1.6), 0.11, skin, scale=(0.9, 1, 1.1), bump=0.02)
    mb.blob(at(0, -0.02, 1.63), 0.125, scarf, scale=(0.95, 0.95, 1.05), bump=0.03)  # платок сзади и сверху
    mb.cyl(at(0, -0.08, 1.52), at(0, -0.14, 1.36), 0.06, 0.02, scarf, n=6)  # узел платка


def dog(mb, base, facing):
    """Дворовая собака, морда по направлению facing"""
    c, s = math.cos(facing), math.sin(facing)
    at = lambda dx, dy, dz: V(base) + V((dx * c - dy * s, dx * s + dy * c, dz))
    fur, dark = mat("Шерсть", "#9A6A3E", rough=1.0), mat("Шерсть тёмная", "#4A3426", rough=1.0)
    mb.blob(at(0, 0, 0.45), 0.2, fur, scale=(0.75, 1.55, 0.8), bump=0.05)
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.cyl(at(sx * 0.09, sy * 0.2, 0), at(sx * 0.09, sy * 0.2, 0.4), 0.035, 0.04, fur, n=6)
    mb.blob(at(0, 0.36, 0.63), 0.12, fur, bump=0.04)
    mb.box(at(0, 0.48, 0.6), (0.09, 0.13, 0.08), dark, rz=facing)  # морда
    for sx in (-1, 1):
        mb.cyl(at(sx * 0.06, 0.33, 0.72), at(sx * 0.07, 0.32, 0.82), 0.035, 0, dark, n=4)  # уши
    mb.beam(at(0, -0.3, 0.5), at(0, -0.45, 0.72), 0.04, 0.04, fur)  # хвост вверх


def chicken(mb, base, facing):
    c, s = math.cos(facing), math.sin(facing)
    at = lambda dx, dy, dz: V(base) + V((dx * c - dy * s, dx * s + dy * c, dz))
    white, red, beak = mat("Перо", "#F1EEE6", rough=1.0), mat("Гребешок", "#C9302C", rough=0.7), mat("Клюв", "#E7A12B", rough=0.6)
    mb.blob(at(0, 0, 0.22), 0.12, white, scale=(0.8, 1.15, 0.9), bump=0.05)
    mb.blob(at(0, 0.11, 0.36), 0.06, white, bump=0.03)
    mb.box(at(0, 0.11, 0.43), (0.02, 0.06, 0.04), red, rz=facing)
    mb.cyl(at(0, 0.16, 0.36), at(0, 0.21, 0.355), 0.02, 0, beak, n=4)
    for sx in (-1, 1):
        mb.cyl(at(sx * 0.04, 0, 0), at(sx * 0.04, 0, 0.13), 0.01, 0.01, beak, n=4)


def build_bystanders():
    """Посторонние у открытого отсека КТПН — нарушение «Люди и животные в опасной зоне»"""
    mb = MB("item_people-animals")
    # От фасада КТПН отходим к дороге и чуть влево — посторонние всё ещё в опасной зоне, но не у самого входа
    x0, y0 = KTPN_POS[0] - 0.6, KTPN_FRONT_Y - 0.9
    villager(mb, (x0 - 1.0, y0 - 1.9, 0), rad(-15))  # смотрит в открытый отсек
    dog(mb, (x0 - 2.3, y0 - 1.3, 0), rad(30))
    for dx, dy, f in ((0.4, -1.2, 120), (0.9, -1.6, -60), (-0.1, -0.8, 200)):
        chicken(mb, (x0 + dx, y0 + dy, 0), rad(f))
    o = mb.build()
    o["inspect_range"] = 3.0  # видно с дороги, подходить вплотную не нужно


def build_extinguisher():
    """Сумка монтёра с инструментом и огнетушитель у правого угла КТПН — правильно, отвлекающий вариант"""
    place_model(SUMKA_GLB, "item_extinguisher-ok", (KTPN_RIGHT_X + 0.1, KTPN_FRONT_Y - 0.6), 0,  # лицом к дороге
                solid=False, fit_logos=False)


# ---------- Готовые модели: фургон, КТПН, сумка с огнетушителем ----------

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


def place_busy_worker():
    """Монтёр без каски в левом отсеке КТПН: стоит на полу отсека лицом к трансформатору и голыми руками держится
    за кабели над ним. Один объект — три карточки задания: без каски и в одиночку (нарушения), в диэлектрических
    ботах (правильно). Поза задана в prep_monter.py: ладони на 0,25 м впереди и на 1,77 м выше ступней —
    так они ложатся на кабели (их фасад в 1,07 м за фасадом КТПН, между x −2,94 и −2,64 от правого края)"""
    place_model(MONTER_GLB, "item_no-helmet+alone+boots-ok", (KTPN_RIGHT_X - 2.78, KTPN_FRONT_Y + 0.79),
                math.pi,  # лицом к задней стене КТПН (+Y)
                base_z=0.26,  # пол отсека
                solid=False, fit_logos=False,
                inspect=3.5)  # стоит в глубине КТПН — осматривается от входа


# ---------- Сборка ----------

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    materials()

    build_ground()
    build_road()
    build_grass()
    build_house()
    build_shed()
    build_ladder()
    build_yard_details()
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
    if PLACE_KTPN:
        place_model(KTPN_GLB, "item_zone-unfenced", (KTPN_RIGHT_X, KTPN_FRONT_Y), 0)  # дверями к дороге; вокруг нет ограждения
        place_busy_worker()
    empty("place_worker", (-1.0, -4.0, 0))

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_extras=True, export_apply=True)


build()
print("Готово:", OUT_GLB, OUT_BLEND)
