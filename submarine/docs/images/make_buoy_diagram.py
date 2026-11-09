#!/usr/bin/env python3
"""Draws relay_buoy_placement.png: where to put the acoustic/LoRa relay buoy."""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, FancyBboxPatch, Rectangle, Ellipse

HERE = os.path.dirname(os.path.abspath(__file__))
INK, WATER, DEEP, LAND = '#14365a', '#cfe8f7', '#9fcde9', '#e7efd9'
SOUND, RADIO, SUB, BAD = '#e67e22', '#8e44ad', '#e8590c', '#c0392b'

fig = plt.figure(figsize=(16, 10.5), dpi=150)
fig.suptitle('Where to put the relay buoy', fontsize=20, color=INK, x=0.03, ha='left', y=0.985, weight='bold')
fig.text(0.03, 0.935, 'The buoy sits in the middle of where the sub works. It hears the sub by sound underwater '
         'and passes everything to your laptop by LoRa radio. No boat, and nothing tied to the sub.',
         fontsize=11.5, color=INK)

# ---------------------------------------------------------------- top view
ax = fig.add_axes([0.02, 0.05, 0.58, 0.85])
ax.set_xlim(0, 600); ax.set_ylim(0, 430); ax.set_aspect('equal'); ax.axis('off')
ax.add_patch(Rectangle((0, 0), 600, 430, fc=LAND, ec='none'))
t = np.linspace(0, 2 * np.pi, 200)
r = 1 + 0.10 * np.sin(3 * t) + 0.06 * np.cos(5 * t + 1)
lake = np.c_[300 + 255 * r * np.cos(t), 220 + 170 * r * np.sin(t)]
ax.add_patch(Polygon(lake, fc=WATER, ec='#5b8fb9', lw=2))
r2 = 1 + 0.08 * np.sin(3 * t + 0.5)
ax.add_patch(Polygon(np.c_[320 + 140 * r2 * np.cos(t), 230 + 85 * r2 * np.sin(t)], fc=DEEP, ec='none', alpha=0.8))
ax.text(395, 290, 'deeper water\n(3-6 m)', color='#2c6e99', fontsize=9, ha='center', style='italic')
ax.set_title('TOP VIEW', loc='left', color=INK, fontsize=13, weight='bold')

bx, by = 300, 225                       # buoy
ax.add_patch(Circle((bx, by), 150, fc=SOUND, alpha=0.10, ec=SOUND, lw=2, ls='--'))
ax.text(bx + 105, by - 128, 'sound range\n~150 m', color=SOUND, fontsize=10, weight='bold', ha='center')
# mission
wps = [(215, 270), (360, 300), (395, 175), (250, 150)]
path = wps + [wps[0]]
ax.plot(*zip(*path), color=SUB, lw=1.6, ls=(0, (6, 4)))
for i, (x, y) in enumerate(wps, 1):
    ax.add_patch(Circle((x, y), 7, fc='white', ec=SUB, lw=2, zorder=3)); ax.text(x, y, str(i), ha='center', va='center', fontsize=8, color=SUB, weight='bold', zorder=4)
ax.annotate('Minnow\'s mission\n(stays inside the circle)', xy=(360, 300), xytext=(400, 360), fontsize=10, color=SUB,
            arrowprops=dict(arrowstyle='->', color=SUB))
ax.add_patch(Ellipse((330, 240), 26, 9, angle=20, fc=SUB, ec='k', lw=0.8))
# buoy
ax.add_patch(Circle((bx, by), 9, fc='#f1c40f', ec='k', lw=1.5)); ax.plot([bx], [by], 'k^', ms=6)
ax.annotate('RELAY BUOY\n(anchored)', xy=(bx - 6, by - 8), xytext=(225, 178), fontsize=11, color=INK, weight='bold',
            arrowprops=dict(arrowstyle='->', color=INK))
# shore station
lx, ly = 70, 228
ax.add_patch(FancyBboxPatch((lx - 22, ly - 12), 34, 22, boxstyle='round,pad=2', fc='white', ec=INK, lw=1.5))
ax.text(lx - 5, ly - 1, 'laptop', ha='center', va='center', fontsize=8, color=INK)
ax.text(lx - 5, ly - 30, 'YOU\n(on the bank)', ha='center', va='top', fontsize=10, color=INK, weight='bold')
ax.plot([lx + 16, bx - 10], [ly + 4, by + 2], color=RADIO, lw=2, ls=(0, (2, 3)))
ax.text(105, 244, 'LoRa radio (km range)', color=RADIO, fontsize=9.5)
ax.plot([lx + 16, bx - 9], [ly - 6, by - 6], color='#7f8c8d', lw=1.2)
ax.text(105, 206, 'pull-in line to the bank (optional)', color='#7f8c8d', fontsize=8.5)
# things to avoid
avoid = [((470, 330), 'weed bed'), ((515, 190), 'inflow /\nweir (noisy)'), ((330, 70), 'island'), ((140, 360), 'swimming /\nboats')]
for (x, y), label in avoid:
    ax.add_patch(Circle((x, y), 24, fc=BAD, alpha=0.15, ec=BAD, lw=1.5, ls=':'))
    ax.text(x, y, label, ha='center', va='center', fontsize=8.5, color=BAD)
ax.text(330, 70 - 40, 'avoid: they block or scramble the sound', color=BAD, fontsize=9, ha='center')
ax.plot([30, 130], [20, 20], color=INK, lw=3); ax.text(80, 26, '100 m', ha='center', color=INK, fontsize=9)

# ---------------------------------------------------------------- side view
ax = fig.add_axes([0.62, 0.42, 0.37, 0.49])
ax.set_xlim(0, 100); ax.set_ylim(-9, 4); ax.axis('off')
ax.set_title('SIDE VIEW (through the buoy)', loc='left', color=INK, fontsize=13, weight='bold')
xb = np.linspace(0, 100, 200)
bottom = -2 - 5.5 * np.sin(np.pi * np.clip(xb, 0, 100) / 100) ** 0.8
ax.fill_between(xb, bottom, 0, color=WATER)
ax.fill_between(xb, -9, bottom, color='#c8b48a')
ax.plot([0, 100], [0, 0], color='#5b8fb9', lw=2)
# buoy
X = 48
ax.add_patch(Rectangle((X - 2.2, -0.5), 4.4, 1.2, fc='#f1c40f', ec='k'))
ax.plot([X, X], [0.7, 3.2], color='k', lw=1.5); ax.plot([X], [3.2], 'ko', ms=4)
ax.text(X + 2, 3.1, 'LoRa antenna\n0.5 m up', fontsize=8.5, color=RADIO, va='top')
ax.text(X - 2.6, 1.3, 'float: ESP32,\nE220, battery', fontsize=8.5, color=INK, ha='right')
ax.plot([X, X], [-0.5, -1.8], color='k', lw=1); ax.add_patch(Rectangle((X - 0.6, -2.1), 1.2, 0.6, fc='#34495e'))
ax.annotate('hydrophone 1.5-2 m down\n(below waves, above weeds)', xy=(X + 0.6, -1.8), xytext=(60, -0.9),
            fontsize=8.5, color=SOUND, arrowprops=dict(arrowstyle='->', color=SOUND))
yb = float(np.interp(X + 6, xb, bottom))
ax.plot([X, X + 6], [-0.5, yb + 0.4], color='#555', lw=1)
ax.add_patch(Rectangle((X + 5, yb), 2.2, 0.8, fc='#7f8c8d', ec='k'))
ax.text(X + 8, yb + 0.2, 'anchor (brick)\nline = 2 x depth', fontsize=8.5, color=INK)
# sub + sound
sx, sy = 24, -2.2
ax.add_patch(Ellipse((sx, sy), 9, 0.6, fc=SUB, ec='k')); ax.text(sx, sy - 1.3, 'Minnow at 2 m', ha='center', fontsize=9, color=SUB)
for rr in (4, 8, 12):
    th = np.linspace(-0.35, 0.35, 30)
    ax.plot(sx + rr * np.cos(th), sy + 0.6 * rr * np.sin(th), color=SOUND, lw=1.5, alpha=0.9)
ax.text(25, -5.6, 'sound 20-40 kHz', color=SOUND, fontsize=9)
ax.text(2, -8.6, 'keep the buoy where it is at least 3 m deep, with clear water between it and the sub', fontsize=9, color=INK)

# ---------------------------------------------------------------- rules
ax = fig.add_axes([0.62, 0.05, 0.37, 0.33]); ax.axis('off')
rules = [
    ('Middle of the mission area', 'not the middle of the lake. Every waypoint within ~150 m.'),
    ('At least 20-30 m from the bank', 'banks echo the sound and bank noise drowns it.'),
    ('In water 3 m deep or more', 'hydrophone 1.5-2 m down, at least 1 m above the bottom.'),
    ('Clear "line of sound" to the sub', 'no islands, weed beds or underwater ridges in between.'),
    ('Away from noise', 'inflows, weirs, pumps, boat lanes.'),
    ('Can see your bank', 'LoRa reaches km over water, but keep line of sight.'),
    ('No boat needed to place it', 'wade out, throw from a jetty, or let Minnow tow it out.'),
]
for i, (h, d) in enumerate(rules):
    y = 0.95 - i * 0.135
    ax.text(0.0, y, f'{i + 1}.', fontsize=11, color=INK, weight='bold', va='top')
    ax.text(0.05, y, h, fontsize=11, color=INK, weight='bold', va='top')
    ax.text(0.05, y - 0.055, d, fontsize=9.5, color='#34495e', va='top')

fig.savefig(os.path.join(HERE, 'relay_buoy_placement.png'))
print('ok')
