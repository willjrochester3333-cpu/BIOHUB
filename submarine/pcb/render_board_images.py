#!/usr/bin/env python3
"""
render_board_images.py - realistic top/bottom images of the Minnow AUV main
board, composited from KiCad's own copper / solder-mask / silkscreen plots.

Run by generate_board.py (step 'outputs') with a Python that has cairosvg and
Pillow (python3.11 in this repo's tool setup):
    python3.11 render_board_images.py <board.kicad_pcb> <holes.json> <out_dir>

Writes board_top.png and board_bottom.png (16 px/mm, transparent outside the
board outline). The Blender model uses board_top.png as the PCB texture.
"""
import json
import os
import subprocess
import sys
import tempfile

import cairosvg
from PIL import Image, ImageChops, ImageDraw

PPM = 16                       # pixels per mm
OX, OY, W, H = 100.0, 100.0, 150.0, 60.0
PAGE_W, PAGE_H = 297.0, 210.0  # A4, the board file's page size

COL = dict(mask=(16, 72, 38), mask_cu=(34, 112, 58), pad=(214, 172, 84),
           silk=(238, 238, 228), hole=(22, 22, 24), edge=(12, 52, 28))


def layer_mask(pcb, layer, tmp):
    svg = os.path.join(tmp, f'{layer}.svg')
    subprocess.run(['kicad-cli', 'pcb', 'export', 'svg', '--layers', layer, '--black-and-white',
                    '--page-size-mode', '1', '--exclude-drawing-sheet', '--drill-shape-opt', '0',
                    '-o', svg, pcb], check=True, capture_output=True)
    png = os.path.join(tmp, f'{layer}.png')
    cairosvg.svg2png(url=svg, write_to=png, output_width=int(PAGE_W * PPM), output_height=int(PAGE_H * PPM))
    im = Image.open(png).convert('RGBA')
    box = tuple(int(round(v * PPM)) for v in (OX, OY, OX + W, OY + H))
    im = im.crop(box)
    # black ink on a transparent page -> use alpha (or darkness) as the mask
    r, g, b, a = im.split()
    dark = ImageChops.invert(im.convert('L'))
    return ImageChops.multiply(a, dark.point(lambda v: 255 if v > 60 else 0))


def outline_mask():
    m = Image.new('L', (int(W * PPM), int(H * PPM)), 0)
    c = 2.0
    pts = [(c, 0), (W - c, 0), (W, c), (W, H - c), (W - c, H), (c, H), (0, H - c), (0, c)]
    ImageDraw.Draw(m).polygon([(x * PPM, y * PPM) for x, y in pts], fill=255)
    return m


def compose(pcb, holes, side, tmp):
    pre = 'F' if side == 'top' else 'B'
    cu = layer_mask(pcb, f'{pre}.Cu', tmp)
    mask = layer_mask(pcb, f'{pre}.Mask', tmp)
    silk = layer_mask(pcb, f'{pre}.SilkS', tmp)
    size = cu.size
    img = Image.new('RGBA', size, COL['mask'] + (255,))
    img.paste(Image.new('RGBA', size, COL['mask_cu'] + (255,)), (0, 0), cu)
    pads = ImageChops.multiply(cu, mask)
    img.paste(Image.new('RGBA', size, COL['pad'] + (255,)), (0, 0), pads)
    silk_vis = ImageChops.subtract(silk, mask)
    img.paste(Image.new('RGBA', size, COL['silk'] + (255,)), (0, 0), silk_vis)
    d = ImageDraw.Draw(img)
    for x, y, r in holes:
        X, Y, R = (x - OX) * PPM, (y - OY) * PPM, r * PPM
        d.ellipse([X - R, Y - R, X + R, Y + R], fill=COL['hole'] + (255,))
    edge = outline_mask()
    img.putalpha(edge)
    if side == 'bottom':
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return img


def main():
    pcb, holes_json, out = sys.argv[1:4]
    holes = json.load(open(holes_json))
    os.makedirs(out, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for side in ('top', 'bottom'):
            img = compose(pcb, holes, side, tmp)
            img.save(os.path.join(out, f'board_{side}.png'))
            print('wrote', os.path.join(out, f'board_{side}.png'), img.size)


if __name__ == '__main__':
    main()
