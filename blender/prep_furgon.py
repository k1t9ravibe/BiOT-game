"""
Готовит фургон furgonkt.glb (сгенерированная модель: ~1,5 млн треугольников, текстуры 4096², размер ~1 м)
для сцены «Улица у КТПН»: упрощает меш, уменьшает текстуры, ставит в натуральную величину и сохраняет
в blender/assets/furgonkt_van.glb в том же виде, что остальные готовые модели (ось Z вверх, см. place_model
в build_landscape.py): при rz = 0 морда смотрит на −X, низ на нуле, центр в начале координат.

На бортах генератор нарисовал кривой логотип и бессмысленную надпись. Их место в текстурах закрашивается
цветом кузова, а сверху рисуется логотип blender/assets/kazakhtelecom_logo.png и надпись KAZAKHTELECOM.

Запуск (из корня проекта), после него — пересобрать сцену build_landscape.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_furgon.py
"""

import math
import os
import sys
import tempfile

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from prep_model import export_asset, import_decimated, shrink_textures, vertices  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "furgonkt.glb")
OUT = os.path.join(ROOT, "blender", "assets", "furgonkt_van.glb")
LOGO = os.path.join(ROOT, "blender", "assets", "kazakhtelecom_logo.png")
FONT = r"C:\Windows\Fonts\arialbd.ttf"
TEXT = "KAZAKHTELECOM"

LENGTH = 5.54     # длина кузова, м — как у прежнего фургона
DECIMATE = 0.03   # доля треугольников, которая остаётся (~45 тыс.)

# Наклейка на грузовой панели обоих бортов (координаты готовой модели, м): там, где были старые логотип и надпись
DECAL_X = (-0.08, 2.32)
DECAL_Z = (1.02, 2.0)
FEATHER = 0.03    # ширина перехода закрашенного прямоугольника в исходную текстуру, м
DECAL_RES = 0.004  # шаг маски наклейки, м


def load_van():
    o = import_decimated(SRC, DECIMATE)
    # В файле морда смотрит на −Y: поворачиваем на −90° (морда на −X), масштабируем по длине,
    # ставим низом на ноль и центром в начало координат
    o.data.transform(Matrix.Rotation(math.radians(-90), 4, "Z"))
    co = vertices(o)
    lo, hi = co.min(0), co.max(0)
    k = LENGTH / (hi[0] - lo[0])
    o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])))
    o.name = "van_body"
    print("van size, m:", ((hi - lo) * k).round(2).tolist())
    shrink_textures()
    return o


# ---------- Наклейка: маска логотипа и надписи ----------

def image_array(img):
    w, h = img.size
    return np.array(img.pixels[:], dtype=np.float32).reshape(h, w, img.channels)  # строка 0 — низ картинки


def crop(a, thr=0.02):
    rows, cols = np.nonzero(a > thr)
    return a[rows.min():rows.max() + 1, cols.min():cols.max() + 1]


def bilinear(a, u, v):
    """Значения маски a в точках (u, v) ∈ [0, 1]², v — вверх; за пределами — 0"""
    h, w = a.shape
    x, y = u * w - 0.5, v * h - 0.5
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    pad = np.pad(a, 1)

    def at(yy, xx):
        return pad[np.clip(yy + 1, 0, h + 1), np.clip(xx + 1, 0, w + 1)]

    out = (at(y0, x0) * (1 - fx) * (1 - fy) + at(y0, x0 + 1) * fx * (1 - fy)
           + at(y0 + 1, x0) * (1 - fx) * fy + at(y0 + 1, x0 + 1) * fx * fy)
    return np.where((u >= 0) & (u <= 1) & (v >= 0) & (v <= 1), out, 0)


def render_text_mask():
    """Рендерит надпись белым по чёрному и возвращает её маску, обрезанную по буквам"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    cu = bpy.data.curves.new("text", "FONT")
    cu.body = TEXT
    cu.font = bpy.data.fonts.load(FONT)
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    t = bpy.data.objects.new("text", cu)
    sc.collection.objects.link(t)
    mat = bpy.data.materials.new("white")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1, 1, 1, 1)
    nt.links.new(em.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    cu.materials.append(mat)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 11
    cam.location = (0, 0, 10)
    sc.world = bpy.data.worlds.new("black")
    sc.world.color = (0, 0, 0)
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 16
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x, sc.render.resolution_y = 2200, 440
    path = os.path.join(tempfile.gettempdir(), "furgon_text.png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return crop(image_array(bpy.data.images.load(path))[:, :, 0])


def logo_mask():
    """Маска и цвет логотипа: синее на белом (или на прозрачном) → маска 0…1 и синий цвет"""
    a = image_array(bpy.data.images.load(LOGO))
    alpha = a[:, :, 3] if a.shape[2] == 4 else np.ones(a.shape[:2], np.float32)
    mask = np.clip((1 - a[:, :, 0]) * alpha, 0, 1)
    blue = np.median(a[mask > 0.95][:, :3], axis=0)
    return crop(mask), blue


def decal_mask(text, logo):
    """Маска наклейки размером с прямоугольник DECAL_X × DECAL_Z: надпись внизу, логотип над ней"""
    W, H = DECAL_X[1] - DECAL_X[0], DECAL_Z[1] - DECAL_Z[0]
    xs = (np.arange(int(W / DECAL_RES)) + 0.5) * DECAL_RES
    zs = (np.arange(int(H / DECAL_RES)) + 0.5) * DECAL_RES
    X, Z = np.meshgrid(xs, zs)
    tw = W - 0.2
    th = tw * text.shape[0] / text.shape[1]
    tb = 0.07  # низ надписи
    mask = bilinear(text, (X - (W - tw) / 2) / tw, (Z - tb) / th)
    lb, lt = tb + th + 0.07, H - 0.03  # низ и верх логотипа
    lh = lt - lb
    lw = lh * logo.shape[1] / logo.shape[0]
    mask = np.maximum(mask, bilinear(logo, (X - (W - lw) / 2) / lw, (Z - lb) / lh))
    print(f"decal: text {tw:.2f}×{th:.2f} m, logo {lw:.2f}×{lh:.2f} m")
    return mask


# ---------- Наклейка: рисование в текстурах ----------

def side_texels(me, w, h):
    """Пиксели текстуры w×h на наружной обшивке бортов в зоне наклейки: столбец, строка, x, y, z"""
    uvl = me.uv_layers.active.data
    f = FEATHER
    out = []
    for t in me.loop_triangles:
        P = np.array([me.vertices[i].co for i in t.vertices])
        if abs(t.normal.y) < 0.5 or np.abs(P[:, 1]).min() < 0.85:
            continue
        if P[:, 0].max() < DECAL_X[0] - f or P[:, 0].min() > DECAL_X[1] + f:
            continue
        if P[:, 2].max() < DECAL_Z[0] - f or P[:, 2].min() > DECAL_Z[1] + f:
            continue
        U = np.array([uvl[l].uv for l in t.loops]) * (w, h)
        m = np.array([U[1] - U[0], U[2] - U[0]]).T
        if abs(np.linalg.det(m)) < 1e-9:
            continue
        lo, hi = np.floor(U.min(0)).astype(int) - 1, np.ceil(U.max(0)).astype(int) + 1
        cx, cy = np.meshgrid(np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1))
        q = np.stack([cx.ravel(), cy.ravel()], 1)
        l12 = np.linalg.solve(m, (q + 0.5 - U[0]).T).T
        bary = np.column_stack([1 - l12.sum(1), l12])
        # С запасом в полтора пикселя за край треугольника, чтобы на швах UV не оставалось старых букв:
        # bary_i × высота треугольника из вершины i — расстояние до противоположной стороны в пикселях
        area2 = abs(np.linalg.det(m))
        heights = area2 / np.linalg.norm(U[[1, 2, 0]] - U[[2, 0, 1]], axis=1)
        ok = (bary * heights >= -1.5).all(1)
        if ok.any():
            out.append(np.column_stack([q[ok], bary[ok] @ P]))
    T = np.concatenate(out)
    return T[(T[:, 0] >= 0) & (T[:, 0] < w) & (T[:, 1] >= 0) & (T[:, 1] < h)]


def flatten_panels(o):
    """Под старыми логотипом и надписью упрощённая обшивка осталась бугристой, и на новой наклейке видны тени.
    Вершины борта в зоне наклейки кладём на гладкую поверхность y = a + b·x + c·z + d·z², подогнанную по панели"""
    me = o.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    x, y, z = co.T
    f = 3 * FEATHER
    edge = np.minimum.reduce([x - DECAL_X[0], DECAL_X[1] - x, z - DECAL_Z[0], DECAL_Z[1] - z])
    for s in (1, -1):
        sel = (s * y > 0.95) & (edge > -2 * f)
        A = np.column_stack([np.ones(sel.sum()), x[sel], z[sel], z[sel] ** 2])
        coef = np.linalg.lstsq(A, y[sel], rcond=None)[0]
        wgt = np.clip(edge[sel] / f + 1, 0, 1)
        y[sel] += wgt * (A @ coef - y[sel])
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))


def paint_decal(o, mask, blue):
    me = o.data
    me.calc_loop_triangles()
    W, H = DECAL_X[1] - DECAL_X[0], DECAL_Z[1] - DECAL_Z[0]
    for img in [i for i in bpy.data.images if i.size[0]]:
        w, h = img.size
        px = image_array(img)
        T = side_texels(me, w, h)
        col, row = T[:, 0].astype(int), T[:, 1].astype(int)
        x, y, z = T[:, 2], T[:, 3], T[:, 4]
        edge = np.minimum.reduce([x - DECAL_X[0], DECAL_X[1] - x, z - DECAL_Z[0], DECAL_Z[1] - z])
        wgt = np.clip(edge / FEATHER + 1, 0, 1)[:, None]
        cur = px[row, col]
        fill = np.median(cur[edge > 0], axis=0)  # фон панели: буквы занимают меньшую часть прямоугольника
        new = cur * (1 - wgt) + fill * wgt
        if "normal" not in img.name.lower() and "metallic" not in img.name.lower():
            # Для зрителя у борта +Y передок справа, у борта −Y — слева: надпись читается от задка к морде
            u = np.where(y > 0, (DECAL_X[1] - x) / W, (x - DECAL_X[0]) / W)
            a = bilinear(mask, u, (z - DECAL_Z[0]) / H)[:, None]
            new[:, :3] = new[:, :3] * (1 - a) + blue * a
        px[row, col] = new
        img.pixels.foreach_set(px.ravel())
        img.pack()
        print(f"painted {img.name}: {len(T)} texels")


def build():
    text = render_text_mask()
    logo, blue = logo_mask()
    mask = decal_mask(text, logo)
    o = load_van()
    flatten_panels(o)
    paint_decal(o, mask, blue)
    export_asset(OUT)


build()
