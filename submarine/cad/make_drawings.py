#!/usr/bin/env python3
"""
make_drawings.py - 2D drawings made from the CAD output (run after build_sub.py --render).

  drawings/window_80x8.svg / .dxf     laser-cut file for the acrylic camera window
  drawings/general_arrangement.png    side / top / front views with the main dimensions
  drawings/end_cap_sections.png       half sections of both O-ring end caps, dimensioned

Needs matplotlib + Pillow (python3.11 -m pip install matplotlib pillow).
"""
import json
import math
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402
from PIL import Image  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DD = json.load(open(os.path.join(HERE, 'design_data.json')))
P, D = DD['params'], DD['derived']
OUT = os.path.join(HERE, 'drawings')
os.makedirs(OUT, exist_ok=True)
INK = '#14365a'


def window_files():
    r = P['window_d'] / 2
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{2 * r + 10}mm" height="{2 * r + 10}mm" '
           f'viewBox="0 0 {2 * r + 10} {2 * r + 10}">\n'
           f'  <circle cx="{r + 5}" cy="{r + 5}" r="{r}" fill="none" stroke="#ff0000" stroke-width="0.1"/>\n'
           f'  <!-- cut line: {P["window_d"]} mm dia. Material: {P["window_t"]} mm CAST acrylic, clear. Qty 1. -->\n'
           '</svg>\n')
    open(os.path.join(OUT, 'window_80x8.svg'), 'w').write(svg)
    dxf = '\n'.join(['0', 'SECTION', '2', 'ENTITIES', '0', 'CIRCLE', '8', 'CUT', '10', '0.0', '20', '0.0', '30', '0.0',
                     '40', f'{r:.3f}', '0', 'ENDSEC', '0', 'EOF']) + '\n'
    open(os.path.join(OUT, 'window_80x8.dxf'), 'w').write(dxf)


def dim(ax, p0, p1, text, off=(0, 0), color=INK, fs=10, ext=True):
    (x0, y0), (x1, y1) = p0, p1
    ox, oy = off
    a0, a1 = (x0 + ox, y0 + oy), (x1 + ox, y1 + oy)
    ax.annotate('', xy=a1, xytext=a0, arrowprops=dict(arrowstyle='<->', color=color, lw=1.1, shrinkA=0, shrinkB=0))
    if ext and (ox or oy):
        for (x, y), (ax_, ay_) in ((p0, a0), (p1, a1)):
            ax.plot([x, ax_], [y, ay_], color=color, lw=0.6, ls=':')
    mx, my = (a0[0] + a1[0]) / 2, (a0[1] + a1[1]) / 2
    vertical = abs(x1 - x0) < 1e-6
    span = abs(y1 - y0) if vertical else abs(x1 - x0)
    gap = 0.03 * span + 1.0
    ax.text(mx + (gap if vertical else 0), my + (0 if vertical else gap), text, color=color, fontsize=fs,
            ha='left' if vertical else 'center', va='center' if vertical else 'bottom', rotation=0,
            bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.85))


def ortho_axes(ax, img_path, cx, cy, scale_mm, h_axis='x', v_axis='z'):
    """Show an orthographic render so that the axes are in vehicle millimetres."""
    im = Image.open(img_path)
    w, h = im.size
    half_w = scale_mm / 2
    half_h = half_w * h / w
    ax.imshow(im, extent=[cx - half_w, cx + half_w, cy - half_h, cy + half_h])
    ax.set_xlim(cx - half_w, cx + half_w)
    ax.set_ylim(cy - half_h, cy + half_h)
    ax.set_aspect('equal')
    ax.axis('off')


def general_arrangement():
    rd = os.path.join(HERE, 'renders')
    x_nose = D['x_front_face'] + 3.0
    x_tail = D['x_rear_face'] - 62.0
    z_top = DD['mast_top_z']
    z_bot = -(D['ro_pipe'] + 11) - P['keel_t'] - P['pod_h']
    half_w = P['thruster_y'] + D['duct_ro']
    fig = plt.figure(figsize=(16.5, 11.7), dpi=150)
    fig.suptitle('Minnow AUV - general arrangement (mm)', fontsize=16, color=INK, x=0.02, ha='left', y=0.997)
    # side view (camera on the starboard side, nose to the right)
    ax = fig.add_axes([0.01, 0.50, 0.66, 0.455])
    ortho_axes(ax, os.path.join(rd, 'ortho_side.png'), -34, 20, 620)
    dim(ax, (x_tail, -112), (x_nose, -112), f'overall length {x_nose - x_tail:.0f}', fs=11)
    dim(ax, (D['x_rear'], -140), (D['x_front'], -140), f'PVC pressure hull {P["pipe_len"]:.0f}', fs=9)
    dim(ax, (x_nose + 15, z_bot), (x_nose + 15, z_top), f'height {z_top - z_bot:.0f}\n(mast to pods)', fs=10)
    for name, x in (('front clamp', P['clamp_front_x']), ('mid clamp\n+ vertical thrusters\n+ mast', P['clamp_mid_x']),
                    ('rear clamp\n+ horizontal thrusters', P['clamp_rear_x'])):
        ax.annotate(f'{name}\nx = {x:+.0f}', xy=(x, 53), xytext=(x + (0 if x else 75), 140 if x else 150), color=INK, fontsize=8,
                    ha='center', arrowprops=dict(arrowstyle='-', color=INK, lw=0.6))
    cg = DD['trim']['cg']
    ax.plot([cg[0]], [cg[2]], marker='o', ms=9, mfc='white', mec='#c0392b', mew=2)
    ax.text(cg[0] + 8, cg[2] - 14, 'CG', color='#c0392b', fontsize=9, weight='bold')
    cb = DD['trim']['cb']
    ax.plot([cb[0]], [cb[2]], marker='+', ms=12, color='#1e8449', mew=2)
    ax.text(cb[0] + 8, cb[2] + 4, 'CB', color='#1e8449', fontsize=9, weight='bold')
    ax.text(x_tail, z_top + 10, 'SIDE (starboard)', color=INK, fontsize=11, weight='bold')
    # top view
    ax = fig.add_axes([0.01, 0.03, 0.66, 0.46])
    ortho_axes(ax, os.path.join(rd, 'ortho_top.png'), -34, 0, 620)
    dim(ax, (x_nose + 10, -half_w), (x_nose + 10, half_w), f'width over thrusters {2 * half_w:.0f}', fs=10)
    dim(ax, (P['clamp_rear_x'], -half_w - 14), (P['clamp_mid_x'], -half_w - 14),
        f'thruster stations {P["clamp_mid_x"] - P["clamp_rear_x"]:.0f}', fs=9)
    ax.text(x_tail, half_w + 22, 'TOP (nose to the right)', color=INK, fontsize=11, weight='bold')
    # front view
    ax = fig.add_axes([0.69, 0.45, 0.30, 0.50])
    ortho_axes(ax, os.path.join(rd, 'ortho_front.png'), 0, 15, 330)
    dim(ax, (-D['ro_cap'] - 2.7, -78), (D['ro_cap'] + 2.7, -78), f'nose {2 * (D["ro_cap"] + 2.7):.0f} dia', fs=9)
    ax.text(-160, 160, 'FRONT (camera window)', color=INK, fontsize=11, weight='bold')
    # key data table
    ax = fig.add_axes([0.69, 0.03, 0.30, 0.40])
    ax.axis('off')
    t = DD['trim']
    rows = [('Mass ready to dive', f"{t['total_mass_g'] / 1000:.2f} kg"),
            ('Displacement', f"{t['displacement_cm3'] / 1000:.2f} L"),
            ('Lead ballast (2 pods)', f"{t['lead_g']:.0f} g"),
            ('Reserve buoyancy', f"{t['reserve_g']:.0f} g (floats when off)"),
            ('BG (stability)', f"{t['bg_mm']:.1f} mm"),
            ('Pressure hull', f"PVC-U {P['pipe_od']:.0f} x {P['pipe_wall']} mm, L {P['pipe_len']:.0f}"),
            ('End-cap O-rings', f"4 x {P['oring_cs']} mm CS, {P['oring_squeeze'] * 100:.0f}% squeeze"),
            ('Camera window', f"{P['window_d']:.0f} x {P['window_t']:.0f} mm cast acrylic"),
            ('Thrusters', '4 x A2212 in 54 mm ducts, 51 mm props'),
            ('Design depth', '10 m (test to 5 m first)')]
    ax.table(cellText=rows, colLabels=['Item', 'Value'], loc='upper left', cellLoc='left', colWidths=[0.45, 0.55])
    fig.savefig(os.path.join(OUT, 'general_arrangement.png'))
    fig.savefig(os.path.join(OUT, 'general_arrangement.pdf'))
    plt.close(fig)


def cap_profiles():
    rb, rg, gw, ro = D['rb'], D['rg'], D['gw'], D['ro_cap']
    ls = P['cap_sleeve_len']
    fw, tw = P['front_wall'], P['window_t']
    rw, rs, ra = D['rw'], D['rs'], D['ra']
    g1, g2 = P['groove1'], P['groove2']

    def bore(x_open, sgn):
        pts = []
        for gpos in (g2, g1):
            xc = x_open + sgn * gpos
            a, b = xc + sgn * gw / 2, xc - sgn * gw / 2
            pts += [(a, rb), (a, rg), (b, rg), (b, rb)]
        pts.append((x_open + sgn * 1.0, rb))
        return pts
    xo, xs, xf = 0.0, ls, ls + fw
    x_seat = xf - tw
    front = [(xo, rb + 1.0), (xo, ro - 0.8), (xo + 0.8, ro), (xf - 1.0, ro), (xf, ro - 1.0), (xf, rw), (x_seat, rw),
             (x_seat, rs), (x_seat - (rs - ra), ra), (xs, ra), (xs, rb)] + bore(xo, 1)
    xr, xb = ls, ls + P['rear_wall']
    rear = [(0, rb + 1.0), (0, ro - 0.8), (0.8, ro), (xb - P['rear_chamfer'], ro), (xb, ro - P['rear_chamfer']),
            (xb, 0), (xr, 0), (xr, rb)] + [(ls - x, r) for x, r in bore(ls, -1)][::-1][1:] + [(1.0, rb)]
    # rebuild rear bore properly (open end at x=0, grooves measured from it)
    rear = [(0, rb + 1.0), (0, ro - 0.8), (0.8, ro), (xb - P['rear_chamfer'], ro), (xb, ro - P['rear_chamfer']),
            (xb, 0), (xr, 0), (xr, rb)]
    for gpos in (g2, g1):
        a, b = gpos + gw / 2, gpos - gw / 2
        rear += [(a, rb), (a, rg), (b, rg), (b, rb)]
    rear.append((1.0, rb))
    fig, axs = plt.subplots(1, 2, figsize=(16.5, 7.5), dpi=150)
    fig.suptitle('O-ring end caps - half sections (mm). Print solid PETG; the pipe slides in from the left.',
                 fontsize=13, color=INK, x=0.02, ha='left')
    for ax, prof, title in ((axs[0], front, 'FRONT CAP (camera window)'), (axs[1], rear, 'REAR CAP (penetrators)')):
        ax.add_patch(Polygon(prof, closed=True, fc='#c9d3dd', ec=INK, lw=1.4))
        # pipe
        ax.add_patch(Polygon([(0, D['ri_pipe']), (ls, D['ri_pipe']), (ls, D['ro_pipe']), (-14, D['ro_pipe']),
                              (-14, D['ri_pipe'])], closed=True, fc='#f0a35c', ec='#9a5a1c', lw=1.0, alpha=0.75))
        for gpos in (g1, g2):
            ax.add_patch(plt.Circle((gpos, (D['ro_pipe'] + rg) / 2), D['gap'] / 2, fc='#222', ec='none'))
        if 'FRONT' in title:
            ax.add_patch(Polygon([(x_seat, 0), (xf, 0), (xf, P['window_d'] / 2), (x_seat, P['window_d'] / 2)], closed=True,
                                 fc='#bfe6ff', ec='#2a7ab0', lw=1.0))
            ax.text(x_seat + tw / 2, 18, 'acrylic\nwindow', ha='center', fontsize=8, color='#2a7ab0', rotation=90)
            dim(ax, (xf + 3, 0), (xf + 3, ra), f'aperture\nR{ra:.1f}', fs=8)
            ax.text(xf + 1, -4.5, f'window {tw:.0f} thick', fontsize=8, color='#2a7ab0', ha='right')
        right = max(x for x, _ in prof)
        dim(ax, (0, ro + 6), (right, ro + 6), f'overall {right:.1f}', fs=9)
        dim(ax, (0, ro + 14), (ls, ro + 14), f'sleeve {ls:.0f}', fs=9)
        dim(ax, (-10, 0), (-10, D['ro_pipe']), f'pipe R{D["ro_pipe"]:.1f}', fs=8)
        dim(ax, (right + 10, 0), (right + 10, ro), f'R{ro:.2f}\n(OD {2 * ro:.2f})', fs=8)
        ax.annotate(f'O-ring groove: bottom dia {2 * rg:.2f}, width {gw:.2f}\ncentres {g1:.0f} and {g2:.0f} mm from the open end\n'
                    f'bore dia {2 * rb:.2f}; {P["oring_squeeze"] * 100:.0f}% squeeze, {D["gland_fill"] * 100:.0f}% fill',
                    xy=(g2, rg), xytext=(-4, 14), fontsize=8, color=INK,
                    arrowprops=dict(arrowstyle='->', color=INK, lw=0.7))
        ax.text(-18, -8, title, color=INK, fontsize=11, weight='bold')
        ax.set_aspect('equal')
        ax.set_xlim(-22, right + 34)
        ax.set_ylim(-12, ro + 24)
        ax.axhline(0, color='#888', lw=0.6, ls='-.')
        ax.text(-18, 1, 'hull axis', fontsize=7, color='#888')
        ax.axis('off')
    fig.savefig(os.path.join(OUT, 'end_cap_sections.png'))
    plt.close(fig)


if __name__ == '__main__':
    window_files()
    cap_profiles()
    if all(os.path.exists(os.path.join(HERE, 'renders', f'ortho_{v}.png')) for v in ('side', 'top', 'front')):
        general_arrangement()
    else:
        print('ortho renders not found - run build_sub.py --render first for the general arrangement')
    print('drawings written to', OUT)
