"""
Локация 3 «Вечерний город»: та же городская улица, что в локации 2 (кварталы, деревья, кусты, остановка —
берутся из build_city.py), но вечером: горят фонари. Вдоль сквера на ближней стороне идёт воздушная линия
0,4 кВ на бетонных опорах; в одном пролёте оборван провод: один конец свисает с опоры и лежит поперёк
тротуара (искрит), другой свисает с соседней опоры на газон.

Запуск (из корня проекта):
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/build_evening.py

Результат:
    public/models/evening.glb   — сцена для игры (http://localhost:5173/evening)
    blender/evening_base.blend  — исходник; скрипт перезаписывает его при каждом запуске

Имена, которые читает игра, — как в build_city.py, и ещё (src/evening/ambient.ts):
    glow_<n>    — пятно света фонаря на земле; lamp_<n> — точечный свет фонаря (только у маршрута игрока)
    spark_src   — конец оборванного провода, который искрит
"""

import math
import os
import sys

import bpy
from mathutils import Vector as V

sys.path.insert(0, os.path.dirname(__file__))
import build_city as city  # noqa: E402
from build_city import M, MB, empty, mat  # noqa: E402

ROOT = city.ROOT
OUT_GLB = os.path.join(ROOT, "public", "models", "evening.glb")
OUT_BLEND = os.path.join(ROOT, "blender", "evening_base.blend")

# Воздушная линия 0,4 кВ: опоры на газоне между тротуаром и сквером, пролёт 30 м, траверса поперёк линии
LINE_Y = -11.0
POLE_XS = [15, 45, 75, 105, 135, 165]
POLE_H = 9.0
ARM_Z = 8.4                        # высота траверсы
PHASES = (-0.6, -0.2, 0.2, 0.6)    # провода по Y от оси линии
SAG = 0.9                          # стрела провеса целого провода
BROKEN = (75, 105)                 # пролёт с оборванным проводом (по X опор); оборвана фаза у тротуара
WIRE_R = 0.018                     # радиус провода (толще настоящего, чтобы было видно издалека)
LAMP_LIGHT_X = (0, 150)            # точечный свет только у фонарей вдоль маршрута игрока — дальше хватает пятен


def evening_materials():
    city.city_materials()
    city.glow(M["lamp"], "#FFD9A0", 6.0)  # плафоны горят
    M["porcelain"] = mat("Изолятор", "#E9EEF2", rough=0.25)
    M["wire"] = mat("Провод", "#3F4246", rough=0.45, metal=0.7)
    M["pole"] = mat("Бетон опоры", "#A9A6A0", rough=0.9)


def wire(mb, pts, r=WIRE_R):
    for a, b in zip(pts, pts[1:]):
        mb.cyl(a, b, r, r, M["wire"], n=5)


def sagging(a, b, n=12):
    """Точки провода между двумя изоляторами с провесом"""
    return [a.lerp(b, k / n) - V((0, 0, SAG * 4 * (k / n) * (1 - k / n))) for k in range(n + 1)]


def insulator(x, y):
    return V((x, y, ARM_Z + 0.22))  # точка крепления провода — верх изолятора


def build_line():
    mb = MB("power_line")
    for i, x in enumerate(POLE_XS):
        pole = MB(f"wall_pole_{i}")
        pole.cyl((x, LINE_Y, 0), (x, LINE_Y, POLE_H), 0.16, 0.1, M["pole"], n=6)
        pole.build()
        mb.span(x - 0.05, LINE_Y - 0.85, ARM_Z - 0.08, x + 0.05, LINE_Y + 0.85, ARM_Z, M["metal"])  # траверса
        mb.beam((x, LINE_Y, ARM_Z - 0.9), (x, LINE_Y - 0.7, ARM_Z - 0.06), 0.05, 0.05, M["metal"])  # подкос
        for dy in PHASES:
            p = V((x, LINE_Y + dy, ARM_Z))
            mb.cyl(p, p + V((0, 0, 0.1)), 0.05, 0.05, M["metal"], n=6)
            mb.cyl(p + V((0, 0, 0.1)), p + V((0, 0, 0.22)), 0.07, 0.05, M["porcelain"], n=8)
    for a, b in zip(POLE_XS, POLE_XS[1:]):
        for dy in PHASES:
            if (a, b) == BROKEN and dy == PHASES[0]:
                continue
            wire(mb, sagging(insulator(a, LINE_Y + dy), insulator(b, LINE_Y + dy)))
    mb.build()


def build_broken_wire():
    """Оборванный провод: кусок от опоры BROKEN[0] свисает и лежит поперёк газона и тротуара, конец искрит;
    кусок от опоры BROKEN[1] свисает на газон. Карточки осматриваются издалека — подходить ближе 8 м нельзя"""
    a, b = BROKEN
    y = LINE_Y + PHASES[0]
    top = insulator(a, y)
    down = [top, top + V((0.3, 0.05, -1.5)), top + V((0.8, 0.15, -3.8)), top + V((1.4, 0.3, -6.2)),
            V((a + 1.9, y + 0.4, 0.6)), V((a + 2.2, y + 0.45, 0.03))]
    ground = [V((a + 3.5, y + 1.2, 0.03)), V((a + 5.0, y + 2.4, 0.03)), V((a + 6.4, y + 3.3, 0.05)),
              V((a + 7.6, y + 4.6, 0.03)), V((a + 8.4, y + 6.0, 0.06)), V((a + 9.6, y + 6.9, 0.07))]
    mb = MB("item_wire-down")
    wire(mb, down + ground)
    mb.build()["inspect_range"] = 8.0
    empty("spark_src", ground[-1] + V((0, 0, 0.05)))

    top = insulator(b, y)
    pts = [top, top + V((-0.2, 0.05, -2.0)), top + V((-0.6, 0.1, -4.5)), top + V((-1.0, 0.2, -7.0)),
           V((b - 1.4, y + 0.25, 0.4)), V((b - 1.7, y + 0.3, 0.03)), V((b - 3.2, y - 0.4, 0.03)),
           V((b - 4.6, y - 0.1, 0.03)), V((b - 6.0, y - 0.9, 0.04))]
    mb = MB("item_wire-hanging")
    wire(mb, pts)
    mb.build()["inspect_range"] = 8.0


def build_lamp_lights():
    """Пустышки под фонарями (те же места, что в city.street_furniture): пятна света на земле и свет у маршрута"""
    n = 0
    for x in range(city.X0 + 4, city.X1, 16):
        for lx, ly in ((x, city.CURB_NEAR - 0.5 + 1.3), (x + 8, city.CURB_FAR + 0.5 - 1.3)):
            empty(f"glow_{n}", (lx, ly, 0.05))
            if LAMP_LIGHT_X[0] <= lx <= LAMP_LIGHT_X[1] and ly < 0:
                empty(f"lamp_{n}", (lx, ly, 6.0))
            n += 1


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    evening_materials()
    city.build_street(hatch=False)
    city.street_furniture()
    city.build_doma()
    city.build_near_side()
    city.place_trees()
    city.place_kusty()
    build_line()
    build_broken_wire()
    build_lamp_lights()
    city.build_templates()

    empty("spawn_A", (27.0, -4.6, 0))   # на ближнем тротуаре между кадкой (x = 16) и фонарём (x = 24) за спиной
    empty("goal_B", (66.0, -5.0, 0))    # на тротуаре, не ближе 8 м к оборванному проводу
    empty("walk_min", (8, -15.0, 0))
    empty("walk_max", (170, city.CURB_FAR - 0.4, 0))

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_extras=True, export_apply=True)


build()
print("Готово:", OUT_GLB, OUT_BLEND)
