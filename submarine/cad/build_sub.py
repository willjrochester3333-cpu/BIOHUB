#!/usr/bin/env python3
"""
build_sub.py - parametric CAD model of the "Minnow" mini torpedo AUV.

Works in Blender 4.2 LTS or newer (tested with 4.5 LTS):

  * In the Blender UI: open this file in the Text Editor and press Run Script.
    The whole submarine is built in the current scene.
  * Headless:   blender -b -P build_sub.py -- --stl --render --blend
  * As a module: python3.11 build_sub.py --stl --render --blend   (pip install bpy)

Flags (all optional):
  --stl      export every 3D-printed part as a print-ready STL (cad/stl/)
  --render   render the beauty / cutaway / detail images (cad/renders/)
  --blend    save cad/minnow_auv.blend
  --quick    low sample count renders (for testing)
  --out DIR  output folder (default: the folder this script lives in)

Units: 1 Blender unit = 1 mm. Vehicle axes: +X forward (nose), +Y port (left),
+Z up. The hull axis is the X axis.

Everything is driven by the parameter block P below. The most important
numbers to MEASURE on your own parts before printing are marked "MEASURE".
"""
import bpy
import bmesh
import json
import math
import os
import struct
import sys
from math import pi, sin, cos, tan, atan, sqrt, radians
from mathutils import Vector, Matrix

# =============================================================================
# PARAMETERS  (mm, grams)
# =============================================================================
P = dict(
    # --- Pressure hull: PVC-U pressure pipe ---------------------------------
    pipe_od=90.0,          # MEASURE. Metric PVC-U pressure pipe OD (tight tolerance)
    pipe_wall=4.3,         # MEASURE. PN10 = 4.3 mm, PN16 = 6.7 mm
    pipe_len=380.0,        # cut square; chamfer both outer edges ~1.5 mm x 15 deg
    # --- O-ring sleeve end caps (O-rings seal on the pipe OD) ---------------
    oring_cs=3.53,         # AS568-238 (88.49 x 3.53) or metric 89 x 3.5
    oring_squeeze=0.20,    # 20 % radial squeeze (static seal)
    groove_w_factor=1.40,  # groove width = 1.4 x cross-section
    cap_bore_clear=0.20,   # radial clearance between cap bore and pipe OD
    cap_sleeve_len=32.0,   # how far each cap slides over the pipe
    cap_outer_wall=3.0,    # wall outside the O-ring grooves
    groove1=10.0,          # groove centres measured from the cap's open end
    groove2=20.0,
    # front cap (camera window)
    front_wall=14.0,
    window_d=80.0,         # 8 mm CAST acrylic disc, laser cut
    window_t=8.0,
    window_recess_clear=0.3,
    window_seat_w=2.0,
    aperture_d=70.0,       # clear aperture in front of the camera lens
    # rear cap (penetrators)
    rear_wall=8.0,
    rear_chamfer=3.0,      # 45 deg chamfer the tail cone seats on
    gland_ring_r=26.0,     # radius of the ring of M12 glands
    gland_tap_d=10.5,      # tap drill for M12x1.5 (tap the printed holes)
    depth_hole_d=10.3,     # clearance for the M10 depth-sensor body (nut inside)
    boss_r=36.0, boss_d=7.0, boss_len=8.0,   # sled mounting bosses (M3 inserts)
    # --- Frame -----------------------------------------------------------------
    clamp_w=16.0, clamp_wall=8.0, clamp_gap=1.0,
    clamp_front_x=143.0, clamp_mid_x=0.0, clamp_rear_x=-143.0,
    ear_out=62.0, ear_h=8.0,
    keel_w=25.0, keel_t=3.0, keel_x0=-170.0, keel_x1=200.0,
    pod_l=120.0, pod_w=34.0, pod_h=32.0, pod_wall=2.4,
    # --- Thrusters (A2212 outrunner in a printed duct) ----------------------
    duct_id=54.0, duct_wall=3.0, duct_len=40.0, thruster_y=94.0,
    prop_d=51.0, prop_pitch=42.0, prop_hub_d=12.0, prop_hub_len=8.0,
    prop_bore_d=5.2, prop_blades=3,
    motor_bell_d=27.7, motor_len=26.0,
    # --- Mast (GPS + LoRa antenna + strobe, potted) --------------------------
    mast_chord=40.0, mast_thick=14.0, mast_h=58.0, puck_d=36.0, puck_h=12.0,
    # --- Camera: GoPro HERO5/6/7 Black body (MEASURE if you use another) ----
    cam_w=62.3, cam_h=44.9, cam_d=33.0,
    cam_lens_y=-14.0, cam_lens_z=0.0,   # lens offset from body centre (looking forward)
    cam_bump=5.0, cam_bump_w=22.0, cam_gap=1.0,
    # --- Internals -----------------------------------------------------------
    batt_l=65.0, batt_w=56.0, batt_h=19.0, batt_count=2,   # 3S1P 18650 flat packs
    pcb_l=150.0, pcb_w=60.0, pcb_x0=-62.0, pcb_z=4.0,   # matches pcb/design.py
    rod_y=33.0, rod_z=-9.0, rod_d=6.0,
    # --- Trim ------------------------------------------------------------------
    reserve_buoyancy_g=45.0,  # how much it should float when switched off
    seg=192,                  # segments on sealing surfaces
)

# densities g/cm3
RHO = dict(pvc=1.40, petg=1.27, acrylic=1.19, alu=2.70, lead=11.34,
           water=0.998, nbr=1.20, nylon=1.14, brass=8.5)


def derived(p):
    """Compute derived dimensions from the parameter block."""
    d = {}
    d['ro_pipe'] = p['pipe_od'] / 2
    d['ri_pipe'] = p['pipe_od'] / 2 - p['pipe_wall']
    d['x_front'] = p['pipe_len'] / 2
    d['x_rear'] = -p['pipe_len'] / 2
    d['rb'] = d['ro_pipe'] + p['cap_bore_clear']                      # cap bore radius
    d['gap'] = p['oring_cs'] * (1 - p['oring_squeeze'])               # radial gland depth
    d['rg'] = d['ro_pipe'] + d['gap']                                 # groove bottom radius
    d['gw'] = p['oring_cs'] * p['groove_w_factor']
    d['ro_cap'] = d['rg'] + p['cap_outer_wall']
    d['oring_id_target'] = p['pipe_od'] - 1.0
    d['x_front_face'] = d['x_front'] + p['front_wall']
    d['x_rear_face'] = d['x_rear'] - p['rear_wall']
    d['rw'] = (p['window_d'] + p['window_recess_clear']) / 2
    d['rs'] = d['rw'] - p['window_seat_w']
    d['ra'] = p['aperture_d'] / 2
    d['duct_ri'] = p['duct_id'] / 2
    d['duct_ro'] = p['duct_id'] / 2 + p['duct_wall']
    d['clamp_ro'] = d['ro_pipe'] + p['clamp_wall']
    groove_area = d['gw'] * d['gap']
    d['gland_fill'] = (pi / 4 * p['oring_cs'] ** 2) / groove_area
    return d


D = derived(P)

# Which electronics board the model shows: 'carrier' = rev 1 (../pcb, reed switch on the hull top,
# separate IMU breakout), 'core' = Minnow Core (../pcb-core, everything on the board, magnet
# sensor on the board's port edge). Set with --core on the command line.
BOARD = {'name': 'carrier'}
CORE_MAGNET_BX = 8.5      # pcb-core/design.py MAGNET_SENSOR_BXBY


def pcb_dir():
    return 'pcb-core' if BOARD['name'] == 'core' else 'pcb'

# =============================================================================
# LOW LEVEL MESH HELPERS
# =============================================================================


def rev_bm(profile, segs):
    """Solid of revolution about the X axis from a closed (x, r) profile."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, r, 0.0)) for x, r in profile]
    es = [bm.edges.new((vs[i], vs[(i + 1) % len(vs)])) for i in range(len(vs))]
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(1, 0, 0),
                   angle=2 * pi, steps=segs, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def bm_box(bm, x0, x1, y0, y1, z0, z1):
    M = (Matrix.Translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)) @
         Matrix.Diagonal((abs(x1 - x0), abs(y1 - y0), abs(z1 - z0), 1.0)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=M)
    return bm


def bm_cyl(bm, p0, p1, r, segs=48, r2=None):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    M = Matrix.Translation((p0 + p1) / 2) @ q.to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs,
                          radius1=r, radius2=r if r2 is None else r2,
                          depth=d.length, matrix=M)
    return bm


def bm_prism(bm, poly2d, z0, z1, plane='XY'):
    """Extrude a 2D polygon. plane='XY' -> extrude along Z, 'YZ' -> along X,
    'XZ' -> along Y. poly2d coordinates are (a, b) in that plane."""
    def P3(a, b, c):
        if plane == 'XY':
            return (a, b, c)
        if plane == 'YZ':
            return (c, a, b)
        return (a, c, b)  # XZ
    n = len(poly2d)
    bot = [bm.verts.new(P3(a, b, z0)) for a, b in poly2d]
    top = [bm.verts.new(P3(a, b, z1)) for a, b in poly2d]
    bm.faces.new(bot[::-1])
    bm.faces.new(top)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    return bm


def bm_transform(bm, M):
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    if M.to_3x3().determinant() < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    return bm


def finish(bm):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


COLL = {}


def coll(name):
    if name not in COLL:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
        COLL[name] = c
    return COLL[name]


def mkobj(name, bm, collection, mat, props=None, smooth=30):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll(collection).objects.link(ob)
    if mat is not None:
        me.materials.append(mat)
    for k, v in (props or {}).items():
        ob[k] = v
    shade(ob, smooth)
    return ob


def shade(ob, angle=30):
    me = ob.data
    if angle is None:
        return
    try:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=radians(angle))
    except (AttributeError, TypeError):
        for p in me.polygons:
            p.use_smooth = True


def boolean(ob, cutter_bm, op='DIFFERENCE', solver='EXACT'):
    cme = bpy.data.meshes.new('_cutter')
    cutter_bm.to_mesh(cme)
    cutter_bm.free()
    cob = bpy.data.objects.new('_cutter', cme)
    bpy.context.scene.collection.objects.link(cob)
    m = ob.modifiers.new('bool', 'BOOLEAN')
    m.operation = op
    m.object = cob
    m.solver = solver
    if solver == 'EXACT':
        m.use_self = True
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.remove(m)
    old = ob.data
    ob.data = me
    me.name = ob.name
    bpy.data.objects.remove(cob)
    bpy.data.meshes.remove(cme)
    bpy.data.meshes.remove(old)
    return ob


def ob_bm(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    return bm


def mesh_volume_centroid(ob):
    """Volume (cm3) and centroid (mm) of a closed mesh, world space."""
    bm = ob_bm(ob)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    V = 0.0
    C = Vector((0, 0, 0))
    for f in bm.faces:
        a, b, c = (v.co for v in f.verts)
        v = a.dot(b.cross(c)) / 6.0
        V += v
        C += v * (a + b + c) / 4.0
    bm.free()
    if abs(V) < 1e-9:
        return 0.0, Vector((0, 0, 0))
    return abs(V) / 1000.0, C / V


# =============================================================================
# MATERIALS
# =============================================================================
MAT = {}


def material(name, color, rough=0.5, metal=0.0, transmission=0.0, ior=1.45,
             alpha=1.0, emission=None, coat=0.0):
    if name in MAT:
        return MAT[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    for key in ('Transmission Weight', 'Transmission'):
        if key in b.inputs:
            b.inputs[key].default_value = transmission
            break
    b.inputs['IOR'].default_value = ior
    if 'Coat Weight' in b.inputs:
        b.inputs['Coat Weight'].default_value = coat
    if alpha < 1.0:
        b.inputs['Alpha'].default_value = alpha
    if emission:
        b.inputs['Emission Color'].default_value = (*emission[0], 1.0)
        b.inputs['Emission Strength'].default_value = emission[1]
    m.diffuse_color = (*color, 1.0)
    MAT[name] = m
    return m


def make_materials():
    material('hull_orange', (0.95, 0.30, 0.04), rough=0.35, coat=0.3)
    material('petg_dark', (0.035, 0.037, 0.042), rough=0.45)
    material('pvc_grey', (0.42, 0.44, 0.46), rough=0.55)
    material('decal_white', (0.92, 0.92, 0.90), rough=0.4)
    material('petg_grey', (0.45, 0.47, 0.50), rough=0.5)
    material('petg_yellow', (0.95, 0.70, 0.05), rough=0.45)
    material('petg_white', (0.85, 0.86, 0.85), rough=0.35, transmission=0.25)
    material('acrylic', (0.95, 0.97, 1.0), rough=0.01, transmission=1.0, ior=1.49)
    material('alu', (0.80, 0.81, 0.83), rough=0.28, metal=1.0)
    material('steel', (0.62, 0.63, 0.65), rough=0.22, metal=1.0)
    material('brass', (0.86, 0.66, 0.30), rough=0.3, metal=1.0)
    material('lead', (0.30, 0.31, 0.33), rough=0.7, metal=0.4)
    material('rubber', (0.012, 0.012, 0.012), rough=0.8)
    material('nylon_black', (0.03, 0.03, 0.03), rough=0.55)
    material('motor_bell', (0.75, 0.55, 0.20), rough=0.25, metal=1.0)
    material('copper', (0.85, 0.42, 0.20), rough=0.35, metal=1.0)
    material('pcb_green', (0.03, 0.20, 0.08), rough=0.35, coat=0.5)
    material('pcb_black', (0.02, 0.02, 0.025), rough=0.35, coat=0.5)
    material('battery_blue', (0.05, 0.22, 0.65), rough=0.4)
    material('gopro', (0.06, 0.06, 0.065), rough=0.6)
    material('glass_dark', (0.01, 0.01, 0.015), rough=0.05, coat=1.0)
    material('cable', (0.02, 0.02, 0.02), rough=0.5)
    material('red', (0.7, 0.03, 0.02), rough=0.4)
    material('foam', (0.02, 0.02, 0.02), rough=1.0)
    material('floor', (0.86, 0.87, 0.88), rough=0.6)


# =============================================================================
# PART BUILDERS
# =============================================================================

def build_pipe():
    ro, ri = D['ro_pipe'], D['ri_pipe']
    x0, x1 = D['x_rear'], D['x_front']
    prof = [(x0, ri), (x0, ro - 0.5), (x0 + 1.5, ro), (x1 - 1.5, ro), (x1, ro - 0.5), (x1, ri)]
    ob = mkobj('Hull_PVC_pipe', rev_bm(prof, P['seg']), 'Hull', MAT['hull_orange'],
               dict(kind='pressure', material='pvc', fill=1.0, buy=True))
    ob.data.materials.append(MAT['pvc_grey'])
    for poly in ob.data.polygons:       # paint is only on the outside
        c = poly.center
        if sqrt(c.y ** 2 + c.z ** 2) < ro - 0.6:
            poly.material_index = 1
    return ob


def cap_bore_points(x_open, direction):
    """Bore of a cap sleeve with two O-ring grooves, listed from the dry end
    toward the open end. direction=+1 for the front cap (sleeve extends +X from
    the open end), -1 for the rear cap."""
    rb, rg, gw = D['rb'], D['rg'], D['gw']
    pts = []
    for gpos in (P['groove2'], P['groove1']):
        xc = x_open + direction * gpos
        a, b = xc + direction * gw / 2, xc - direction * gw / 2
        pts += [(a, rb), (a, rg), (b, rg), (b, rb)]
    pts.append((x_open + direction * 1.0, rb))
    return pts


def build_front_cap():
    xo = D['x_front'] - P['cap_sleeve_len']
    xs = D['x_front']
    xf = D['x_front_face']
    rb, ro, rw, rs, ra = D['rb'], D['ro_cap'], D['rw'], D['rs'], D['ra']
    tw = P['window_t']
    x_seat = xf - tw
    x_ch = x_seat - (rs - ra)          # 45 deg chamfer so it prints without support
    prof = [(xo, rb + 1.0), (xo, ro - 0.8), (xo + 0.8, ro), (xf - 1.0, ro), (xf, ro - 1.0),
            (xf, rw), (x_seat, rw), (x_seat, rs), (max(x_ch, xs + 0.5), ra), (xs, ra), (xs, rb)]
    prof += cap_bore_points(xo, +1)
    ob = mkobj('FrontCap', rev_bm(prof, P['seg']), 'Hull', MAT['petg_dark'],
               dict(kind='pressure', material='petg', fill=1.0, print=True,
                    print_dir=(-1, 0, 0), note='Pressure part: 100% infill, 0.12-0.16 mm layers, '
                    'window face on the bed. Epoxy-coat outside (not the grooves).'))
    return ob


def build_window():
    xf = D['x_front_face']
    r = P['window_d'] / 2
    prof = [(xf - P['window_t'], 0), (xf - P['window_t'], r - 0.5), (xf - P['window_t'] + 0.5, r),
            (xf - 0.5, r), (xf, r - 0.5), (xf, 0)]
    return mkobj('Window_acrylic', rev_bm(prof, 128), 'Hull', MAT['acrylic'],
                 dict(kind='pressure', material='acrylic', fill=1.0, buy=True), smooth=60)


def build_rear_cap():
    xo = D['x_rear'] + P['cap_sleeve_len']
    xr = D['x_rear']
    xb = D['x_rear_face']
    rb, ro, ch = D['rb'], D['ro_cap'], P['rear_chamfer']
    prof = [(xo, rb + 1.0), (xo, ro - 0.8), (xo - 0.8, ro), (xb + ch, ro), (xb, ro - ch),
            (xb, 0.0), (xr, 0.0), (xr, rb)]
    prof += cap_bore_points(xo, -1)
    ob = mkobj('RearCap', rev_bm(prof, P['seg']), 'Hull', MAT['petg_dark'],
               dict(kind='pressure', material='petg', fill=1.0, print=True,
                    print_dir=(1, 0, 0), note='Pressure part: 100% infill, rear face on the bed. '
                    'Tap the 7 ring holes M12x1.5. Epoxy-coat outside.'))
    # sled bosses on the inner face
    bm = bmesh.new()
    for a in rear_boss_angles():
        y, z = P['boss_r'] * sin(a), P['boss_r'] * cos(a)
        bm_cyl(bm, (xr - 0.5, y, z), (xr + P['boss_len'], y, z), P['boss_d'] / 2, 32)
    boolean(ob, bm, 'UNION')
    # holes
    bm = bmesh.new()
    for name, a, dia in rear_penetrators():
        y, z = (0.0, 0.0) if a is None else (P['gland_ring_r'] * sin(a), P['gland_ring_r'] * cos(a))
        bm_cyl(bm, (xb - 2, y, z), (xr + 1, y, z), dia / 2, 40)
    for a in rear_boss_angles():   # M3 heat-set insert holes in the bosses
        y, z = P['boss_r'] * sin(a), P['boss_r'] * cos(a)
        bm_cyl(bm, (xr + 1.5, y, z), (xr + P['boss_len'] + 1, y, z), 2.0, 24)
    boolean(ob, bm, 'DIFFERENCE')
    shade(ob)
    return ob


def rear_penetrators():
    """(name, angle from top toward port (+Y) in rad or None for centre, hole dia)."""
    t = P['gland_tap_d']
    step = 2 * pi / 7
    names = ['mast cable (GPS+strobe)', 'LoRa coax', 'thruster H-port', 'thruster V-port',
             'thruster V-stbd', 'thruster H-stbd', 'vent tube + ball valve']
    out = [(n, i * step, t) for i, n in enumerate(names)]
    out.append(('depth/temp sensor (M10)', None, P['depth_hole_d']))
    return out


def rear_boss_angles():
    step = 2 * pi / 7
    return [1.5 * step, 3.5 * step, 5.5 * step]


def build_orings():
    r_major = (D['ro_pipe'] + D['rg']) / 2
    r_minor = D['gap'] / 2
    obs = []
    xo_f = D['x_front'] - P['cap_sleeve_len']
    xo_r = D['x_rear'] + P['cap_sleeve_len']
    xs = [xo_f + P['groove1'], xo_f + P['groove2'], xo_r - P['groove1'], xo_r - P['groove2']]
    for i, x in enumerate(xs):
        prof = [(x + r_minor * cos(t), r_major + r_minor * 1.2 * sin(t))
                for t in [2 * pi * k / 16 for k in range(16)]]
        obs.append(mkobj(f'Oring_{i + 1}', rev_bm(prof, 128), 'Hull', MAT['rubber'],
                         dict(kind='pressure', mass_g=3.0, buy=True), smooth=80))
    return obs


def build_clamp(kind):
    """Split ring clamp. Returns (upper, lower) halves. The clamp is a pure
    extrusion along X so it prints flat on its side with no supports."""
    xc = P[f'clamp_{kind}_x']
    w = P['clamp_w']
    x0, x1 = xc - w / 2, xc + w / 2
    ro_p, rc = D['ro_pipe'], D['clamp_ro']
    eo, eh = P['ear_out'], P['ear_h']
    bm = rev_bm([(x0, ro_p - 1), (x0, rc), (x1, rc), (x1, ro_p - 1)], 128)
    # ears: pinch bolts + thruster mounts (mid and rear clamps). The front clamp
    # only needs small pinch-bolt lugs.
    ear_out = eo if kind != 'front' else ro_p + 17.0
    for s in (1, -1):
        bm_box(bm, x0, x1, *sorted((s * (ro_p - 2), s * ear_out)), -eh, eh)
    bm_box(bm, x0, x1, -14, 14, -(ro_p + 11), -(ro_p - 3))     # keel pad
    if kind == 'mid':
        bm_box(bm, x0, x1, -10, 10, ro_p - 3, ro_p + 11)        # mast pad
    ob = mkobj(f'Clamp_{kind}', bm, 'Frame', MAT['petg_dark'])
    # remesh the overlapping primitives into one solid
    bm2 = bmesh.new()
    bm_box(bm2, x0 - 1, x1 + 1, -1, 1, -1, 1)
    boolean(ob, bm2, 'UNION')
    bm2 = bmesh.new()
    bm_cyl(bm2, (x0 - 2, 0, 0), (x1 + 2, 0, 0), ro_p, 192)            # pipe
    for s in (1, -1):   # ear bolts M4
        for dx in (-4.5, 4.5):
            bolt_y = 56.0 if kind != 'front' else ro_p + 9.5
            bm_cyl(bm2, (xc + dx, s * bolt_y, -eh - 2), (xc + dx, s * bolt_y, eh + 2), 2.2, 24)
    for dy in (-7, 7):  # keel inserts M4 (from below)
        bm_cyl(bm2, (xc, dy, -(ro_p + 12)), (xc, dy, -(ro_p + 3)), 2.8, 24)
    if kind == 'mid':
        for dx in (-4.5, 4.5):  # mast inserts M3
            bm_cyl(bm2, (xc + dx, 0, ro_p + 12), (xc + dx, 0, ro_p + 4), 2.0, 24)
    if kind in ('front', 'rear'):
        # 4 x M3x20 screws pass THROUGH the clamp into heat-set inserts in the
        # nose ring / tail cone flange. Heads sit in counterbores on the side
        # that faces the middle of the hull, so they stay reachable.
        head_face = x0 if kind == 'front' else x1
        sgn = 1 if kind == 'front' else -1
        for k in range(4):
            a = pi / 4 + k * pi / 2
            y, z = 49.0 * sin(a), 49.0 * cos(a)
            bm_cyl(bm2, (x0 - 1, y, z), (x1 + 1, y, z), 1.7, 20)
            bm_cyl(bm2, (head_face - sgn * 1, y, z), (head_face + sgn * 3.5, y, z), 3.1, 20)
    boolean(ob, bm2, 'DIFFERENCE')
    halves = []
    for name, z0, z1 in (('upper', P['clamp_gap'] / 2, 200), ('lower', -200, -P['clamp_gap'] / 2)):
        h = bpy.data.objects.new(f'Clamp_{kind}_{name}', ob.data.copy())
        coll('Frame').objects.link(h)
        bm3 = bmesh.new()
        bm_box(bm3, x0 - 5, x1 + 5, -200, 200, z0, z1)
        boolean(h, bm3, 'INTERSECT')
        h['kind'] = 'wet'
        h['material'] = 'petg'
        h['fill'] = 1.0
        h['print'] = True
        h['print_dir'] = (1, 0, 0)
        h['note'] = 'Print on its side (ring axis vertical), 100% infill or 6 walls+40%.'
        shade(h)
        halves.append(h)
    bpy.data.objects.remove(ob)
    return halves


def build_mag_target():
    """White ring on top of the hull marking where to hold the magnet (reed
    switch inside, see build_internals)."""
    ro = D['ro_pipe']
    bm = bmesh.new()
    cut = bmesh.new()
    if BOARD['name'] == 'core':       # port side, level with the magnet sensor on the board edge
        xm, zm = P['pcb_x0'] + CORE_MAGNET_BX, P['pcb_z'] + 1.6
        bm_cyl(bm, (xm, ro - 1.0, zm), (xm, ro + 0.6, zm), 9.0, 48)
        bm_cyl(cut, (xm, ro - 2, zm), (xm, ro + 2, zm), 6.5, 48)
    else:
        bm_cyl(bm, (-111, 0, ro - 1.0), (-111, 0, ro + 0.6), 9.0, 48)
        bm_cyl(cut, (-111, 0, ro - 2), (-111, 0, ro + 2), 6.5, 48)
    ob = mkobj('MagnetTarget_decal', bm, 'Hull', MAT['decal_white'], dict(kind='pressure', mass_g=0.0))
    boolean(ob, cut, 'DIFFERENCE')
    cut = bmesh.new()
    bm_cyl(cut, (D['x_rear'], 0, 0), (D['x_front'], 0, 0), ro - 0.2, 192)
    boolean(ob, cut, 'DIFFERENCE')
    return ob


def build_keel():
    bm = bmesh.new()
    z0 = -(D['ro_pipe'] + 11) - P['keel_t']
    bm_box(bm, P['keel_x0'], P['keel_x1'], -P['keel_w'] / 2, P['keel_w'] / 2, z0, z0 + P['keel_t'])
    ob = mkobj('Keel_bar_alu_25x3', bm, 'Frame', MAT['alu'],
               dict(kind='wet', material='alu', fill=1.0, buy=True))
    bm = bmesh.new()
    xs = [P[f'clamp_{k}_x'] for k in ('front', 'mid', 'rear')]
    for xc in xs:
        for dy in (-7, 7):
            bm_cyl(bm, (xc, dy, z0 - 1), (xc, dy, z0 + P['keel_t'] + 1), 2.2, 20)
    x = P['keel_x0'] + 10
    while x <= P['keel_x1'] - 10 + 1e-6:     # pod holes every 20 mm on the centre line
        bm_cyl(bm, (x, 0, z0 - 1), (x, 0, z0 + P['keel_t'] + 1), 2.2, 16)
        x += 20.0
    boolean(ob, bm, 'DIFFERENCE')
    shade(ob, None)
    return ob, z0


def build_pod(name, xc, z_top):
    L, W, H, t = P['pod_l'], P['pod_w'], P['pod_h'], P['pod_wall']
    bm = bmesh.new()
    bm_box(bm, xc - L / 2, xc + L / 2, -W / 2, W / 2, z_top - H, z_top)
    ob = mkobj(name, bm, 'Frame', MAT['petg_yellow'],
               dict(kind='wet', material='petg', fill=1.0, print=True, print_dir=(0, 0, 1),
                    note='Open side up. Fill with lead shot, then bolt open side to the keel bar.'))
    bm = bmesh.new()
    bm_box(bm, xc - L / 2 + t + 12, xc + L / 2 - t - 12, -W / 2 + t, W / 2 - t, z_top - H + 3, z_top + 1)
    boolean(ob, bm, 'DIFFERENCE')
    bm = bmesh.new()  # end blocks with M4 inserts at +-50 mm (on the 20 mm keel grid)
    for dx in (-50, 50):
        bm_cyl(bm, (xc + dx, 0, z_top - 12), (xc + dx, 0, z_top + 1), 2.8, 24)
    boolean(ob, bm, 'DIFFERENCE')
    # bevel-ish look
    shade(ob, None)
    return ob


def pod_cavity_volume():
    L, W, H, t = P['pod_l'], P['pod_w'], P['pod_h'], P['pod_wall']
    return (L - 2 * t - 24) * (W - 2 * t) * (H - 3) / 1000.0   # cm3


# ---------------------------------------------------------------- thrusters
def duct_bm():
    """Duct + struts + motor mount in LOCAL coordinates: axis +X, x=0 is the
    motor-mount end, x=duct_len the prop end."""
    ri, ro, L = D['duct_ri'], D['duct_ro'], P['duct_len']
    prof = [(0, ri + 1.2), (0, ro - 1.0), (1.0, ro), (L - 1.0, ro), (L, ro - 1.0),
            (L, ri + 0.4), (L - 2.0, ri), (6.0, ri), (0.8, ri + 1.2)]
    bm = rev_bm(prof, 96)
    # motor mount disk
    rev = rev_bm([(0, 4.6), (0, 15.5), (4.0, 15.5), (4.0, 4.6)], 64)
    _merge(bm, rev)
    for k in range(3):   # struts
        a = pi / 2 + k * 2 * pi / 3
        s = bmesh.new()
        bm_box(s, 0, 6.0, -1.6, 1.6, 14.5, ri + 1.5)
        bm_transform(s, Matrix.Rotation(a, 4, 'X'))
        _merge(bm, s)
    return bm


def _merge(bm, other):
    me = bpy.data.meshes.new('_tmp')
    other.to_mesh(me)
    other.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


def motor_holes_bm():
    bm = bmesh.new()
    bm_box(bm, -1, 5, -2.0, 2.0, 4.0, 13.0)      # slot for the three motor wires
    for r, angs in ((8.0, (0, pi)), (9.5, (pi / 2, 3 * pi / 2))):   # 16 mm and 19 mm patterns
        for a in angs:
            bm_cyl(bm, (-1, r * cos(a), r * sin(a)), (5, r * cos(a), r * sin(a)), 1.65, 16)
    return bm


def prop_bm(handed=1):
    """3-blade propeller, LOCAL coords: axis +X, hub from x=0 to hub_len."""
    R = P['prop_d'] / 2
    rh = P['prop_hub_d'] / 2
    hub_len = P['prop_hub_len']
    bm = rev_bm([(0, P['prop_bore_d'] / 2), (0, rh - 0.6), (0.6, rh), (hub_len - 0.6, rh),
                 (hub_len, rh - 0.6), (hub_len, P['prop_bore_d'] / 2)], 64)
    n_st, n_u = 14, 14
    xm = hub_len / 2
    for b in range(P['prop_blades']):
        phi0 = b * 2 * pi / P['prop_blades']
        stations = []
        for i in range(n_st):
            s = i / (n_st - 1)
            r = (rh - 0.7) + s * (R - (rh - 0.7))
            c = 9.0 + 10.0 * s - 11.0 * s * s
            if i == n_st - 1:
                c *= 0.55
            t = 2.6 - 1.4 * s
            beta = atan(P['prop_pitch'] / (2 * pi * r))
            sec = []
            # upper surface LE->TE (n_u points incl. both ends), lower surface
            # TE->LE without repeating the two end points: 2*n_u-2 points
            uv = [(-c / 2 + c * k / (n_u - 1), 1) for k in range(n_u)]
            uv += [(c / 2 - c * k / (n_u - 1), -1) for k in range(1, n_u - 1)]
            for u, sign in uv:
                e = max(0.0, 1 - (2 * u / c) ** 2)
                v = sign * (t / 2) * e ** 0.55
                s_arc = u * cos(beta) - v * sin(beta)
                a = u * sin(beta) + v * cos(beta)
                phi = phi0 + handed * s_arc / r
                sec.append((xm + a, r * cos(phi), r * sin(phi)))
            stations.append(sec)
        vs = [[bm.verts.new(p) for p in sec] for sec in stations]
        m = len(vs[0])
        for i in range(n_st - 1):
            for k in range(m):
                k2 = (k + 1) % m
                bm.faces.new((vs[i][k], vs[i][k2], vs[i + 1][k2], vs[i + 1][k]))
        bm.faces.new(vs[0][::-1])
        bm.faces.new(vs[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def motor_parts_bm():
    """A2212 style outrunner, LOCAL coords (base at x=4 on the mount disk)."""
    stator = rev_bm([(4.0, 0), (4.0, 13.5), (6.5, 13.5), (6.5, 0)], 48)
    bell = rev_bm([(6.5, 0), (6.5, P['motor_bell_d'] / 2), (4.0 + P['motor_len'] - 1, P['motor_bell_d'] / 2),
                   (4.0 + P['motor_len'], P['motor_bell_d'] / 2 - 1), (4.0 + P['motor_len'], 0)], 48)
    shaft = rev_bm([(4.0 + P['motor_len'], 0), (4.0 + P['motor_len'], 4.2), (32.0, 4.2), (32.0, 2.6),
                    (43.0, 2.6), (43.5, 2.0), (43.5, 0)], 32)
    return stator, bell, shaft


def place_matrix(kind, side):
    """LOCAL thruster frame -> vehicle frame."""
    y = side * P['thruster_y']
    if kind == 'H':
        xc = P['clamp_rear_x']
        return Matrix.Translation((xc + 20, y, 0)) @ Matrix.Rotation(pi, 4, 'Z')
    xc = P['clamp_mid_x']
    return Matrix.Translation((xc, y, 20)) @ Matrix.Rotation(pi / 2, 4, 'Y')


def build_thruster(kind, side, handed):
    tag = f"{kind}_{'port' if side > 0 else 'stbd'}"
    M = place_matrix(kind, side)
    duct = mkobj(f'Duct_{tag}', bm_transform(duct_bm(), M), 'Thrusters', MAT['petg_dark'],
                 dict(kind='wet', material='petg', fill=1.0, print=True,
                      print_dir=(-1, 0, 0) if kind == 'H' else (0, 0, -1),
                      note='Motor-mount end on the bed, 100% infill.'))
    # mounting tab that sits on top of the clamp ear (+ web down to the bed when printed)
    eh = P['ear_h']
    xc = P['clamp_rear_x'] if kind == 'H' else P['clamp_mid_x']
    w = P['clamp_w']
    bm = bmesh.new()
    ylo, yhi = 47.0, 66.4
    if kind == 'V':
        bm_box(bm, xc - w / 2, xc + w / 2, *sorted((side * ylo, side * yhi)), eh, 20.0)
    else:
        bm_box(bm, xc - w / 2, xc + 20.0, *sorted((side * ylo, side * yhi)), eh, eh + 5.0)
    boolean(duct, bm, 'UNION')
    bm = bm_transform(motor_holes_bm(), M)   # motor screws (16 and 19 mm patterns)
    for dx in (-4.5, 4.5):                   # M4 bolts through tab + clamp ear
        bm_cyl(bm, (xc + dx, side * 56, eh - 2), (xc + dx, side * 56, 22), 2.2, 20)
    boolean(duct, bm, 'DIFFERENCE')
    shade(duct)
    stator, bell, shaft = motor_parts_bm()
    mot = mkobj(f'Motor_{tag}', bm_transform(bell, M), 'Thrusters', MAT['motor_bell'],
                dict(kind='wet', mass_g=50.0, disp_cm3=8.5, buy=True))
    st = mkobj(f'MotorBase_{tag}', bm_transform(stator, M), 'Thrusters', MAT['nylon_black'],
               dict(kind='wet', mass_g=0.0, disp_cm3=0.0))
    sh = mkobj(f'PropAdapter_{tag}', bm_transform(shaft, M), 'Thrusters', MAT['steel'],
               dict(kind='wet', mass_g=0.0, disp_cm3=0.0))
    pm = M @ Matrix.Translation((31.5, 0, 0))
    prop = mkobj(f'Prop_{tag}_{"CW" if handed > 0 else "CCW"}', bm_transform(prop_bm(handed), pm),
                 'Thrusters', MAT['petg_grey'],
                 dict(kind='wet', material='petg', fill=1.0, print=True,
                      print_dir=(-1, 0, 0) if kind == 'H' else (0, 0, -1),
                      note='Print hub-down with tree supports at 0.12 mm, or in resin.'))
    inner = bmesh.new()      # fuse blades + hub into one watertight solid
    bm_box(inner, 2.0, 6.0, 3.6, 4.6, -0.4, 0.4)
    bm_transform(inner, pm)
    boolean(prop, inner, 'UNION')
    shade(prop, 50)
    return [duct, mot, st, sh, prop]


# ---------------------------------------------------------------- mast
def naca_section(chord, thick, n=28):
    t = thick / chord
    up, lo = [], []
    for i in range(n + 1):
        b = pi * i / n
        x = (1 - cos(b)) / 2
        yt = 5 * t * (0.2969 * sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
        up.append((x * chord, yt * chord))
        lo.append((x * chord, -yt * chord))
    pts = up + lo[::-1][1:-1]
    return pts


def build_mast():
    xc = P['clamp_mid_x']
    z_base = D['ro_pipe'] + 11
    c, th = P['mast_chord'], P['mast_thick']
    sec = [(xc + c / 2 - x, y) for x, y in naca_section(c, th)]   # leading edge forward
    bm = bmesh.new()
    bm_box(bm, xc - c / 2 - 2, xc + c / 2 + 2, -9, 9, z_base, z_base + 4)       # base plate
    bm_prism(bm, sec, z_base + 3.5, z_base + 4 + P['mast_h'])
    zt = z_base + 4 + P['mast_h']
    puck = rev_bm([(0, 0), (0, P['puck_d'] / 2 - 1.5), (1.5, P['puck_d'] / 2), (P['puck_h'] - 2, P['puck_d'] / 2),
                   (P['puck_h'], P['puck_d'] / 2 - 2), (P['puck_h'], 0)], 64)
    bm_transform(puck, Matrix.Translation((xc, 0, zt)) @ Matrix.Rotation(-pi / 2, 4, 'Y'))
    _merge(bm, puck)
    cone = bmesh.new()   # 45 deg chamfer under the puck so it prints without support
    bm_cyl(cone, (xc, 0, zt - (P['puck_d'] / 2 - th / 2) + 0.5), (xc, 0, zt + 0.5), th / 2, 48, r2=P['puck_d'] / 2 - 0.5)
    _merge(bm, cone)
    ob = mkobj('Mast', bm, 'Frame', MAT['petg_white'],
               dict(kind='wet', print=True, print_dir=(0, 0, 1),
                    note='Print in natural/clear PETG with 2 mm walls and NO infill (hollow), '
                         'then pot GPS, antenna and strobe LED inside with epoxy.'))
    bm = bmesh.new()
    bm_box(bm, xc - 5, xc + 5, -2, 2, z_base + 1, z_base + 3)
    boolean(ob, bm, 'UNION')
    bm = bmesh.new()
    for dx in (-4.5, 4.5):
        bm_cyl(bm, (xc + dx, 0, z_base - 1), (xc + dx, 0, z_base + 5), 1.7, 16)
    bm_cyl(bm, (xc - 10, 0, z_base - 1), (xc - 10, 0, z_base + 10), 4.0, 24)   # cable entry
    boolean(ob, bm, 'DIFFERENCE')
    shade(ob)
    V, _ = mesh_volume_centroid(ob)
    ob['mass_g'] = V * 1.20 + 15.0      # PETG shell + epoxy core + GPS/antenna/LED
    ob['disp_cm3'] = V
    ob['material'] = 'petg'
    return ob, zt + P['puck_h']


# ---------------------------------------------------------------- fairings
def build_nose_ring():
    xcl = P['clamp_front_x'] + P['clamp_w'] / 2          # clamp front face
    xf = D['x_front_face']
    ro = D['ro_cap'] + 2.7
    ri = D['ro_cap'] + 0.4
    lip = 3.0
    fl = 5.0                                              # flange thickness (M3 inserts)
    prof = [(xcl, 46.0), (xcl, ro), (xf - 14.0 + lip, ro), (xf + lip, D['rw'] - 0.2),
            (xf + lip, D['ra'] + 0.5), (xf + 0.5, D['ra'] + 0.5), (xf + 0.5, D['rw'] + 0.8),
            (xf, D['rw'] + 0.8), (xf, ri), (xcl + fl, ri), (xcl + fl, 46.0)]
    ob = mkobj('NoseRing', rev_bm(prof, 160), 'Fairings', MAT['petg_dark'],
               dict(kind='wet', material='petg', fill=1.0, print=True, print_dir=(-1, 0, 0),
                    note='Lip down. Retains the window and the front cap. 4 x M3 heat-set inserts '
                         'in the flange; screws come through the front clamp from behind.'))
    bm = bmesh.new()
    for k in range(4):
        a = pi / 4 + k * pi / 2
        y, z = 49.0 * sin(a), 49.0 * cos(a)
        bm_cyl(bm, (xcl - 1, y, z), (xcl + fl + 0.5, y, z), 2.0, 16)
    boolean(ob, bm, 'DIFFERENCE')
    shade(ob)
    return ob


def build_tail_cone():
    xcl = P['clamp_rear_x'] - P['clamp_w'] / 2           # clamp rear face
    xb = D['x_rear_face']
    ro = D['ro_cap'] + 3.2
    ri = D['ro_cap'] + 0.4
    ch = P['rear_chamfer']
    x_tip = xb - 62.0
    prof = [(xcl, 46.0), (xcl, ro)]
    n = 14
    x_start = xb + 2
    for i in range(1, n + 1):          # ogive outer surface
        s = i / n
        x = x_start + (x_tip - x_start) * s
        r = 9.0 + (ro - 9.0) * sqrt(max(0.0, 1 - s ** 1.8))
        prof.append((x, r))
    prof += [(x_tip, 7.0)]
    for i in range(n, 0, -1):          # inner surface (2.4 mm wall)
        s = i / n
        x = x_start + (x_tip - x_start) * s
        r = 9.0 + (ro - 9.0) * sqrt(max(0.0, 1 - s ** 1.8)) - 1.8
        if x > xb - ch - 2:
            continue
        prof.append((x + 1.5, max(r, 6.5)))
    fl = 5.0
    prof += [(xb - 0.4, D['ro_cap'] - ch - 1.0), (xb - 0.4 + 0.0, D['ro_cap'] - ch + 0.4),
             (xb + ch, ri), (xcl - fl, ri), (xcl - fl, 46.0)]
    ob = mkobj('TailCone', rev_bm(prof, 160), 'Fairings', MAT['petg_dark'],
               dict(kind='wet', material='petg', fill=1.0, print=True, print_dir=(-1, 0, 0),
                    note='Flange down. Seats on the rear-cap chamfer and holds the rear cap on. '
                         '4 x M3 heat-set inserts in the flange.'))
    bm = bmesh.new()
    for k in range(4):     # 4 open-ended cable slots (top, port, bottom, stbd)
        a = k * pi / 2
        s = bmesh.new()
        bm_box(s, xb - 22, xcl + 2, -6.5, 6.5, 30, 70)
        bm_transform(s, Matrix.Rotation(-a, 4, 'X'))
        _merge(bm, s)
    for k in range(4):     # heat-set insert holes
        a = pi / 4 + k * pi / 2
        y, z = 49.0 * sin(a), 49.0 * cos(a)
        bm_cyl(bm, (xcl + 1, y, z), (xcl - fl - 0.5, y, z), 2.0, 16)
    boolean(ob, bm, 'DIFFERENCE')
    shade(ob)
    return ob


# ---------------------------------------------------------------- penetrators
def build_penetrators():
    xb = D['x_rear_face']
    obs = []
    for name, a, dia in rear_penetrators():
        y, z = (0.0, 0.0) if a is None else (P['gland_ring_r'] * sin(a), P['gland_ring_r'] * cos(a))
        bm = bmesh.new()
        if a is None:   # depth sensor (Bar30-style potted bolt)
            bm_cyl(bm, (xb - 9, y, z), (xb + 0.01, y, z), 9.5, 6)
            bm_cyl(bm, (xb - 12, y, z), (xb - 9, y, z), 5.5, 24)
            ob = mkobj('DepthSensor_MS5837', bm, 'Hull', MAT['steel'],
                       dict(kind='pressure', mass_g=25.0, buy=True))
        else:
            bm_cyl(bm, (xb - 6, y, z), (xb + 0.01, y, z), 8.6, 6)
            bm_cyl(bm, (xb - 14, y, z), (xb - 6, y, z), 7.2, 24, r2=6.0)
            ob = mkobj(f'Gland_M12_{name.split()[0]}_{len(obs)}', bm, 'Hull', MAT['nylon_black'],
                       dict(kind='pressure', mass_g=5.0, buy=True))
        obs.append(ob)
    return obs


# ---------------------------------------------------------------- internals
def build_internals(pcb_layout=None):
    obs = []
    xr = D['x_rear']
    ri = D['ri_pipe']
    # sled rear plate + standoffs
    x_plate = xr + P['boss_len'] + 20.0
    bm = rev_bm([(x_plate, 0), (x_plate, ri - 1.5), (x_plate + 4, ri - 1.5), (x_plate + 4, 0)], 96)
    ob = mkobj('Sled_rear_plate', bm, 'Internals', MAT['petg_grey'],
               dict(kind='dry', material='petg', fill=0.5, print=True, print_dir=(1, 0, 0),
                    note='Any infill. Clamp the two 6 mm rods.'))
    bm = bmesh.new()
    bm_box(bm, x_plate - 1, x_plate + 5, -18, 18, 6, 30)       # cable pass-through window
    bm_box(bm, x_plate - 1, x_plate + 5, -14, 14, -30, -12)
    for a in rear_boss_angles():
        y, z = P['boss_r'] * sin(a), P['boss_r'] * cos(a)
        bm_cyl(bm, (x_plate - 1, y, z), (x_plate + 5, y, z), 1.7, 16)
    for s in (1, -1):
        bm_cyl(bm, (x_plate - 1, s * P['rod_y'], P['rod_z']), (x_plate + 5, s * P['rod_y'], P['rod_z']),
               P['rod_d'] / 2 + 0.15, 24)
    boolean(ob, bm, 'DIFFERENCE')
    obs.append(ob)
    bm = bmesh.new()
    for a in rear_boss_angles():
        y, z = P['boss_r'] * sin(a), P['boss_r'] * cos(a)
        bm_cyl(bm, (xr + P['boss_len'], y, z), (x_plate, y, z), 2.6, 6)
    obs.append(mkobj('Standoffs_M3x20', bm, 'Internals', MAT['brass'], dict(kind='dry', mass_g=6.0, buy=True)))
    # rods
    x_rod1 = D['x_front'] - P['cam_d'] - P['cam_gap'] - 6.0
    bm = bmesh.new()
    for s in (1, -1):
        bm_cyl(bm, (x_plate, s * P['rod_y'], P['rod_z']), (x_rod1, s * P['rod_y'], P['rod_z']), P['rod_d'] / 2, 24)
    obs.append(mkobj('Sled_rods_alu_6mm', bm, 'Internals', MAT['alu'], dict(kind='dry', mass_g=26.0, buy=True)))
    # ESC sits at the rear (short motor leads to the glands); batteries go
    # forward under the PCB to bring the centre of gravity forward.
    ex0 = x_plate + 5
    ex1 = ex0 + 42.0
    # battery tray + batteries
    bx0 = ex1 + 2
    bx1 = bx0 + P['batt_count'] * (P['batt_l'] + 2) + 4
    bz0 = -26.0
    bm = bmesh.new()
    bm_box(bm, bx0, bx1, -27.5, 27.5, bz0 - 2, bz0)
    for s in (1, -1):
        bm_box(bm, bx0, bx1, *sorted((s * 27.5, s * (P['rod_y'] - 3.5))), bz0 - 2, P['rod_z'] - 3.0)
        bm_cyl(bm, (bx0, s * P['rod_y'], P['rod_z']), (bx1, s * P['rod_y'], P['rod_z']), 4.6, 24)
    ob = mkobj('Sled_battery_tray', bm, 'Internals', MAT['petg_grey'],
               dict(kind='dry', material='petg', fill=0.5, print=True, print_dir=(0, 0, 1),
                    note='Strap batteries down with Velcro.'))
    bm = bmesh.new()
    for s in (1, -1):
        bm_cyl(bm, (bx0 - 1, s * P['rod_y'], P['rod_z']), (bx1 + 1, s * P['rod_y'], P['rod_z']), P['rod_d'] / 2 + 0.15, 24)
    boolean(ob, bm, 'DIFFERENCE')
    clip_to_bore(ob)
    obs.append(ob)
    for i in range(P['batt_count']):
        x0 = bx0 + 2 + i * (P['batt_l'] + 2)
        bm = bmesh.new()
        for k in range(3):
            y = -P['batt_w'] / 2 + 9.3 + k * 18.7
            bm_cyl(bm, (x0, y, bz0 + 9.5), (x0 + P['batt_l'], y, bz0 + 9.5), 9.3, 32)
        obs.append(mkobj(f'Battery_3S1P_{i + 1}', bm, 'Internals', MAT['battery_blue'],
                         dict(kind='dry', mass_g=150.0, buy=True)))
    # ESC 4-in-1 tray + board
    bm = bmesh.new()
    bm_box(bm, ex0, ex1, -27.5, 27.5, bz0 - 2, bz0)
    for s in (1, -1):
        bm_box(bm, ex0, ex1, *sorted((s * 27.5, s * (P['rod_y'] - 3.5))), bz0 - 2, P['rod_z'] - 3.0)
        bm_cyl(bm, (ex0, s * P['rod_y'], P['rod_z']), (ex1, s * P['rod_y'], P['rod_z']), 4.6, 24)
    ob = mkobj('Sled_esc_tray', bm, 'Internals', MAT['petg_grey'],
               dict(kind='dry', material='petg', fill=0.5, print=True, print_dir=(0, 0, 1),
                    note='30.5 mm M3 pattern for the 4-in-1 ESC.'))
    bm = bmesh.new()
    for s in (1, -1):
        bm_cyl(bm, (ex0 - 1, s * P['rod_y'], P['rod_z']), (ex1 + 1, s * P['rod_y'], P['rod_z']), P['rod_d'] / 2 + 0.15, 24)
    for dx in (-15.25, 15.25):
        for dy in (-15.25, 15.25):
            bm_cyl(bm, ((ex0 + ex1) / 2 + dx, dy, bz0 - 3), ((ex0 + ex1) / 2 + dx, dy, bz0 + 1), 1.4, 12)
    boolean(ob, bm, 'DIFFERENCE')
    clip_to_bore(ob)
    obs.append(ob)
    exm = (ex0 + ex1) / 2
    bm = bmesh.new()
    bm_box(bm, exm - 18, exm + 18, -18, 18, bz0 + 3, bz0 + 4.6)
    for dx in (-10, 10):
        bm_cyl(bm, (exm + dx, -13, bz0 + 4.6), (exm + dx, -13, bz0 + 10), 3.2, 16)
    obs.append(mkobj('ESC_4in1', bm, 'Internals', MAT['pcb_black'], dict(kind='dry', mass_g=25.0, buy=True)))
    # PCB + modules
    obs += build_pcb_model(pcb_layout)
    # IMU bracket + board (the core board has the compass on it)
    if BOARD['name'] == 'core':
        obs += build_camera(x_rod1) + build_leak_probes(xr, ri)
        return obs
    ix = 118.0          # IMU well away from the ESC, battery and DevKit
    bm = bmesh.new()
    bm_box(bm, ix - 15, ix + 15, -P['rod_y'], P['rod_y'], P['rod_z'] - 1.5, P['rod_z'] + 1.5)
    for s in (1, -1):
        bm_cyl(bm, (ix - 15, s * P['rod_y'], P['rod_z']), (ix + 15, s * P['rod_y'], P['rod_z']), 4.6, 24)
    bm_box(bm, ix - 12, ix + 12, -10, 10, P['rod_z'], P['rod_z'] + 9)
    ob = mkobj('Sled_imu_bracket', bm, 'Internals', MAT['petg_grey'],
               dict(kind='dry', material='petg', fill=0.5, print=True, print_dir=(0, 0, 1),
                    note='Keep the IMU flat and square to the hull axis.'))
    bm = bmesh.new()
    for s in (1, -1):
        bm_cyl(bm, (ix - 16, s * P['rod_y'], P['rod_z']), (ix + 16, s * P['rod_y'], P['rod_z']), P['rod_d'] / 2 + 0.15, 24)
    boolean(ob, bm, 'DIFFERENCE')
    obs.append(ob)
    bm = bmesh.new()
    bm_box(bm, ix - 12.8, ix + 12.8, -8.9, 8.9, P['rod_z'] + 9, P['rod_z'] + 10.6)
    bm_box(bm, ix - 2.6, ix + 2.6, -2.6, 2.6, P['rod_z'] + 10.6, P['rod_z'] + 11.6)
    obs.append(mkobj('IMU_BNO085', bm, 'Internals', MAT['pcb_black'], dict(kind='dry', mass_g=4.0, buy=True)))
    # camera cradle + camera
    obs += build_camera(x_rod1)
    obs += build_leak_probes(xr, ri)
    # reed switch on the top inner wall
    bm = bmesh.new()
    bm_cyl(bm, (-118, 0, ri - 2.0), (-104, 0, ri - 2.0), 1.1, 12)
    obs.append(mkobj('ReedSwitch', bm, 'Internals', MAT['acrylic'], dict(kind='dry', mass_g=1.0, buy=True)))
    return obs


def build_leak_probes(xr, ri):
    obs = []
    for name, x in (('LeakProbe_front', D['x_front'] - P['cam_d'] - 20.0), ('LeakProbe_rear', xr + 12.0)):
        bm = bmesh.new()
        bm_box(bm, x - 7, x + 7, -5, 5, -ri + 0.6, -ri + 2.2)
        obs.append(mkobj(name, bm, 'Internals', MAT['pcb_green'], dict(kind='dry', mass_g=2.0, buy=True)))
    return obs


def clip_to_bore(ob, margin=0.8):
    """Trim a sled part so it can never touch the inside of the pipe."""
    bm = bmesh.new()
    bm_cyl(bm, (D['x_rear'] - 5, 0, 0), (D['x_front'] + 5, 0, 0), D['ri_pipe'] - margin, 128)
    boolean(ob, bm, 'INTERSECT')
    shade(ob)
    return ob


# PCB mounting: board holes (bx, by) from pcb/design.py; two brackets sit on the
# battery-tray rod sleeves, one small post clamps the rods in front of the tray.
PCB_BRACKETS = [((24.0, 4.0), (24.0, 56.0)), ((71.5, 4.0), (71.5, 56.5))]
PCB_FRONT_POST = (96.0, 4.0)
PCB_COLORS = {'yellow': (0.93, 0.78, 0.10), 'fuse_blue': (0.25, 0.55, 0.95), 'black': (0.03, 0.03, 0.03),
              'tan': (0.62, 0.50, 0.33), 'led_green': (0.2, 0.8, 0.3), 'cap_blue': (0.08, 0.12, 0.35),
              'beige': (0.90, 0.86, 0.76), 'esp_silver': (0.72, 0.72, 0.74)}


def board_to_vehicle(bx, by):
    return P['pcb_x0'] + bx, P['pcb_w'] / 2 - by


def pcb_texture_material():
    img_path = os.path.join(script_dir(), '..', pcb_dir(), 'output', 'board_top.png')
    if not os.path.exists(img_path):
        return MAT['pcb_green']
    m = bpy.data.materials.new('pcb_texture')
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(os.path.abspath(img_path))
    tex.interpolation = 'Cubic'
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.32
    if 'Coat Weight' in bsdf.inputs:
        bsdf.inputs['Coat Weight'].default_value = 0.4
    return m


def build_pcb_model(layout):
    obs = []
    z = P['pcb_z']
    L, W, c = P['pcb_l'], P['pcb_w'], 2.0
    outline = [(c, 0), (L - c, 0), (L, c), (L, W - c), (L - c, W), (c, W), (0, W - c), (0, c)]
    bm = bmesh.new()
    bm_prism(bm, [board_to_vehicle(bx, by) for bx, by in outline], z, z + 1.6)
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for lp in f.loops:
            vx, vy = lp.vert.co.x, lp.vert.co.y
            bx, by = vx - P['pcb_x0'], W / 2 - vy
            lp[uv].uv = (bx / L, 1.0 - by / W)
    ob = mkobj('PCB_mainboard', bm, 'Internals', pcb_texture_material(),
               dict(kind='dry', mass_g=32.0, buy=True), smooth=None)
    obs.append(ob)
    # brackets resting on the battery-tray rod sleeves (top of sleeves = rod_z + 4.6)
    zs = P['rod_z'] + 4.6
    for i, posts in enumerate(PCB_BRACKETS):
        x = P['pcb_x0'] + posts[0][0]
        bm = bmesh.new()
        bm_box(bm, x - 4, x + 4, -P['rod_y'] - 4, P['rod_y'] + 4, zs, zs + 2.8)
        for bx, by in posts:
            _, y = board_to_vehicle(bx, by)
            bm_cyl(bm, (x, y, zs + 1.0), (x, y, z), 3.2, 20)
        b = mkobj(f'Sled_pcb_bracket_{i + 1}', bm, 'Internals', MAT['petg_grey'],
                  dict(kind='dry', material='petg', fill=0.5, print=True, print_dir=(0, 0, 1),
                       note='Rests across the two battery-tray rod sleeves (zip-tie or glue it); '
                            'M3 screws into the PCB mounting holes.'))
        cut = bmesh.new()
        for bx, by in posts:
            _, y = board_to_vehicle(bx, by)
            bm_cyl(cut, (x, y, z - 7), (x, y, z + 0.5), 1.25, 12)
        boolean(b, cut, 'DIFFERENCE')
        clip_to_bore(b)
        obs.append(b)
    x, y = board_to_vehicle(*PCB_FRONT_POST)
    bm = bmesh.new()
    bm_box(bm, x - 4, x + 4, -P['rod_y'], P['rod_y'], P['rod_z'] + 3.0, P['rod_z'] + 6.0)
    for s in (1, -1):
        bm_cyl(bm, (x - 4, s * P['rod_y'], P['rod_z']), (x + 4, s * P['rod_y'], P['rod_z']), 4.6, 24)
    bm_cyl(bm, (x, y, P['rod_z'] + 3.0), (x, y, z), 3.2, 20)
    b = mkobj('Sled_pcb_front_post', bm, 'Internals', MAT['petg_grey'],
              dict(kind='dry', material='petg', fill=0.5, print=True, print_dir=(0, 0, 1),
                   note='Clamps onto the rods in front of the battery tray; supports the PCB at hole H5.'))
    cut = bmesh.new()
    for s in (1, -1):
        bm_cyl(cut, (x - 5, s * P['rod_y'], P['rod_z']), (x + 5, s * P['rod_y'], P['rod_z']), P['rod_d'] / 2 + 0.15, 24)
    bm_cyl(cut, (x, y, z - 6), (x, y, z + 0.5), 1.25, 12)
    boolean(b, cut, 'DIFFERENCE')
    clip_to_bore(b)
    obs.append(b)
    obs += build_pcb_parts(layout)
    return obs


def build_pcb_parts(layout):
    """3D bodies of the components, from pcb/placement.json (written by the KiCad generator)."""
    obs = []
    zt = P['pcb_z'] + 1.6
    parts = (layout or {}).get('parts', [])
    by_col = {}
    for rec in parts:
        if rec['kind'] != 'part':
            continue
        x, y = board_to_vehicle(rec['x'], rec['y'])
        bm = by_col.setdefault(rec['color'], bmesh.new())
        if rec['shape'] == 'cyl':
            bm_cyl(bm, (x, y, zt), (x, y, zt + rec['h']), rec['w'] / 2, 32)
        else:
            bm_box(bm, x - rec['w'] / 2, x + rec['w'] / 2, y - rec['d'] / 2, y + rec['d'] / 2, zt, zt + rec['h'])
    for col, bm in by_col.items():
        m = material(f'pcbpart_{col}', PCB_COLORS.get(col, (0.1, 0.1, 0.1)), rough=0.45)
        obs.append(mkobj(f'PCB_parts_{col}', bm, 'Internals', m, dict(kind='dry', mass_g=0.0), smooth=None))
    sock = MAT['nylon_black']
    for rec in parts:
        if rec['kind'] == 'devkit':
            obs += build_devkit(rec['x'], rec['y'], zt, sock)
        elif rec['kind'] == 'e220':
            obs += build_e220(rec['x'], rec['y'], zt, sock)
    if parts:
        obs[0]['mass_g'] = 30.0        # all small parts together
    return obs


def build_devkit(bx1, by1, zt, sock):
    """ESP32-S3-DevKitC-1 on two 22-pin sockets; (bx1, by1) = J1 pin 1."""
    obs = []
    hs = 8.5
    bm = bmesh.new()
    for dy in (0.0, 22.86):
        xa, ya = board_to_vehicle(bx1 + 1.27, by1 + dy - 1.27)
        xb, yb = board_to_vehicle(bx1 - 53.34 - 1.27, by1 + dy + 1.27)
        bm_box(bm, xb, xa, yb, ya, zt, zt + hs)
    obs.append(mkobj('DevKit_sockets', bm, 'Internals', sock, dict(kind='dry', mass_g=6.0, buy=True), smooth=None))
    z0 = zt + hs
    xa, ya = board_to_vehicle(bx1 + 7.667, by1 - 1.333)
    xb, yb = board_to_vehicle(bx1 - 53.34 - 9.05 + 1.5, by1 + 22.86 + 1.333)
    bm = bmesh.new()
    bm_box(bm, xb, xa, yb, ya, z0, z0 + 1.6)
    obs.append(mkobj('DevKit_board', bm, 'Internals', MAT['pcb_black'], dict(kind='dry', mass_g=10.0, buy=True), smooth=None))
    yc = (ya + yb) / 2
    bm = bmesh.new()   # WROOM-1 shield can (antenna part stays bare PCB)
    bm_box(bm, xa - 25.5 + 0.5, xa - 6.8, yc - 9.0, yc + 9.0, z0 + 1.6, z0 + 1.6 + 3.1)
    for dy in (-6.0, 6.0):  # two USB-C receptacles at the other end
        bm_box(bm, xb - 1.5, xb + 7.3, yc + dy - 4.5, yc + dy + 4.5, z0 + 1.6, z0 + 1.6 + 3.2)
    obs.append(mkobj('DevKit_module_shield', bm, 'Internals', MAT['steel'], dict(kind='dry', mass_g=0.0), smooth=None))
    return obs


def build_e220(bx1, by1, zt, sock):
    """Ebyte E220-900T22D on a 7-pin socket; (bx1, by1) = pin 1, module extends +bx."""
    obs = []
    hs = 8.5
    xa, ya = board_to_vehicle(bx1 - 1.27, by1 - 1.27)
    xb, yb = board_to_vehicle(bx1 + 1.27, by1 + 6 * 2.54 + 1.27)
    bm = bmesh.new()
    bm_box(bm, xa, xb, yb, ya, zt, zt + hs)
    obs.append(mkobj('E220_socket', bm, 'Internals', sock, dict(kind='dry', mass_g=1.0), smooth=None))
    z0 = zt + hs
    x0, y0 = board_to_vehicle(bx1 - 1.3, by1 - 2.88)
    x1, y1 = board_to_vehicle(bx1 + 34.7, by1 + 18.12)
    bm = bmesh.new()
    bm_box(bm, x0, x1, y1, y0, z0, z0 + 1.0)
    obs.append(mkobj('E220_board', bm, 'Internals', material('e220_blue', (0.05, 0.18, 0.55), rough=0.4),
                     dict(kind='dry', mass_g=6.0, buy=True), smooth=None))
    yc = (y0 + y1) / 2
    bm = bmesh.new()
    bm_box(bm, x0 + 6, x1 - 8, yc - 8, yc + 8, z0 + 1.0, z0 + 3.2)
    obs.append(mkobj('E220_shield', bm, 'Internals', MAT['steel'], dict(kind='dry', mass_g=0.0), smooth=None))
    bm = bmesh.new()
    bm_cyl(bm, (x1 - 2, yc, z0 + 3.5), (x1 + 7.5, yc, z0 + 3.5), 3.2, 6)
    bm_cyl(bm, (x1 + 7.5, yc, z0 + 3.5), (x1 + 9.0, yc, z0 + 3.5), 2.0, 24)
    obs.append(mkobj('E220_SMA', bm, 'Internals', MAT['brass'], dict(kind='dry', mass_g=0.0), smooth=None))
    return obs


def build_camera(x_rod1):
    obs = []
    xf = D['x_front']
    x_face = xf - P['cam_gap']
    x_back = x_face - P['cam_d']
    w, h = P['cam_w'], P['cam_h']
    bm = bmesh.new()
    bm_box(bm, x_back, x_face, -w / 2, w / 2, -h / 2, h / 2)
    bmesh.ops.bevel(bm, geom=[e for e in bm.edges], offset=4.0, segments=4, affect='EDGES', profile=0.5)
    ob = mkobj('Camera_GoPro_HERO7', bm, 'Internals', MAT['gopro'], dict(kind='dry', mass_g=117.0, buy=True))
    obs.append(ob)
    ly, lz = P['cam_lens_y'], P['cam_lens_z']
    bm = bmesh.new()
    bm_box(bm, x_face - 0.5, x_face + P['cam_bump'], ly - P['cam_bump_w'] / 2, ly + P['cam_bump_w'] / 2,
           lz - P['cam_bump_w'] / 2, lz + P['cam_bump_w'] / 2)
    bmesh.ops.bevel(bm, geom=[e for e in bm.edges], offset=3.0, segments=3, affect='EDGES', profile=0.5)
    obs.append(mkobj('Camera_lens_bump', bm, 'Internals', MAT['gopro'], dict(kind='dry', mass_g=0.0)))
    bm = bmesh.new()
    bm_cyl(bm, (x_face + P['cam_bump'] - 0.2, ly, lz), (x_face + P['cam_bump'] + 0.4, ly, lz), 7.5, 48)
    obs.append(mkobj('Camera_lens_glass', bm, 'Internals', MAT['glass_dark'], dict(kind='dry', mass_g=0.0)))
    # black foam anti-glare ring: from the lens bump to the window's inner face
    x_win = D['x_front_face'] - P['window_t']
    x_ring0 = x_face + P['cam_bump'] - 1.5
    bm = rev_bm([(0, 11.5), (0, 16), (x_win - x_ring0, 16), (x_win - x_ring0, 11.5)], 48)
    bm_transform(bm, Matrix.Translation((x_ring0, ly, lz)))
    obs.append(mkobj('Camera_foam_ring', bm, 'Internals', MAT['foam'], dict(kind='dry', mass_g=0.5)))
    # cradle
    bm = bmesh.new()
    zf = -h / 2 - 0.6
    bm_box(bm, x_rod1 - 3, x_back - 3, -P['rod_y'] - 3, P['rod_y'] + 3, -14, 14)          # back plate
    bm_box(bm, x_back - 3, x_face - 8, -27, 27, zf - 2.2, zf)                           # floor
    for s in (1, -1):
        bm_box(bm, x_back - 3, x_face - 10, *sorted((s * (w / 2 + 0.6), s * (w / 2 + 3.4))), -12, 12)   # fingers
        bm_cyl(bm, (x_rod1 - 3, s * P['rod_y'], P['rod_z']), (x_back + 6, s * P['rod_y'], P['rod_z']), 4.6, 24)
    ob = mkobj('Sled_camera_cradle', bm, 'Internals', MAT['petg_grey'],
               dict(kind='dry', material='petg', fill=0.5, print=True, print_dir=(0, 0, 1),
                    note='Add 3 mm foam behind the camera so it is pushed gently to the window.'))
    cut = bmesh.new()
    for s in (1, -1):
        bm_cyl(cut, (x_rod1 - 6, s * P['rod_y'], P['rod_z']), (x_rod1 + 0.5, s * P['rod_y'], P['rod_z']),
               P['rod_d'] / 2 + 0.15, 24)
    bm_box(cut, x_back - 0.01, x_face + 5, -w / 2 - 0.6, w / 2 + 0.6, -h / 2 - 0.6, h / 2 + 0.6)
    boolean(ob, cut, 'DIFFERENCE')
    # keep the cradle inside the bore
    cut = bmesh.new()
    bm_cyl(cut, (x_rod1 - 10, 0, 0), (x_face + 10, 0, 0), D['ri_pipe'] - 0.8, 128)
    boolean(ob, cut, 'INTERSECT')
    obs.append(ob)
    return obs


# ---------------------------------------------------------------- cables
def cable(name, pts, r=2.8, mat='cable'):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = r
    cu.bevel_resolution = 3
    cu.use_fill_caps = True
    sp = cu.splines.new('BEZIER')
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    ob = bpy.data.objects.new(name, cu)
    coll('Cables').objects.link(ob)
    cu.materials.append(MAT[mat])
    return ob


def build_cables(mast_top):
    xb = D['x_rear_face']
    out = []
    pen = {n: a for n, a, _ in rear_penetrators()}
    R = P['gland_ring_r']

    def gl(n):
        a = pen[n]
        return Vector((xb - 14, R * sin(a), R * cos(a)))
    ty = P['thruster_y']
    xr, xm = P['clamp_rear_x'], P['clamp_mid_x']
    zc = D['clamp_ro'] + 1.0
    for side, tag in ((1, 'port'), (-1, 'stbd')):
        g = gl(f'thruster H-{tag}')
        out.append(cable(f'Cable_H_{tag}', [g, g + Vector((-8, 0, 0)), (xb - 16, side * 47, 3),
                                             (xb + 8, side * 58, 4), (xr + 22, side * 70, 4),
                                             (xr + 22, side * (ty - 14), 3)]))
        g = gl(f'thruster V-{tag}')
        out.append(cable(f'Cable_V_{tag}', [g, g + Vector((-8, 0, 0)), (xb - 16, side * 48, -3),
                                             (xb + 8, side * 52, -10), (xr + 30, side * 48.5, -14),
                                             (xm - 30, side * 49, -14), (xm - 10, side * 60, 26),
                                             (xm, side * (ty - 14), 26)]))
    rp = D['ro_pipe']
    g = gl('mast cable (GPS+strobe)')
    out.append(cable('Cable_mast', [g, g + Vector((-8, 0, 0)), (xb - 16, 0, 47), (xb + 12, 0, 57.5),
                                    (xr, 0, zc + 3.5), (xr + 30, 0, rp + 3), (xm - 40, 0, rp + 3),
                                    (xm - 10, 0, zc + 3)], r=2.6))
    g = gl('LoRa coax')
    out.append(cable('Cable_LoRa_coax', [g, g + Vector((-8, 0, 0)), (xb - 16, 8, 46), (xb + 12, 6, 57),
                                         (xr, 5, zc + 2.5), (xr + 30, 5, rp + 2), (xm - 40, 5, rp + 2),
                                         (xm - 12, 3, zc + 3)], r=1.4))
    g = gl('vent tube + ball valve')
    v = cable('Vent_tube', [g, g + Vector((-12, 0, 0)), (xb - 30, -10, 22)], r=3.0, mat='brass')
    out.append(v)
    return out


# =============================================================================
# ASSEMBLY
# =============================================================================

def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for blocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for b in list(blocks):
            blocks.remove(b)
    COLL.clear()
    MAT.clear()


def build_all(pcb_layout=None):
    clear_scene()
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 0.001
    sc.unit_settings.length_unit = 'MILLIMETERS'
    make_materials()
    parts = {}
    parts['pipe'] = build_pipe()
    parts['front_cap'] = build_front_cap()
    parts['window'] = build_window()
    parts['rear_cap'] = build_rear_cap()
    parts['orings'] = build_orings()
    parts['penetrators'] = build_penetrators()
    for k in ('front', 'mid', 'rear'):
        parts[f'clamp_{k}'] = build_clamp(k)
    parts['keel'], keel_z0 = build_keel()
    parts['mag_target'] = build_mag_target()
    parts['nose_ring'] = build_nose_ring()
    parts['tail_cone'] = build_tail_cone()
    parts['mast'], mast_top = build_mast()
    parts['thrusters'] = []
    for kind, side, handed in (('H', 1, 1), ('H', -1, -1), ('V', 1, -1), ('V', -1, 1)):
        parts['thrusters'] += build_thruster(kind, side, handed)
    parts['internals'] = build_internals(pcb_layout)
    parts['cables'] = build_cables(mast_top)
    parts['keel_z0'] = keel_z0
    parts['mast_top'] = mast_top
    # trim: place ballast pods so the sub floats level with the target reserve buoyancy
    trim = solve_trim(keel_z0)
    parts['trim'] = trim
    for i, (xc, mass) in enumerate(trim['pods']):
        pod = build_pod(f'BallastPod_{"front" if i == 0 else "rear"}', xc, keel_z0)
        fill_h = min(P['pod_h'] - 3.5, max(0.5, mass / RHO['lead'] / 0.62 * 1000.0 /
                     ((P['pod_l'] - 2 * P['pod_wall'] - 24) * (P['pod_w'] - 2 * P['pod_wall']))))
        bm = bmesh.new()
        L, W, t = P['pod_l'], P['pod_w'], P['pod_wall']
        bm_box(bm, xc - L / 2 + t + 12.2, xc + L / 2 - t - 12.2, -W / 2 + t + 0.2, W / 2 - t - 0.2,
               keel_z0 - P['pod_h'] + 3.2, keel_z0 - P['pod_h'] + 3.2 + fill_h)
        mkobj(f'LeadShot_{"front" if i == 0 else "rear"}', bm, 'Frame', MAT['lead'], dict(kind='ballast'))
    return parts


# =============================================================================
# MASS PROPERTIES / TRIM
# =============================================================================

def displacement_envelope():
    """Closed outer surface of the sealed hull (pipe + caps), cm3 and centroid."""
    rp, rc = D['ro_pipe'], D['ro_cap']
    xo_f = D['x_front'] - P['cap_sleeve_len']
    xo_r = D['x_rear'] + P['cap_sleeve_len']
    xb, xf = D['x_rear_face'], D['x_front_face']
    ch = P['rear_chamfer']
    prof = [(xb, 0), (xb, rc - ch), (xb + ch, rc), (xo_r, rc), (xo_r, rp), (xo_f, rp), (xo_f, rc),
            (xf, rc), (xf, 0)]
    bm = rev_bm(prof, 192)
    ob = mkobj('_envelope', bm, 'Hull', None, smooth=None)
    V, C = mesh_volume_centroid(ob)
    bpy.data.objects.remove(ob)
    return V, C


def mass_props():
    rows = []
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or 'kind' not in ob or ob['kind'] == 'ballast':
            continue
        V, C = mesh_volume_centroid(ob)
        kind = ob['kind']
        if 'mass_g' in ob:
            m = float(ob['mass_g'])
            disp = float(ob.get('disp_cm3', m / 1.6)) if kind == 'wet' else 0.0
        else:
            rho = RHO[ob['material']]
            fill = float(ob.get('fill', 1.0))
            m = V * rho * fill + float(ob.get('mass_extra_g', 0.0))
            disp = (V * fill + float(ob.get('disp_extra_cm3', 0.0))) if kind == 'wet' else 0.0
        rows.append(dict(name=ob.name, kind=kind, vol_cm3=V, mass_g=m, disp_cm3=disp,
                         cx=C.x, cy=C.y, cz=C.z))
    # cables (curves): estimate 45 g/m, 21 cm3/m
    for ob in bpy.data.objects:
        if ob.type == 'CURVE':
            L = sum(sp.calc_length() for sp in ob.data.splines)
            dens = 45.0 if 'coax' not in ob.name else 12.0
            m = dens * L / 1000.0 + (25.0 if ob.name == 'Vent_tube' else 0.0)
            pts = [bp.co for sp in ob.data.splines for bp in sp.bezier_points]
            c = sum(pts, Vector((0, 0, 0))) / len(pts)
            rows.append(dict(name=ob.name, kind='wet', vol_cm3=0, mass_g=m, disp_cm3=m / 1.9,
                             cx=c.x, cy=c.y, cz=c.z))
    # allowances that are not modelled: internal wiring, screws, heat-set inserts, sealant
    rows.append(dict(name='Internal wiring + connectors (allowance)', kind='dry', vol_cm3=0, mass_g=45.0,
                     disp_cm3=0, cx=-40.0, cy=0.0, cz=0.0))
    rows.append(dict(name='Screws, nuts, inserts (allowance)', kind='wet', vol_cm3=0, mass_g=45.0,
                     disp_cm3=6.0, cx=0.0, cy=0.0, cz=-20.0))
    rows.append(dict(name='Grease, epoxy, sealant (allowance)', kind='pressure', vol_cm3=0, mass_g=20.0,
                     disp_cm3=0, cx=0.0, cy=0.0, cz=0.0))
    return rows


def solve_trim(keel_z0):
    rows = mass_props()
    Venv, Cenv = displacement_envelope()
    M = sum(r['mass_g'] for r in rows)
    Mx = sum(r['mass_g'] * r['cx'] for r in rows)
    Mz = sum(r['mass_g'] * r['cz'] for r in rows)
    Vw = sum(r['disp_cm3'] for r in rows)
    Vx = sum(r['disp_cm3'] * r['cx'] for r in rows) + Venv * Cenv.x
    Vz = sum(r['disp_cm3'] * r['cz'] for r in rows) + Venv * Cenv.z
    Vtot = Venv + Vw
    # printed pod shells (approximate before they exist)
    pod_shell = (P['pod_l'] * P['pod_w'] * P['pod_h'] / 1000.0) - pod_cavity_volume()
    pod_shell_m = pod_shell * RHO['petg']
    zc_pod = keel_z0 - P['pod_h'] / 2
    zc_lead = keel_z0 - P['pod_h'] + 3 + 8.0
    rw = RHO['water']
    R = P['reserve_buoyancy_g']
    # ballast lead mass so that displacement*rw - mass = R
    M_tot_no_lead = M + 2 * pod_shell_m
    V_no_lead = Vtot + 2 * pod_shell
    lead = (V_no_lead * rw - M_tot_no_lead - R) / (1 - rw / RHO['lead'])
    # longitudinal: choose the two pod centres on the 20 mm grid that put CG over CB
    best = None
    # pod centres sit 10 mm off the 20 mm hole grid so both pod bolts (+-50 mm) land on holes
    grid = [P['keel_x0'] + 20 + 20 * k for k in range(int((P['keel_x1'] - P['keel_x0']) / 20))]
    half = P['pod_l'] / 2
    for xf in grid:
        for xr in grid:
            if xf - xr < P['pod_l'] + 4 or xf + half > P['keel_x1'] or xr - half < P['keel_x0']:
                continue
            # split lead between pods: solve moment balance exactly (both >= 0)
            # CG_x(total) == CB_x(total)
            Vl = lead / RHO['lead']
            Vtotal = V_no_lead + Vl
            # unknown a = lead in front pod; rear gets lead - a
            # mass moment: Mx + pod shells + a*xf + (lead-a)*xr ; buoyancy moment: Vx + shells + Vl parts
            msum = M_tot_no_lead + lead
            Mxs = Mx + pod_shell_m * (xf + xr)
            Vxs = Vx + pod_shell * (xf + xr)
            # CGx = (Mxs + a xf + (lead-a) xr)/msum ;  CBx = (Vxs + (a xf + (lead-a) xr)/rho_pb)/Vtotal
            # linear in a:
            k1 = (xf - xr) / msum - (xf - xr) / RHO['lead'] / Vtotal
            k0 = (Mxs + lead * xr) / msum - (Vxs + lead * xr / RHO['lead']) / Vtotal
            if abs(k1) < 1e-12:
                continue
            a = -k0 / k1
            if a < 0 or a > lead:
                continue
            cap = pod_cavity_volume() * RHO['lead'] * 0.62
            if a > cap or lead - a > cap:
                continue
            score = abs(a - lead / 2)
            if best is None or score < best[0]:
                best = (score, xf, xr, a)
    if best is None:
        raise RuntimeError('Trim solver could not balance the vehicle - move the pods/keel.')
    _, xf, xr, a = best
    Vl = lead / RHO['lead']
    msum = M_tot_no_lead + lead
    cgx = (Mx + pod_shell_m * (xf + xr) + a * xf + (lead - a) * xr) / msum
    cgz = (Mz + pod_shell_m * 2 * zc_pod + lead * zc_lead) / msum
    Vtotal = V_no_lead + Vl
    cbx = (Vx + pod_shell * (xf + xr) + (a * xf + (lead - a) * xr) / RHO['lead']) / Vtotal
    cbz = (Vz + pod_shell * 2 * zc_pod + Vl * zc_lead) / Vtotal
    return dict(rows=rows, envelope_cm3=Venv, mass_no_ballast_g=M, wet_disp_cm3=Vw,
                lead_g=lead, pods=[(xf, a), (xr, lead - a)], total_mass_g=msum,
                displacement_cm3=Vtotal, reserve_g=Vtotal * rw - msum,
                cg=(cgx, 0.0, cgz), cb=(cbx, 0.0, cbz), bg_mm=cbz - cgz,
                pod_shell_g=pod_shell_m, pod_capacity_g=pod_cavity_volume() * RHO['lead'] * 0.62)


# =============================================================================
# EXPORTS
# =============================================================================

def write_stl(path, ob, up_dir):
    bm = ob_bm(ob)
    q = Vector(up_dir).normalized().rotation_difference(Vector((0, 0, 1)))
    bm.transform(q.to_matrix().to_4x4())
    bmesh.ops.triangulate(bm, faces=bm.faces)
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    off = Vector((-(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, -min(zs)))
    bm.transform(Matrix.Translation(off))
    bm.normal_update()
    with open(path, 'wb') as f:
        f.write(b'Minnow AUV - ' + ob.name.encode()[:60] + b' ' * (80 - 13 - min(60, len(ob.name))))
        f.write(struct.pack('<I', len(bm.faces)))
        for fc in bm.faces:
            f.write(struct.pack('<3f', *fc.normal))
            for v in fc.verts:
                f.write(struct.pack('<3f', *v.co))
            f.write(b'\x00\x00')
    size = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    bm.free()
    return size


def export_stls(out):
    d = os.path.join(out, 'stl')
    os.makedirs(d, exist_ok=True)
    rows = []
    seen_mirror = set()
    for ob in sorted(bpy.data.objects, key=lambda o: o.name):
        if ob.type != 'MESH' or not ob.get('print'):
            continue
        name = ob.name
        # identical parts: export one of each design
        if name.startswith('Duct_V_stbd'):
            continue    # same STL as Duct_V_port rotated 180 deg
        if name.startswith('Prop_') and ('_stbd_' in name):
            continue    # CW/CCW covered by the port props (one of each handedness)
        if name == 'BallastPod_rear':
            continue    # identical to the front pod
        V, _ = mesh_volume_centroid(ob)
        fn = f'{name}.stl'
        size = write_stl(os.path.join(d, fn), ob, tuple(ob['print_dir']))
        qty = 1
        if name.startswith(('Duct_V_port', 'Prop_', 'BallastPod_')):
            qty = 2
        fill = float(ob.get('fill', 1.0))
        rows.append(dict(file=fn, qty=qty, grams_each=round(V * RHO['petg'] * fill, 1),
                         bbox_mm=[round(s, 1) for s in size], note=ob.get('note', '')))
    # O-ring fit-test ring (print this first!)
    fit = build_fit_test()
    size = write_stl(os.path.join(d, '00_Oring_fit_test.stl'), fit, (-1, 0, 0))
    V, _ = mesh_volume_centroid(fit)
    rows.insert(0, dict(file='00_Oring_fit_test.stl', qty=1, grams_each=round(V * RHO['petg'], 1),
                        bbox_mm=[round(s, 1) for s in size],
                        note='PRINT FIRST. Slide over your pipe with one greased O-ring: it should '
                             'slide on firmly and seal; adjust cap_bore_clear/oring_squeeze if not.'))
    bpy.data.objects.remove(fit)
    with open(os.path.join(out, 'print_list.json'), 'w') as f:
        json.dump(rows, f, indent=1)
    return rows


def build_fit_test():
    xo = 0.0
    rb, rg, gw, ro = D['rb'], D['rg'], D['gw'], D['ro_cap']
    L = 16.0
    prof = [(xo, rb + 1.0), (xo, ro), (L, ro), (L, rb), (xo + 8 + gw / 2, rb), (xo + 8 + gw / 2, rg),
            (xo + 8 - gw / 2, rg), (xo + 8 - gw / 2, rb), (xo + 1.0, rb)]
    return mkobj('_fit_test', rev_bm(prof, P['seg']), 'Hull', None)


def write_reports(out, parts):
    trim = parts['trim']
    rep = dict(params=P, derived=D, trim={k: v for k, v in trim.items() if k != 'rows'},
               penetrators=[dict(name=n, angle_deg=None if a is None else round(math.degrees(a), 1),
                                 hole_d=dia) for n, a, dia in rear_penetrators()],
               mast_top_z=parts['mast_top'])
    with open(os.path.join(out, 'design_data.json'), 'w') as f:
        json.dump(rep, f, indent=1, default=lambda o: list(o) if hasattr(o, '__iter__') else str(o))
    rows = sorted(trim['rows'], key=lambda r: -r['mass_g'])
    lines = ['# Mass, buoyancy and trim report', '',
             'Generated by `cad/build_sub.py` from the CAD geometry. Printed parts use their real mesh '
             'volume; bought parts use catalogue masses. Re-run after you weigh your own parts.', '',
             '| Quantity | Value |', '|---|---|',
             f"| Sealed hull displacement | {trim['envelope_cm3']:.0f} cm3 |",
             f"| Mass without ballast | {trim['mass_no_ballast_g']:.0f} g |",
             f"| Lead ballast needed | {trim['lead_g']:.0f} g (front pod {trim['pods'][0][1]:.0f} g at x={trim['pods'][0][0]:.0f} mm, "
             f"rear pod {trim['pods'][1][1]:.0f} g at x={trim['pods'][1][0]:.0f} mm) |",
             f"| Ballast pod capacity | {trim['pod_capacity_g']:.0f} g each (lead shot) |",
             f"| Total mass ready to dive | {trim['total_mass_g']:.0f} g |",
             f"| Total displacement | {trim['displacement_cm3']:.0f} cm3 |",
             f"| Reserve buoyancy (floats when off) | {trim['reserve_g']:.0f} g |",
             f"| Centre of gravity (x, z) | {trim['cg'][0]:.1f}, {trim['cg'][2]:.1f} mm |",
             f"| Centre of buoyancy (x, z) | {trim['cb'][0]:.1f}, {trim['cb'][2]:.1f} mm |",
             f"| Metacentric height BG | {trim['bg_mm']:.1f} mm (stable, keeps the camera level) |",
             f"| Mast top above hull axis | {parts['mast_top']:.0f} mm |",
             '', '## Breakdown (heaviest first)', '', '| Part | Where | Mass g | Displaces cm3 | x mm | z mm |',
             '|---|---|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['name']} | {r['kind']} | {r['mass_g']:.1f} | {r['disp_cm3']:.1f} | {r['cx']:.0f} | {r['cz']:.0f} |")
    lines += ['', '`pressure` and `dry` parts are inside the sealed envelope (their displacement is the envelope); '
              '`wet` parts displace their own material volume.']
    with open(os.path.join(out, 'trim_report.md'), 'w') as f:
        f.write('\n'.join(lines) + '\n')


# =============================================================================
# RENDERING
# =============================================================================

def setup_render(quick=False, res=(1920, 1080)):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 24 if quick else 64
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except TypeError:
        pass
    sc.cycles.max_bounces = 8
    sc.cycles.transmission_bounces = 8
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except TypeError:
        pass
    w = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    bg.inputs[0].default_value = (0.78, 0.82, 0.87, 1.0)
    bg.inputs[1].default_value = 0.55
    # floor
    if 'Floor' not in bpy.data.objects:
        bm = bmesh.new()
        bm_box(bm, -4000, 4000, -4000, 4000, -96.0, -95.0)
        mkobj('Floor', bm, 'Studio', MAT['floor'], smooth=None)
    # sun lights: their strength does not depend on distance, so the mm scale
    # of the scene does not matter
    for name, loc, energy, angle, col in (
            ('Key', (450, 700, 900), 3.2, 9.0, (1.0, 0.96, 0.90)),
            ('Fill', (-700, -500, 400), 0.9, 25.0, (0.85, 0.9, 1.0)),
            ('Rim', (-500, 600, 250), 1.6, 5.0, (1.0, 1.0, 1.0))):
        if name in bpy.data.objects:
            continue
        ld = bpy.data.lights.new(name, 'SUN')
        ld.energy = energy
        ld.angle = radians(angle)
        ld.color = col
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        coll('Studio').objects.link(lo)
        look_at(lo, (0, 0, 0))


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def camera(name, loc, target, lens=50, ortho=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 5
    cd.clip_end = 20000
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    co = bpy.data.objects.new(name, cd)
    co.location = loc
    coll('Studio').objects.link(co)
    look_at(co, target)
    return co


def render(path, cam):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('rendered', path, flush=True)


def set_hidden(names_pred, hidden):
    for ob in bpy.data.objects:
        if names_pred(ob):
            ob.hide_render = hidden
            ob.hide_viewport = hidden


def make_section_copies(cut_pred, keep_side='neg_y'):
    """Duplicate the shells that hide the internals and cut away the +Y half."""
    made = []
    for ob in list(bpy.data.objects):
        if ob.type != 'MESH' or not cut_pred(ob):
            continue
        c = bpy.data.objects.new(ob.name + '_SECTION', ob.data.copy())
        coll('Section').objects.link(c)
        bm = bmesh.new()
        bm_box(bm, -1000, 1000, 0.0, 1000, -1000, 1000)
        boolean(c, bm, 'DIFFERENCE')
        shade(c)
        made.append(c)
        ob.hide_render = ob.hide_viewport = True
    return made


def do_renders(out, quick=False):
    rd = os.path.join(out, 'renders')
    os.makedirs(rd, exist_ok=True)
    setup_render(quick)
    tgt = Vector((-20, 0, 5))
    hero = camera('Cam_hero', (520, 760, 330), tgt, lens=50)
    render(os.path.join(rd, '01_hero.png'), hero)
    rear = camera('Cam_rear', (-900, -560, 330), tgt, lens=55)
    render(os.path.join(rd, '02_rear_three_quarter.png'), rear)
    # side & top orthographic (used for the dimensioned drawing)
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = 2000, 1100
    side = camera('Cam_side', (-34, -2000, 20), (-34, 0, 20), ortho=620)
    render(os.path.join(rd, 'ortho_side.png'), side)
    top = camera('Cam_top', (-34, 0, 2000), (-34, 0, 0), ortho=620)
    top.rotation_euler = (0, 0, 0)
    render(os.path.join(rd, 'ortho_top.png'), top)
    front = camera('Cam_front', (2000, 0, 15), (0, 0, 15), ortho=330)
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = 1400, 1100
    render(os.path.join(rd, 'ortho_front.png'), front)
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = 1920, 1080
    # cutaway: hide port thrusters/cables, cut the shells in half
    shells = ('Hull_PVC_pipe', 'FrontCap', 'RearCap', 'NoseRing', 'TailCone', 'Window_acrylic', 'Oring_',
              'Clamp_', 'Gland_', 'DepthSensor')
    port_hide = lambda ob: ('_port' in ob.name) or ob.name in ('Cable_mast', 'Cable_LoRa_coax')
    set_hidden(port_hide, True)
    secs = make_section_copies(lambda ob: ob.name.startswith(shells))
    cut = camera('Cam_cutaway', (330, 820, 300), Vector((-10, 0, -5)), lens=46)
    render(os.path.join(rd, '03_cutaway.png'), cut)
    # seal detail (front end)
    det = camera('Cam_seal', (250, 330, 60), Vector((185, 0, 0)), lens=60)
    set_hidden(lambda ob: ob.name.startswith(('Camera', 'Sled_camera')), True)
    render(os.path.join(rd, '05_front_seal_section.png'), det)
    set_hidden(lambda ob: ob.name.startswith(('Camera', 'Sled_camera')), False)
    det2 = camera('Cam_rearseal', (-120, 330, 90), Vector((-185, 0, 0)), lens=60)
    render(os.path.join(rd, '06_rear_cap_section.png'), det2)
    for c in secs:
        bpy.data.objects.remove(c)
    for ob in bpy.data.objects:
        ob.hide_render = ob.hide_viewport = False
    # exploded view
    offsets = {'NoseRing': (110, 0, 0), 'Window_acrylic': (80, 0, 0), 'FrontCap': (45, 0, 0),
               'Oring_1': (20, 0, 0), 'Oring_2': (20, 0, 0), 'RearCap': (-60, 0, 0), 'Oring_3': (-30, 0, 0),
               'Oring_4': (-30, 0, 0), 'TailCone': (-150, 0, 0), 'Gland_': (-60, 0, 0), 'DepthSensor': (-60, 0, 0),
               'Mast': (0, 0, 70), 'Duct_H_port': (0, 70, 0), 'Motor_H_port': (0, 70, 0),
               'MotorBase_H_port': (0, 70, 0), 'PropAdapter_H_port': (0, 70, 0), 'Prop_H_port': (-40, 70, 0),
               'Duct_V_port': (0, 70, 0), 'Motor_V_port': (0, 70, 0), 'MotorBase_V_port': (0, 70, 0),
               'PropAdapter_V_port': (0, 70, 0), 'Prop_V_port': (0, 70, -40),
               'BallastPod_': (0, 250, 0), 'LeadShot_': (0, 250, 0), 'Keel_': (0, 215, 0)}
    hide_cables = [ob for ob in bpy.data.objects if ob.type == 'CURVE']
    for ob in hide_cables:
        ob.hide_render = True
    moved = []
    for ob in bpy.data.objects:
        for k, v in offsets.items():
            if ob.name.startswith(k):
                ob.location = Vector(v)
                moved.append(ob)
                break
    ex = camera('Cam_exploded', (420, 1150, 520), Vector((-40, 60, -10)), lens=36)
    render(os.path.join(rd, '04_exploded.png'), ex)
    for ob in moved:
        ob.location = (0, 0, 0)
    # internals only: the sled as it slides out
    set_hidden(lambda ob: not (ob.users_collection and ob.users_collection[0].name in ('Internals', 'Studio')), True)
    for ob in bpy.data.objects:
        if ob.name == 'Floor':
            ob.hide_render = False
    sled = camera('Cam_sled', (260, 430, 210), Vector((10, 0, -5)), lens=50)
    render(os.path.join(rd, '07_internal_sled.png'), sled)
    for ob in bpy.data.objects:
        ob.hide_render = ob.hide_viewport = False
    for ob in hide_cables:
        ob.hide_render = False
    # thruster close-up
    th = camera('Cam_thruster', (60, 330, 140), Vector((-146, 94, 0)), lens=70)
    render(os.path.join(rd, '08_thruster_closeup.png'), th)


# =============================================================================
# MAIN
# =============================================================================

def script_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


def main(argv):
    out = script_dir()
    if '--out' in argv:
        out = argv[argv.index('--out') + 1]
    layout = None
    if '--core' in argv:
        BOARD['name'] = 'core'
    lp = os.path.join(script_dir(), '..', pcb_dir(), 'placement.json')
    if os.path.exists(lp):
        with open(lp) as f:
            layout = json.load(f)
    parts = build_all(layout)
    t = parts['trim']
    print(f"[trim] envelope {t['envelope_cm3']:.0f} cm3, mass {t['mass_no_ballast_g']:.0f} g, "
          f"lead {t['lead_g']:.0f} g, pods {t['pods']}, reserve {t['reserve_g']:.1f} g, BG {t['bg_mm']:.1f} mm",
          flush=True)
    print(f"[seal] groove radial depth {D['gap']:.3f} mm, width {D['gw']:.2f} mm, cap OD {2 * D['ro_cap']:.2f} mm, "
          f"groove fill {D['gland_fill'] * 100:.0f} %", flush=True)
    write_reports(out, parts)
    if '--stl' in argv:
        rows = export_stls(out)
        print(f"[stl] {len(rows)} files, {sum(r['grams_each'] * r['qty'] for r in rows):.0f} g of PETG", flush=True)
    if '--blend' in argv:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'minnow_auv.blend'), compress=True)
    if '--render' in argv:
        do_renders(out, quick='--quick' in argv)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    main(argv)
