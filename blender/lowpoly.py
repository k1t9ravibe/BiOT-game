"""
Общие инструменты низкополигональных сцен (тот же стиль, что у сцены 1 — build_landscape.py):
цвета и материалы, построитель мешей MB, окна со ставнями, фронтоны, штакетник, деревья.

Подключение в скрипте сцены:
    sys.path.insert(0, os.path.dirname(__file__))
    from lowpoly import *

build_landscape.py пока держит свою копию этих функций — сцена 1 закончена и не трогается.
"""

import math
import random

import bmesh
import bpy
from mathutils import Matrix
from mathutils import Vector as V

rad = math.radians


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


M = {}


def base_materials():
    """Палитра сцены 1 — чтобы дома, окна, деревья и заборы выглядели так же"""
    M.update(
        plaster=mat("Побелка", "#EEEAE0"),
        plinth=mat("Цоколь", "#7E8288"),
        roof=mat("Кровля", "#3F7A6A", rough=0.5, metal=0.3),
        roof_red=mat("Кровля красная", "#8E3E3E", rough=0.5, metal=0.3),
        roof_blue=mat("Кровля синяя", "#3E5E8E", rough=0.5, metal=0.3),
        trim=mat("Наличники", "#F7F7F2", rough=0.6),
        shutter=mat("Ставни", "#2F6FB8", rough=0.6),
        gable=mat("Фронтон", "#5A8FC0", rough=0.7),
        glass=mat("Стекло", "#2D4B6E", rough=0.15),
        door=mat("Дверь", "#6B4026", rough=0.7),
        brick=mat("Кирпич", "#A65A3C"),
        concrete=mat("Бетон", "#9A9DA2"),
        wood=mat("Дерево", "#8A6440"),
        wood_dark=mat("Тёмное дерево", "#5E4630"),
        picket=mat("Штакетник", "#4F86C6", rough=0.7),
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

    def span(self, x0, y0, z0, x1, y1, z1, m):
        """Брусок по двум углам"""
        self.box(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)), m)

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
        """Неровная сфера — крона дерева, куст, облако, голова"""
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

    def build(self, smooth_shade=False, recalc=True, solid=False, parent=None, pivot=None):
        """parent — объект-родитель (стоит в начале координат без поворота);
        pivot — точка, вокруг которой объект будут вращать в игре: туда переносится его начало координат"""
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
        if pivot is not None:
            pivot = V(pivot)
            me.transform(Matrix.Translation(-pivot))
            o.location = pivot
        if parent is not None:
            # Деталь строится в мировых координатах; обратная матрица родителя сохраняет её на месте
            if parent.parent is not None:
                bpy.context.view_layer.update()
                inv = parent.matrix_world.inverted()
            else:
                inv = parent.matrix_basis.inverted()
            o.parent = parent
            o.matrix_parent_inverse = inv
        if solid:
            o["solid"] = 1
        return o


def empty(name, loc=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, None)
    o.empty_display_type = "PLAIN_AXES"
    o.empty_display_size = 1.0
    o.location = loc
    bpy.context.collection.objects.link(o)
    if parent is not None:
        o.parent = parent
    return o


# ---------- Детали в стиле сцены 1 ----------

def window(mb, p, n, t, zc, w=1.0, h=1.2, shutters=True, z0=0.0):
    """Окно на стене: p — точка на поверхности стены (x, y), n — наружу, t — вдоль стены"""
    n, t = V(n), V(t)
    axes = (t, V((0, 0, 1)).cross(t), V((0, 0, 1)))
    at = lambda along, out, z: V((p[0], p[1], z)) + t * along + n * out
    mb.box(at(0, 0.02, zc), (w, 0.04, h), M["glass"], axes=axes)
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


def picket_fence(mb, a, b):
    """Штакетник: столбы, две прожилины, острые штакетины"""
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
    for k in range(int(length / 0.17)):
        p = a + t * (0.085 + k * 0.17) + n * 0.1
        h = 1.25 + 0.03 * math.sin(k * 1.7)
        w = 0.045
        prof = [(-w, 0.08), (w, 0.08), (w, h), (0, h + 0.07), (-w, h)]
        pts = [p + t * u + V((0, 0, z)) + n * off for off in (-0.012, 0.012) for (u, z) in prof]
        faces = [(0, 1, 2, 3, 4), (9, 8, 7, 6, 5)] + [(i, (i + 1) % 5, 5 + (i + 1) % 5, 5 + i) for i in range(5)]
        mb.poly(pts, faces, M["picket"])


def tree(mb_trunk, mb_crown, kind, x, y, s=1.0, z=0.0):
    """Деревья как в сцене 1: berёза, ель, лиственное, яблоня"""
    base = V((x, y, z - 0.2))
    if kind == "birch":
        top = base + V((random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), 6.5 * s))
        mb_trunk.cyl(base, top, 0.16 * s, 0.07 * s, M["birch"], n=7)
        for k in range(5):
            h = random.uniform(0.5, 3.5) * s
            mb_trunk.box(base.lerp(top, h / (6.5 * s)), (0.3 * s, 0.3 * s, 0.05), M["birch_mark"], rz=random.uniform(0, 3))
        for k in range(3):
            mb_crown.blob(base.lerp(top, 0.62 + 0.13 * k) + V((random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5), 0)),
                          1.5 * s, M["leaf_light"], scale=(1, 1, 1.35), bump=0.2)
    elif kind == "pine":
        mb_trunk.cyl(base, base + V((0, 0, 3 * s)), 0.2 * s, 0.12 * s, M["bark"], n=6)
        for k in range(3):
            r = (2.0 - k * 0.5) * s
            mb_crown.cyl(base + V((0, 0, (1.6 + k * 1.6) * s)), base + V((0, 0, (4.2 + k * 1.6) * s)), r, 0, M["pine"], n=8)
    else:
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
