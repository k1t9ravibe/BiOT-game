"""
Сборка 3D-сцены «Опора у сельской АТС» для режима ходьбы (/walk?scene=t1).
Персонаж игрока (public/models/worker.glb) собирает blender/build_worker.py из готовой модели.

Запуск (из корня проекта):
    blender --background --python blender/build_t1.py

Результат:
    public/models/t1.glb      — сцена для игры
    blender/t1_pole.blend     — исходник сцены, можно открыть и доработать в Blender руками

Соглашение об именах объектов (игра читает их из .glb):
    item_<id>   — объект, который можно осмотреть; <id> совпадает с id карточки в public/tasks.json
                  (нарушение это или нет, берётся из tasks.json, а не из имени)
    wall_*      — препятствие, сквозь которое нельзя пройти
    solid = 1   — пользовательское свойство (Object Properties → Custom Properties): тоже препятствие
    spawn_A     — точка старта игрока, goal_B — точка финиша
"""

import math
import os

import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_MODELS = os.path.join(ROOT, "public", "models")
OUT_BLEND = os.path.join(ROOT, "blender", "t1_pole.blend")
os.makedirs(OUT_MODELS, exist_ok=True)

rad = math.radians


# ---------- Вспомогательные функции ----------

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def srgb(h):
    """#RRGGBB → линейный цвет (так его ждёт glTF)"""
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


def mat(name, hex_color, rough=0.85, metal=0.0, emit=None):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    col = (*srgb(hex_color), 1)
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*srgb(emit), 1)
        b.inputs["Emission Strength"].default_value = 1.0
    m.diffuse_color = col
    return m


def _finish(o, name, material):
    o.name = name
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        o.data.materials.append(material)
    return o


def box(name, size, loc, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.scale = size
    return _finish(o, name, material)


def cyl(name, r, depth, loc, material, rot=(0, 0, 0), verts=14):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    return _finish(bpy.context.object, name, material)


def sphere(name, r, loc, material, scale=(1, 1, 1), seg=14):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=max(6, seg // 2), radius=r, location=loc)
    o = bpy.context.object
    o.scale = scale
    return _finish(o, name, material)


def cone(name, r, depth, loc, material, verts=10):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, depth=depth, location=loc)
    return _finish(bpy.context.object, name, material)


def rod(name, p1, p2, r, material, verts=8):
    """Цилиндр между двумя точками (кабель, провод)"""
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d.length, location=(p1 + p2) / 2)
    o = bpy.context.object
    o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    return _finish(o, name, material)


def prism(name, w, d, h, loc, material):
    """Двускатная крыша: треугольная призма, конёк вдоль X"""
    x, y = w / 2, d / 2
    verts = [(-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0), (-x, 0, h), (x, 0, h)]
    faces = [(0, 1, 5, 4), (2, 3, 4, 5), (0, 4, 3), (1, 2, 5), (0, 3, 2, 1)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.data.materials.append(material)
    return o


def join(objs, name, origin=(0, 0, 0)):
    """Склеить объекты в один; точка опоры (origin) — в указанной точке"""
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    bpy.context.scene.cursor.location = origin
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    bpy.context.scene.cursor.location = (0, 0, 0)
    return o


def empty(name, loc):
    o = bpy.data.objects.new(name, None)
    o.empty_display_type = "PLAIN_AXES"
    o.location = loc
    bpy.context.collection.objects.link(o)
    return o


def solid(o):
    o["solid"] = 1
    return o


# ---------- Персонаж ----------

M = {}


def materials():
    M.update(
        uniform=mat("Спецодежда", "#1B3A73"),
        stripe=mat("Светоотражающие полосы", "#D9DEE6", rough=0.35),
        logo=mat("Логотип", "#FFFFFF", rough=0.5),
        skin=mat("Кожа", "#E0AC88"),
        hair=mat("Волосы", "#3B2A20"),
        boots=mat("Ботинки", "#1E1E22"),
        helmet=mat("Каска", "#F4F6F8", rough=0.3),
        grass=mat("Трава", "#A9BC63"),
        dirt=mat("Грунт", "#9C7B55"),
        brick=mat("Кирпич", "#B0603F"),
        concrete=mat("Бетон", "#8C8F94"),
        metal=mat("Металл", "#5E6670", rough=0.5, metal=0.4),
        cabinet=mat("Шкаф", "#B9C0C8", rough=0.5, metal=0.3),
        glass=mat("Стекло", "#2D4B6E", rough=0.15),
        wood=mat("Дерево", "#7A5534"),
        ladder=mat("Лестница", "#C99A4B"),
        fence=mat("Забор", "#2F6FD0"),
        white=mat("Белый кузов", "#F3F4F6", rough=0.4),
        tyre=mat("Шины", "#23252A"),
        drum=mat("Барабан", "#9A6B3F"),
        cable=mat("Кабель", "#202226", rough=0.6),
        red=mat("Красный", "#D23B2F", rough=0.5),
        orange=mat("Оранжевый", "#F28C28", rough=0.5),
        house=mat("Стены дома", "#EFE6D2"),
        roof=mat("Кровля", "#3E6E8E"),
        roof2=mat("Кровля 2", "#8E3E3E"),
        leaf=mat("Листва", "#5E8F3A"),
    )


def build_worker(helmet=True):
    """
    Монтёр ростом ~1.8 м, смотрит в −Y (в three.js это +Z).
    Возвращает словарь частей; у рук и ног точка опоры — в плече/бедре, чтобы их можно было вращать.
    """
    parts = {}

    # Ноги (опора в бедре на высоте 0.95)
    for side, x in (("L", 0.13), ("R", -0.13)):
        leg = box(f"leg_{side}_m", (0.2, 0.24, 0.82), (x, 0, 0.54), M["uniform"])
        stripe = box(f"leg_{side}_s", (0.21, 0.25, 0.05), (x, 0, 0.42), M["stripe"])
        boot = box(f"leg_{side}_b", (0.22, 0.34, 0.14), (x, -0.04, 0.07), M["boots"])
        parts[f"leg_{side}"] = join([leg, stripe, boot], f"leg_{side}", origin=(x, 0, 0.95))

    # Туловище: куртка, полосы, белый логотип на спине (+Y)
    torso = [
        box("torso_m", (0.52, 0.3, 0.62), (0, 0, 1.25), M["uniform"]),
        box("torso_s1", (0.53, 0.31, 0.06), (0, 0, 1.12), M["stripe"]),
        box("torso_s2", (0.53, 0.31, 0.06), (0, 0, 1.38), M["stripe"]),
        box("torso_logo", (0.2, 0.02, 0.13), (0, 0.16, 1.25), M["logo"]),
        box("belt", (0.53, 0.31, 0.06), (0, 0, 0.97), M["boots"]),
    ]
    parts["torso"] = join(torso, "torso", origin=(0, 0, 0.95))

    # Руки (опора в плече на высоте 1.5)
    for side, x in (("L", 0.34), ("R", -0.34)):
        arm = box(f"arm_{side}_m", (0.15, 0.17, 0.6), (x, 0, 1.22), M["uniform"])
        stripe = box(f"arm_{side}_s", (0.16, 0.18, 0.05), (x, 0, 1.2), M["stripe"])
        hand = sphere(f"arm_{side}_h", 0.07, (x, 0, 0.88), M["skin"], seg=10)
        parts[f"arm_{side}"] = join([arm, stripe, hand], f"arm_{side}", origin=(x, 0, 1.5))

    # Голова; каска — только у игрока (у монтёра на лестнице её нет — это нарушение)
    head = [
        cyl("neck", 0.07, 0.1, (0, 0, 1.6), M["skin"], verts=10),
        sphere("head_m", 0.15, (0, 0, 1.75), M["skin"]),
        sphere("hair", 0.152, (0, 0.03, 1.79), M["hair"], scale=(1, 1, 0.8)),
    ]
    if helmet:
        head += [
            sphere("helmet_dome", 0.175, (0, 0, 1.8), M["helmet"], scale=(1, 1.08, 0.85)),
            cyl("helmet_brim", 0.2, 0.02, (0, -0.03, 1.74), M["helmet"], verts=18),
            box("helmet_strap", (0.31, 0.02, 0.02), (0, -0.05, 1.66), M["boots"]),
        ]
    parts["head"] = join(head, "head", origin=(0, 0, 1.6))
    return parts


# ---------- Сцена t1 ----------

def build_scene():
    reset()
    materials()

    # Земля и тропинка от фургона к опоре
    box("ground", (70, 70, 0.1), (0, 0, -0.05), M["grass"])
    box("path", (2.2, 9.5, 0.02), (-1.2, -1.2, 0.01), M["dirt"], rot=(0, 0, rad(-35)))

    # Здание сельской АТС: кирпич, плоская крыша, металлическая дверь, окна, мачта на крыше
    ats = [
        box("ats_walls", (6.4, 4.6, 3.2), (-4.5, 7.5, 1.6), M["brick"]),
        box("ats_roof", (6.8, 5.0, 0.25), (-4.5, 7.5, 3.32), M["concrete"]),
        box("ats_plinth", (6.6, 4.8, 0.35), (-4.5, 7.5, 0.17), M["concrete"]),
        box("ats_door", (1.1, 0.06, 2.1), (-3.0, 5.18, 1.05), M["metal"]),
        box("ats_win1", (1.2, 0.06, 0.9), (-5.6, 5.18, 1.9), M["glass"]),
        box("ats_win2", (0.9, 0.06, 0.9), (-6.9, 5.18, 1.9), M["glass"]),
        box("ats_canopy", (1.6, 0.8, 0.08), (-3.0, 4.85, 2.35), M["concrete"]),
        cyl("ats_mast", 0.06, 3.0, (-6.2, 8.6, 4.9), M["metal"]),
        box("ats_dish", (0.5, 0.1, 0.5), (-6.2, 8.5, 6.0), M["white"]),
    ]
    join(ats, "wall_ats", origin=(-4.5, 7.5, 0))

    # Деревянная опора связи с траверсой и открытым распределительным шкафом
    PX, PY = 3.0, 5.0
    pole = [
        cyl("pole_m", 0.15, 8.0, (PX, PY, 4.0), M["wood"]),
        box("pole_arm", (1.6, 0.12, 0.12), (PX, PY, 7.5), M["wood"]),
        cyl("ins1", 0.05, 0.18, (PX - 0.65, PY, 7.65), M["white"], verts=8),
        cyl("ins2", 0.05, 0.18, (PX + 0.65, PY, 7.65), M["white"], verts=8),
    ]
    solid(join(pole, "wall_pole", origin=(PX, PY, 0)))
    cab = [
        box("cab_body", (0.7, 0.32, 0.9), (PX, PY - 0.32, 3.2), M["cabinet"]),
        box("cab_inside", (0.6, 0.02, 0.8), (PX, PY - 0.49, 3.2), M["glass"]),
        # Открытая дверца, повёрнута почти на 100°
        box("cab_door", (0.04, 0.68, 0.88), (PX + 0.37, PY - 0.82, 3.2), M["cabinet"]),
    ]
    join(cab, "cabinet", origin=(PX, PY, 0))
    # Провода к зданию АТС
    rod("wire1", (PX - 0.65, PY, 7.7), (-2.0, 7.5, 3.5), 0.015, M["cable"])
    rod("wire2", (PX + 0.65, PY, 7.7), (12, 9, 7.6), 0.015, M["cable"])
    rod("wire3", (PX - 0.65, PY, 7.7), (-14, 2, 7.6), 0.015, M["cable"])

    # НАРУШЕНИЕ: лестница под неправильным углом (~55° вместо 75°) на неровной земле (кочка)
    L, tilt = 5.0, 35.0
    base = Vector((PX, PY - 0.2 - L * math.sin(rad(tilt)), 0.18))
    rails = [
        box("rail_l", (0.07, 0.07, L), (-0.25, 0, L / 2), M["ladder"]),
        box("rail_r", (0.07, 0.07, L), (0.25, 0, L / 2), M["ladder"]),
    ]
    rungs = [box(f"rung{i}", (0.5, 0.05, 0.05), (0, 0, 0.3 + i * 0.32), M["ladder"]) for i in range(15)]
    ladder = join(rails + rungs, "item_ladder-angle")
    ladder.rotation_euler = (rad(-tilt), rad(6), 0)  # 6° вбок — стоит на кочке
    ladder.location = base
    sphere("mound", 0.75, (base.x + 0.15, base.y, 0.0), M["dirt"], scale=(1.2, 1, 0.28))

    # НАРУШЕНИЕ: монтёр на лестнице без каски; спецодежда в порядке — отвлекающий вариант
    parts = build_worker(helmet=False)
    parts["arm_L"].rotation_euler = (rad(-125), 0, 0)
    parts["arm_R"].rotation_euler = (rad(-105), 0, 0)
    parts["leg_R"].rotation_euler = (rad(-35), 0, 0)
    for p in parts.values():
        bpy.ops.object.select_all(action="DESELECT")
        p.select_set(True)
        bpy.context.view_layer.objects.active = p
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    s = 2.4  # метров вверх по лестнице
    npc_pos = (PX, base.y + s * math.sin(rad(tilt)) - 0.25, base.z + s * math.cos(rad(tilt)))
    head = join([parts["head"]], "item_no-helmet")
    body = join([parts["torso"], parts["leg_L"], parts["leg_R"], parts["arm_L"], parts["arm_R"]], "item_workwear-ok")
    for o in (head, body):
        o.rotation_euler = (rad(12), 0, rad(180))  # лицом к опоре, корпус наклонён к лестнице
        o.location = npc_pos

    # НАРУШЕНИЕ: кабельный барабан без домкратов и клиньев, кабель тянется к опоре
    DX, DY = 6.6, 1.2
    drum = [
        cyl("drum_d1", 0.75, 0.08, (DX - 0.42, DY, 0.75), M["drum"], rot=(0, rad(90), 0), verts=20),
        cyl("drum_d2", 0.75, 0.08, (DX + 0.42, DY, 0.75), M["drum"], rot=(0, rad(90), 0), verts=20),
        cyl("drum_core", 0.55, 0.78, (DX, DY, 0.75), M["cable"], rot=(0, rad(90), 0), verts=20),
    ]
    solid(join(drum, "item_drum-unsecured", origin=(DX, DY, 0)))
    rod("cable_run", (DX - 0.3, DY + 0.3, 0.25), (PX + 0.15, PY - 0.1, 0.05), 0.035, M["cable"])
    rod("cable_up", (PX + 0.15, PY - 0.15, 0.05), (PX + 0.15, PY - 0.2, 2.8), 0.03, M["cable"])

    # НАРУШЕНИЕ: инструмент разбросан у основания опоры (крупно, чтобы было видно)
    tools = [
        box("toolbox", (0.6, 0.32, 0.3), (1.2, 2.6, 0.15), M["red"], rot=(0, rad(80), rad(20))),
        box("wrench", (0.07, 0.5, 0.03), (1.9, 1.6, 0.03), M["metal"], rot=(0, 0, rad(40))),
        box("hammer_h", (0.06, 0.45, 0.05), (0.8, 1.7, 0.03), M["wood"], rot=(0, 0, rad(-25))),
        box("hammer_t", (0.22, 0.08, 0.08), (0.7, 1.92, 0.05), M["metal"], rot=(0, 0, rad(-25))),
        box("screwdriver", (0.05, 0.4, 0.05), (2.3, 2.3, 0.03), M["orange"], rot=(0, 0, rad(70))),
        box("pliers", (0.12, 0.3, 0.03), (1.5, 3.2, 0.03), M["red"], rot=(0, 0, rad(10))),
        cyl("tape", 0.12, 0.08, (2.0, 2.9, 0.04), M["orange"]),
    ]
    join(tools, "item_tools-scattered", origin=(1.5, 2.4, 0)).scale = (1.6, 1.6, 1.6)

    # Отвлекающий вариант: служебный фургон стоит в стороне
    VX, VY = -6.5, -3.5
    van = [
        box("van_body", (4.6, 2.0, 1.9), (VX, VY, 1.35), M["white"]),
        box("van_cab", (1.0, 2.0, 1.2), (VX + 2.75, VY, 1.0), M["white"]),
        box("van_wind", (0.06, 1.8, 0.6), (VX + 3.27, VY, 1.4), M["glass"]),
        box("van_side_win", (0.9, 0.04, 0.55), (VX + 2.6, VY - 1.0, 1.5), M["glass"]),
        box("van_stripe", (4.6, 2.02, 0.15), (VX, VY, 1.05), M["fence"]),
    ]
    for i, (wx, wy) in enumerate([(-1.4, -1.0), (1.8, -1.0), (-1.4, 1.0), (1.8, 1.0)]):
        van.append(cyl(f"wheel{i}", 0.4, 0.28, (VX + wx, VY + wy, 0.4), M["tyre"], rot=(rad(90), 0, 0), verts=16))
    solid(join(van, "item_van-ok", origin=(VX, VY, 0)))

    # Синий деревянный забор
    fence = []
    for i in range(14):
        fence.append(box(f"post{i}", (0.12, 0.12, 1.8), (-13 + i * 2.0, 12.5, 0.9), M["wood"]))
    for z in (0.5, 1.4):
        fence.append(box(f"rail{z}", (26, 0.06, 0.1), (0, 12.45, z), M["fence"]))
    for i in range(86):
        fence.append(box(f"board{i}", (0.22, 0.03, 1.6), (-12.9 + i * 0.3, 12.4, 0.85), M["fence"]))
    join(fence, "wall_fence", origin=(0, 12.5, 0))

    # Частные дома за забором
    for i, (hx, roof) in enumerate([(-9, M["roof"]), (0, M["roof2"]), (9, M["roof"])]):
        h = [
            box(f"house{i}", (6, 5, 2.8), (hx, 17.5, 1.4), M["house"]),
            prism(f"house{i}_roof", 6.6, 5.6, 1.8, (hx, 17.5, 2.8), roof),
            box(f"house{i}_win", (1.0, 0.06, 0.9), (hx - 1.5, 14.98, 1.6), M["glass"]),
            box(f"house{i}_win2", (1.0, 0.06, 0.9), (hx + 1.5, 14.98, 1.6), M["glass"]),
        ]
        join(h, f"wall_house_{i}", origin=(hx, 17.5, 0))

    # Деревья
    for i, (tx, ty) in enumerate([(-13, 4), (-12, -6), (12, 5), (11, -7), (14, 0)]):
        t = [cyl(f"trunk{i}", 0.18, 1.6, (tx, ty, 0.8), M["wood"], verts=8), cone(f"crown{i}", 1.4, 3.4, (tx, ty, 3.2), M["leaf"])]
        solid(join(t, f"wall_tree_{i}", origin=(tx, ty, 0)))

    # Точки маршрута: старт у фургона, финиш у опоры
    empty("spawn_A", (-3.6, -5.2, 0))
    empty("goal_B", (1.0, 1.0, 0))

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT_MODELS, "t1.glb"), export_format="GLB", export_extras=True)


build_scene()
print("Готово:", OUT_MODELS, OUT_BLEND)
