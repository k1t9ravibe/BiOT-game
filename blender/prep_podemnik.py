"""
Готовит автовышку podemnik_strela_bez_montera.glb (сгенерированная модель: машина с выдвинутыми опорами и поднятой
корзиной у своей опоры ВЛ, ~1,5 млн треугольников, текстуры 4096², размер ~1 м) для сцены «Вечерний город»
и сохраняет в blender/assets/podemnik.glb (ось Z вверх, как остальные готовые модели). Машина стоит вдоль Y,
кабиной и опорой к −Y; масштаб — по верху опоры (9 м, как у опор линии в build_evening.py). Модель в HD:
игрок подходит к ней близко, при сильном упрощении текстура плывёт.

В текстуре рисуются: на дверях кабины с обеих сторон — логотип logo_ktl.png (из корня проекта), на боках стрелы —
надпись KAZAKHTELECOM чёрным. Для зрителя с каждой стороны надпись читается слева направо.

Запуск (из корня проекта), после него — пересобрать сцену build_evening.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_podemnik.py
"""

import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from prep_furgon import bilinear, image_array, logo_mask, render_text_mask  # noqa: E402
from prep_model import export_asset, import_decimated, shrink_textures, vertices  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "podemnik_strela_bez_montera.glb")
OUT = os.path.join(ROOT, "blender", "assets", "podemnik.glb")
LOGO = os.path.join(ROOT, "logo_ktl.png")

HEIGHT = 9.0      # верх опоры, м
DECIMATE = 0.1    # ~150 тыс. треугольников

# Наклейки в координатах готовой модели, м: прямоугольник длиной length и высотой height на плоском боку детали.
# axis — направление детали (вдоль него идёт надпись), normal — наружу на бок +X; centers — центр наклейки
# на поверхности боков +X (1) и −X (−1). Боковины кабины стоят при x = +0,83 и −2,06. Стрела в плане повёрнута
# (на метр по y её бок уходит на ~0,35 м к −X) и наклонена (на метр опускается на 0,11 м)
LOGO_DECAL = dict(axis=(0, 1, 0), normal=(1, 0, 0), centers={1: (0.83, -1.72, 2.05), -1: (-2.06, -1.72, 2.05)},
                  length=0.9, height=0.62)  # перед дверной ручкой
TEXT_DECAL = dict(axis=(-0.35, 1, -0.11), normal=(1, 0.35, 0), centers={1: (-1.2, 2.0, 5.08), -1: (-1.82, 2.0, 5.08)},
                  length=3.8, height=0.3)  # не заходит на стык секций у поворотной части (y > 4,1)
PLANE_TOL = 0.12  # на сколько грань может отстоять от плоскости бока, м


def load():
    o = import_decimated(SRC, DECIMATE)
    co = vertices(o)
    lo, hi = co.min(0), co.max(0)
    k = HEIGHT / (hi[2] - lo[2])
    o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])))
    o.name = "podemnik"
    print("size, m:", ((hi - lo) * k).round(2).tolist())
    shrink_textures(2)
    return o


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def decal_frame(decal, side):
    """Центр, «вправо» и «вверх» наклейки для зрителя, который смотрит на бок side (+1 / −1) снаружи"""
    nrm = unit(decal["normal"]) * side
    axis = unit(decal["axis"])
    axis = unit(axis - axis.dot(nrm) * nrm)
    right = np.cross(-nrm, (0, 0, 1))  # вправо для зрителя, который смотрит на бок
    if axis.dot(right) < 0:
        axis = -axis  # иначе надпись с этой стороны вышла бы зеркальной
    up = np.cross(nrm, axis)
    return np.asarray(decal["centers"][side], float), nrm, axis, up


def decal_texels(me, w, h, decal, side):
    """Пиксели текстуры w×h на боку side в прямоугольнике наклейки: столбец, строка, u, v ∈ [0, 1]
    (u — слева направо для зрителя с этой стороны, v — снизу вверх)"""
    c, nrm, axis, up = decal_frame(decal, side)
    L, H = decal["length"], decal["height"]
    reach = math.hypot(L, H) / 2 + 0.05
    uvl = me.uv_layers.active.data
    out = []
    for t in me.loop_triangles:
        if np.dot(t.normal, nrm) < 0.6:
            continue
        P = np.array([me.vertices[i].co for i in t.vertices])
        rel = P - c
        if np.abs(rel @ nrm).max() > PLANE_TOL or np.linalg.norm(rel - np.outer(rel @ nrm, nrm), axis=1).min() > reach:
            continue
        U = np.array([uvl[li].uv for li in t.loops]) * (w, h)
        m = np.array([U[1] - U[0], U[2] - U[0]]).T
        if abs(np.linalg.det(m)) < 1e-9:
            continue
        lo, hi = np.floor(U.min(0)).astype(int) - 1, np.ceil(U.max(0)).astype(int) + 1
        cx, cy = np.meshgrid(np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1))
        q = np.stack([cx.ravel(), cy.ravel()], 1)
        l12 = np.linalg.solve(m, (q + 0.5 - U[0]).T).T
        bary = np.column_stack([1 - l12.sum(1), l12])
        ok = (bary >= -0.02).all(1)
        if not ok.any():
            continue
        p = bary[ok] @ P - c
        out.append(np.column_stack([q[ok], 0.5 + p @ axis / L, 0.5 + p @ up / H]))
    T = np.concatenate(out)
    keep = (T[:, 0] >= 0) & (T[:, 0] < w) & (T[:, 1] >= 0) & (T[:, 1] < h)
    keep &= (T[:, 2] >= 0) & (T[:, 2] <= 1) & (T[:, 3] >= 0) & (T[:, 3] <= 1)
    return T[keep]


def paint(o, decal, mask, color):
    me = o.data
    me.calc_loop_triangles()
    for img in [i for i in bpy.data.images if i.size[0]]:
        name = img.name.lower()
        if "normal" in name or "metallic" in name:
            continue  # рисуем только цвет: наклейка плоская
        w, h = img.size
        px = image_array(img)
        for side in (1, -1):
            T = decal_texels(me, w, h, decal, side)
            col, row = T[:, 0].astype(int), T[:, 1].astype(int)
            a = bilinear(mask, T[:, 2], T[:, 3])[:, None]
            px[row, col, :3] = px[row, col, :3] * (1 - a) + np.asarray(color) * a
            print(f"{img.name}: side {side:+d}, {len(T)} texels")
        img.pixels.foreach_set(px.ravel())
        img.pack()


def fit(mask, decal):
    """Вписывает маску в прямоугольник наклейки с сохранением пропорций: поля по краям"""
    L, H = decal["length"], decal["height"]
    mh, mw = mask.shape
    k = min(L / mw, H / mh)
    ph, pw = int(round((H / k - mh) / 2)), int(round((L / k - mw) / 2))
    return np.pad(mask, ((max(ph, 0),) * 2, (max(pw, 0),) * 2))


def build():
    text = fit(render_text_mask(), TEXT_DECAL)  # сбрасывает сцену — до загрузки модели
    logo, blue = logo_mask(LOGO)
    logo = fit(logo, LOGO_DECAL)
    o = load()
    paint(o, LOGO_DECAL, logo, blue)
    paint(o, TEXT_DECAL, text, (0.02, 0.02, 0.02))
    export_asset(OUT)


build()
