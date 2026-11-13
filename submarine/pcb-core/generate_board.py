#!/usr/bin/env python3
"""
generate_board.py - builds the KiCad project for the Minnow CORE board (the
fully assembled, everything-on-one-board version) from design.py.

Steps (each can be run on its own):
  sch         write the schematic (minnow-core.kicad_sch)
  verify_sch  export the netlist from the schematic and compare it with design.py
  check       courtyard overlap / board-edge check of the placement
  route       pre-route the high-current copper, autoroute the rest with Freerouting
  widen       put necked-down supply tracks back to their class width
  stitch      ground stitching vias between the two ground pours
  drc         KiCad design-rule check
  outputs     Gerbers + drill (zip), JLCPCB assembly BOM + placement (CPL) files,
              schematic PDF/PNG, layout PDF, board images, placement.json

Needs KiCad 7+ (pcbnew Python module, kicad-cli), Java 25 + Freerouting 2.5 for 'route',
and a Python with cairosvg + Pillow for the images.
Usage: FREEROUTING_JAR=/path/freerouting.jar python3 generate_board.py all
"""
import csv
import json
import math
import os
import re
import subprocess
import sys
import uuid as uuidlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design as DZ  # noqa: E402

PROJECT = DZ.PROJECT
KSYM = '/usr/share/kicad/symbols'
KFP = '/usr/share/kicad/footprints'
OX, OY = 100.0, 100.0          # board origin in KiCad coordinates
FREEROUTING = os.environ.get('FREEROUTING_JAR', '')


def U():
    return str(uuidlib.uuid4())


def kx(bx):
    return OX + bx


def ky(by):
    return OY + by


# =============================================================================
# 2. PCB
# =============================================================================

def load_fp(fpid):
    import pcbnew
    lib, name = fpid.split(':')
    path = os.path.join(HERE, 'core.pretty') if lib == 'core' else os.path.join(KFP, f'{lib}.pretty')
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise RuntimeError(f'footprint not found: {fpid}')
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def sym_uuids():
    """Stable symbol UUIDs shared by the schematic and the PCB (footprint paths)."""
    p = os.path.join(HERE, 'uuids.json')
    data = json.load(open(p)) if os.path.exists(p) else {}
    changed = False
    for part in DZ.PARTS:
        if part['ref'] not in data:
            data[part['ref']] = U()
            changed = True
    if 'ROOT' not in data:
        data['ROOT'] = U()
        changed = True
    if changed:
        json.dump(data, open(p, 'w'), indent=1)
    return data


def build_pcb():
    import pcbnew
    F = pcbnew.FromMM
    V = lambda x, y: pcbnew.VECTOR2I(F(x), F(y))  # noqa: E731
    uu = sym_uuids()
    board = pcbnew.BOARD()
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.m_TrackMinWidth = F(0.15)
    ds.m_ViasMinSize = F(0.6)
    ds.m_MinThroughDrill = F(0.3)
    ds.m_CopperEdgeClearance = F(0.4)
    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetClearance(F(0.2))
    nc.SetTrackWidth(F(0.3))
    nc.SetViaDiameter(F(0.7))
    nc.SetViaDrill(F(0.35))
    # nets
    nets = {}

    def net(name):
        if name not in nets:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
            nets[name] = ni
        return nets[name]
    for part in DZ.PARTS:
        for n in part['pins'].values():
            if n:
                net(n)
    # outline (2 mm chamfered corners)
    W, H, c = DZ.BOARD_W, DZ.BOARD_H, 2.0
    pts = [(c, 0), (W - c, 0), (W, c), (W, H - c), (W - c, H), (c, H), (0, H - c), (0, c)]
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(kx(a[0]), ky(a[1])))
        s.SetEnd(V(kx(b[0]), ky(b[1])))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(F(0.1))
        board.Add(s)
    # footprints
    for part in DZ.PARTS:
        fp = load_fp(part['fp'])
        bx, by, rot = part['pcb']
        fp.SetReference(part['ref'])
        fp.SetValue(part['val'])
        fp.SetPosition(V(kx(bx), ky(by)))
        fp.SetOrientationDegrees(rot)
        fp.SetPath(pcbnew.KIID_PATH(f"/{uu[part['ref']]}"))
        board.Add(fp)
        for pad in fp.Pads():
            num = pad.GetNumber()
            if num in part['pins'] and part['pins'][num]:
                pad.SetNet(net(part['pins'][num]))
        # tidy silkscreen reference size
        ref = fp.Reference()
        ref.SetTextSize(V(0.8, 0.8))
        ref.SetTextThickness(F(0.15))
    return board, nets


def courtyard_boxes(board):
    import pcbnew
    boxes = {}
    for fp in board.GetFootprints():
        try:
            poly = fp.GetCourtyard(pcbnew.F_CrtYd)
            if poly.OutlineCount() == 0:
                raise ValueError
            bb = poly.BBox()
        except Exception:
            bb = fp.GetBoundingBox(False, False)
        boxes[fp.GetReference()] = (pcbnew.ToMM(bb.GetLeft()) - OX, pcbnew.ToMM(bb.GetTop()) - OY,
                                    pcbnew.ToMM(bb.GetRight()) - OX, pcbnew.ToMM(bb.GetBottom()) - OY)
    return boxes


def module_body(ref):
    """Real body of the ESP32 module (its footprint courtyard also covers the antenna keep-out)."""
    bx, by, _ = next(p for p in DZ.PARTS if p['ref'] == ref)['pcb']
    return (bx - 10.5, by - 9.25, bx + 15.5, by + 9.25)     # module outline + 0.25 mm courtyard margin


EDGE_OK = {'J3', 'J13'}        # USB sockets overhang the board edge on purpose


def step_check(board=None):
    if board is None:
        board, _ = build_pcb()
    import pcbnew
    board.BuildConnectivity()
    for fp in board.GetFootprints():
        fp.BuildCourtyardCaches()
    boxes = courtyard_boxes(board)
    boxes['U7'] = module_body('U7')
    ant = antenna_zone()
    probs = []
    refs = sorted(boxes)
    for i, a in enumerate(refs):
        ax0, ay0, ax1, ay1 = boxes[a]
        if ax0 < -0.01 or ay0 < -0.01 or ax1 > DZ.BOARD_W + 0.01 or ay1 > DZ.BOARD_H + 0.01:
            if a not in EDGE_OK:
                probs.append(f'{a} outside board: {tuple(round(v, 1) for v in boxes[a])}')
        if a != 'U7' and min(ax1, ant[2]) - max(ax0, ant[0]) > 0 and min(ay1, ant[3]) - max(ay0, ant[1]) > 0:
            probs.append(f'{a} is inside the ESP32 antenna keep-out')
        for b in refs[i + 1:]:
            bx0, by0, bx1, by1 = boxes[b]
            ox = min(ax1, bx1) - max(ax0, bx0)
            oy = min(ay1, by1) - max(ay0, by0)
            if ox > 0.05 and oy > 0.05:
                probs.append(f'{a} overlaps {b} by {ox:.1f} x {oy:.1f} mm')
    print(f'[check] {len(boxes)} footprints, {len(probs)} problems')
    for p in probs:
        print('   ', p)
    return probs


def antenna_zone():
    """The ESP32 footprint's own antenna keep-out, in board coordinates (bx0, by0, bx1, by1)."""
    bx, by, rot = next(p for p in DZ.PARTS if p['ref'] == 'U7')['pcb']
    assert rot == 270
    # footprint zone: x -24..24, y -30.74..-9.55; rotation 270 maps (x, y) -> (-y, x)
    return (bx + 9.55, by - 24.0, bx + 30.74, by + 24.0)


def add_keepout(board):
    """Board-level copy of the antenna keep-out, so the autorouter sees it too."""
    import pcbnew
    F = pcbnew.FromMM
    x0, y0, x1, y1 = antenna_zone()
    ka = pcbnew.ZONE(board)
    ka.SetIsRuleArea(True)
    ka.SetDoNotAllowCopperPour(True)
    ka.SetDoNotAllowTracks(True)
    ka.SetDoNotAllowVias(True)
    ka.SetDoNotAllowPads(False)
    ka.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.F_Cu)
    ls.AddLayer(pcbnew.B_Cu)
    ka.SetLayerSet(ls)
    ol = ka.Outline()
    ol.NewOutline()
    for x, y in ((x0, max(y0, -1.0)), (DZ.BOARD_W + 1, max(y0, -1.0)), (DZ.BOARD_W + 1, y1), (x0, y1)):
        ol.Append(F(kx(x)), F(ky(y)))
    board.Add(ka)


def add_zones_and_text(board, nets, keepout=True):
    import pcbnew
    F = pcbnew.FromMM
    V = lambda x, y: pcbnew.VECTOR2I(F(x), F(y))  # noqa: E731
    W, H = DZ.BOARD_W, DZ.BOARD_H
    # ground pours on both layers
    for layer in (pcbnew.B_Cu, pcbnew.F_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(nets['GND'])
        ol = z.Outline()
        ol.NewOutline()
        for x, y in ((0.3, 0.3), (W - 0.3, 0.3), (W - 0.3, H - 0.3), (0.3, H - 0.3)):
            ol.Append(F(kx(x)), F(ky(y)))
        z.SetMinThickness(F(0.25))
        z.SetLocalClearance(F(0.3))
        z.SetThermalReliefGap(F(0.4))
        z.SetThermalReliefSpokeWidth(F(0.5))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetAssignedPriority(0)
        board.Add(z)
    if keepout:
        add_keepout(board)
    hide_terminal_refs(board)
    add_silk(board)


def hide_terminal_refs(board):
    """The screw terminals get a label per screw instead of their reference text."""
    tb = {p['ref'] for p in DZ.PARTS if p['fp'].startswith('TerminalBlock')}
    for fp in board.GetFootprints():
        if fp.GetReference() in tb:
            fp.Reference().SetVisible(False)


def add_silk(board):
    """Board-level silkscreen: title, connector hints and the magnet marker."""
    import pcbnew
    F = pcbnew.FromMM
    V = lambda x, y: pcbnew.VECTOR2I(F(x), F(y))  # noqa: E731
    mx = DZ.MAGNET_SENSOR_BXBY[0]
    texts = [
        ('MINNOW CORE  rev ' + DZ.REV, 75.0, 27.0, 1.6, pcbnew.B_SilkS),
        ('ESP32 / BNO055 / BME280 / Ra-01H LoRa / TPS54302', 75.0, 30.0, 1.0, pcbnew.B_SilkS),
        ('assembled by JLCPCB - see submarine/pcb-core/README.md', 75.0, 32.4, 0.9, pcbnew.B_SilkS),
        ('github.com: BIOHUB/submarine', 75.0, 34.6, 0.9, pcbnew.B_SilkS),
        ('MAGNET SENSOR U2: hold the magnet on the hull here', 29.0, 1.4, 0.8, pcbnew.B_SilkS),
        ('BATTERY 3S', 9.0, 43.4, 0.9, pcbnew.F_SilkS),
        ('ESC POWER', 16.5, 58.4, 0.9, pcbnew.F_SilkS),
        ('MAGNET', mx, 13.25, 0.8, pcbnew.F_SilkS),
        ('CAMERA 5V', 130.0, 58.6, 0.9, pcbnew.F_SilkS),
        ('LORA ANT', 75.5, 35.6, 0.8, pcbnew.F_SilkS),
        ('BOOT', 105.0, 8.3, 0.8, pcbnew.F_SilkS),
        ('RESET', 114.0, 8.3, 0.8, pcbnew.F_SilkS),
    ]
    for txt, x, y, s, layer in texts:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(txt)
        t.SetPosition(V(kx(x), ky(y)))
        t.SetLayer(layer)
        t.SetTextSize(V(s, s))
        t.SetTextThickness(F(max(0.15, s * 0.15)))      # JLCPCB prints lines from 0.15 mm
        if layer == pcbnew.B_SilkS:
            t.SetMirrored(True)
        board.Add(t)
    # a label next to every screw of the screw terminals (their reference text would sit on top of it)
    for p in DZ.PARTS:
        if not p.get('labels'):
            continue
        ox, oy, rot = p['pcb']
        sgn = 1 if rot == 0 else -1           # rot 0: starboard edge, rot 180: port edge
        for k, lab in enumerate(p['labels']):
            t = pcbnew.PCB_TEXT(board)
            t.SetText(lab)
            t.SetPosition(V(kx(ox + sgn * 3.5 * k), ky(oy - sgn * 4.3)))
            t.SetLayer(pcbnew.F_SilkS)
            t.SetTextSize(V(0.8, 0.8))
            t.SetTextThickness(F(0.15))
            board.Add(t)
    # bottom-side arrow from the label to the board edge, right under the magnet sensor
    for x1, y1, x2, y2 in ((mx + 2.0, 1.4, mx, 1.4), (mx, 1.4, mx + 0.9, 0.8), (mx, 1.4, mx + 0.9, 2.0)):
        sh = pcbnew.PCB_SHAPE(board)
        sh.SetShape(pcbnew.SHAPE_T_SEGMENT)
        sh.SetStart(V(kx(x1), ky(y1)))
        sh.SetEnd(V(kx(x2), ky(y2)))
        sh.SetLayer(pcbnew.B_SilkS)
        sh.SetWidth(F(0.2))
        board.Add(sh)


def step_relabel():
    """Re-draw the board-level silkscreen on the routed board (no re-routing)."""
    import pcbnew
    path = os.path.join(HERE, f'{PROJECT}.kicad_pcb')
    board = pcbnew.LoadBoard(path)
    hide_terminal_refs(board)
    for d in list(board.GetDrawings()):
        if d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            board.Remove(d)
    add_silk(board)
    board.Save(path)
    print('[relabel] silkscreen redrawn')


def step_pcb(save=True):
    import pcbnew
    board, nets = build_pcb()
    add_zones_and_text(board, nets)
    path = os.path.join(HERE, f'{PROJECT}.kicad_pcb')
    if save:
        board.Save(path)
        print(f'[pcb] {len(list(board.GetFootprints()))} footprints, {len(nets)} nets -> {path}')
    return board




# =============================================================================
# 3. SCHEMATIC
# =============================================================================
GRID = 1.27


def snap(v):
    return round(round(v / GRID) * GRID, 4)


def _scan_block(text, start):
    """Return the balanced '( ... )' block starting at text[start] == '('."""
    depth, i, n, ins = 0, start, len(text), False
    while i < n:
        ch = text[i]
        if ins:
            if ch == '\\':
                i += 2
                continue
            if ch == '"':
                ins = False
        elif ch == '"':
            ins = True
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    raise ValueError('unbalanced block')


def _top_symbol(text, name):
    key = f'\n  (symbol "{name}"'
    i = text.find(key)
    if i < 0:
        raise KeyError(name)
    return _scan_block(text, i + 3)


def sexp(text):
    toks = re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+', text)
    st = [[]]
    for t in toks:
        if t == '(':
            st.append([])
        elif t == ')':
            x = st.pop()
            st[-1].append(x)
        else:
            st[-1].append(t)
    return st[0][0]


def _unq(s):
    return s[1:-1] if s.startswith('"') else s


_LIBCACHE = {}


def lib_symbol(lib_id):
    """(embedded_text, pins) for a library symbol, with 'extends' flattened."""
    if lib_id in _LIBCACHE:
        return _LIBCACHE[lib_id]
    lib, name = lib_id.split(':')
    path = os.path.join(HERE, 'auv.kicad_sym') if lib == 'auv' else os.path.join(KSYM, f'{lib}.kicad_sym')
    text = open(path).read()
    blk = _top_symbol(text, name)
    m = re.search(r'\(extends "([^"]+)"\)', blk)
    if m:
        parent = m.group(1)
        pblk = _top_symbol(text, parent)
        child_props = dict(re.findall(r'\(property "([^"]+)" ("(?:\\.|[^"\\])*")', blk))
        out = pblk.replace(f'(symbol "{parent}"', f'(symbol "{name}"', 1)
        out = out.replace(f'(symbol "{parent}_', f'(symbol "{name}_')

        def fix_prop(mm):
            key = mm.group(1)
            if key in child_props:
                return f'(property "{key}" {child_props[key]}'
            return mm.group(0)
        out = re.sub(r'\(property "([^"]+)" ("(?:\\.|[^"\\])*")', fix_prop, out)
        blk = out
    emb = blk.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)
    tree = sexp(blk)
    pins = []

    def walk(node, unit=0, conv=0):
        if not isinstance(node, list) or not node:
            return
        if node[0] == 'symbol' and len(node) > 1:
            mm = re.match(r'.*_(\d+)_(\d+)$', _unq(node[1]))
            if mm:
                unit, conv = int(mm.group(1)), int(mm.group(2))
        if node[0] == 'pin':
            at = next(x for x in node if isinstance(x, list) and x[0] == 'at')
            ln = next((x for x in node if isinstance(x, list) and x[0] == 'length'), ['length', '0'])
            num = next(x for x in node if isinstance(x, list) and x[0] == 'number')
            nm = next(x for x in node if isinstance(x, list) and x[0] == 'name')
            if unit in (0, 1) and conv in (0, 1):
                pins.append(dict(num=_unq(num[1]), name=_unq(nm[1]), x=float(at[1]), y=float(at[2]),
                                 rot=int(float(at[3])) if len(at) > 3 else 0, length=float(ln[1])))
            return
        for ch in node[1:]:
            walk(ch, unit, conv)
    walk(tree)
    _LIBCACHE[lib_id] = (emb, pins)
    return emb, pins


OUTWARD = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}   # schematic coords (y down)


def _label_len(net):
    return 1.15 * len(net) + 2.0


def sym_extent(pins, nets):
    """Bounding box (schematic offsets from the symbol origin) incl. labels."""
    xs, ys = [-2.54, 2.54], [-2.54, 2.54]
    for p in pins:
        px, py = p['x'], -p['y']
        dx, dy = OUTWARD[p['rot'] % 360]
        net = nets.get(p['num'])
        L = 2.54 + (_label_len(net) if net else 1.27)
        xs += [px, px + dx * L]
        ys += [py, py + dy * L]
        # inner end of the pin (towards the body)
        xs.append(px - dx * p['length'])
        ys.append(py - dy * p['length'])
    return min(xs), min(ys), max(xs), max(ys)


def step_sch():
    uu = sym_uuids()
    root = uu['ROOT']
    parts = [p for p in DZ.PARTS]
    flags = [('GND', '#FLG01'), ('VSYS', '#FLG02'), ('+5V', '#FLG03'), ('LDO_IN', '#FLG04'),
             ('VAON_IN', '#FLG05'), ('USB_VBUS', '#FLG06')]
    lib_ids = sorted({p['sym'] for p in parts} | {'power:PWR_FLAG'})
    items = []          # schematic body lines
    # --- layout: blocks in columns
    order = ['power', 'buck', 'outputs', 'usb', 'mcu', 'lora', 'esc', 'sensors', 'camera', 'misc']
    col_w = 176.0
    margin_x, margin_y = 20.0, 22.0
    cols = [[], [], []]
    col_assign = {'power': 0, 'buck': 0, 'outputs': 0, 'usb': 1, 'mcu': 1, 'lora': 1, 'esc': 1, 'sensors': 2,
                  'camera': 2, 'misc': 2}
    placed = []
    block_rects = []
    col_y = [margin_y, margin_y, margin_y]
    for blk in order:
        c = col_assign[blk]
        bx0 = margin_x + c * (col_w + 12.0)
        by0 = col_y[c]
        x, y, row_h = bx0 + 4.0, by0 + 10.0, 0.0
        members = [p for p in parts if p['blk'] == blk]
        if blk == 'power':
            members = members + [dict(ref=f, sym='power:PWR_FLAG', val='PWR_FLAG', fp='', pins={'1': n},
                                      flag=True) for n, f in flags]
        for p in members:
            _, pins = lib_symbol(p['sym'])
            nets = {k: (v if v else None) for k, v in p['pins'].items()}
            x0, y0, x1, y1 = sym_extent(pins, nets)
            x1 = max(x1, 0.95 * len(p.get('val', '')) + 1.0)     # room for the value text
            for r in re.finditer(r'\(rectangle \(start ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\)',
                                 lib_symbol(p['sym'])[0]):      # and for the symbol body itself
                ax, ay, bx_, by_ = (float(v) for v in r.groups())
                x0, x1 = min(x0, ax - 1.0, bx_ - 1.0), max(x1, ax + 1.0, bx_ + 1.0)
                y0, y1 = min(y0, -ay - 1.0, -by_ - 1.0), max(y1, -ay + 1.0, -by_ + 1.0)
            w, h = x1 - x0 + 4.0, y1 - y0 + 7.0
            if x + w > bx0 + col_w and x > bx0 + 4.0:
                x = bx0 + 4.0
                y += row_h
                row_h = 0.0
            ox, oy = snap(x - x0), snap(y - y0 + 3.0)
            placed.append((p, ox, oy, pins, (x0, y0, x1, y1)))
            x += w
            row_h = max(row_h, h)
        bh = (y + row_h) - by0 + 2.0
        block_rects.append((blk, bx0, by0, bx0 + col_w, by0 + bh))
        col_y[c] = by0 + bh + 8.0
    sheet_w = margin_x * 2 + 3 * col_w + 24.0
    sheet_h = max(col_y) + 25.0
    paper = 'A2' if sheet_w <= 594 and sheet_h <= 420 else 'A1'
    # --- emit symbols, wires, labels
    for p, ox, oy, pins, ext in placed:
        is_flag = p.get('flag', False)
        su = uu.get(p['ref'], U()) if not is_flag else U()
        x0, y0, x1, y1 = ext
        side_pins = {OUTWARD[q['rot'] % 360] for q in pins}
        if side_pins <= {(0, 1), (0, -1)}:          # vertical 2-pin parts: text to the right
            rpos, vpos, just = (ox + 2.54, oy - 1.27), (ox + 2.54, oy + 1.27), 'left'
        else:
            rpos, vpos, just = (ox, oy + y0 + 4.0 - 1.27), (ox, oy + y1 - 3.5), 'left'
        hide_rv = ' hide' if is_flag else ''
        props = [
            ('Reference', p['ref'], rpos, hide_rv),
            ('Value', p['val'], vpos, ''),
            ('Footprint', p.get('fp', ''), (ox, oy), ' hide'),
            ('Datasheet', '~', (ox, oy), ' hide'),
        ]
        if not is_flag:
            props.append(('MPN', p.get('mpn', ''), (ox, oy), ' hide'))
        lines = [f'  (symbol (lib_id "{p["sym"]}") (at {ox} {oy} 0) (unit 1)',
                 f'    (in_bom {"no" if is_flag else "yes"}) (on_board {"no" if is_flag else "yes"}) (dnp no)',
                 f'    (uuid "{su}")']
        for k, v, (px, py), h in props:
            v = v.replace('"', "'")
            lines.append(f'    (property "{k}" "{v}" (at {snap(px)} {snap(py)} 0)'
                         f' (effects (font (size 1.27 1.27)) (justify {just}){h}))')
        for q in pins:
            lines.append(f'    (pin "{q["num"]}" (uuid "{U()}"))')
        lines.append(f'    (instances (project "{PROJECT}" (path "/{root}" (reference "{p["ref"]}") (unit 1))))')
        lines.append('  )')
        items += lines
        for q in pins:
            net = p['pins'].get(q['num'])
            px, py = snap(ox + q['x']), snap(oy - q['y'])
            dx, dy = OUTWARD[q['rot'] % 360]
            if not net:
                if q['num'] in p['pins']:
                    items.append(f'  (no_connect (at {px} {py}) (uuid "{U()}"))')
                continue
            qx, qy = snap(px + dx * 2.54), snap(py + dy * 2.54)
            items.append(f'  (wire (pts (xy {px} {py}) (xy {qx} {qy})) (stroke (width 0) (type default)) (uuid "{U()}"))')
            ang = {(-1, 0): 180, (1, 0): 0, (0, 1): 270, (0, -1): 90}[(dx, dy)]
            jst = 'right bottom' if ang in (180, 270) else 'left bottom'
            items.append(f'  (label "{net}" (at {qx} {qy} {ang}) (fields_autoplaced)'
                         f' (effects (font (size 1.27 1.27)) (justify {jst})) (uuid "{U()}"))')
    for blk, x0, y0, x1, y1 in block_rects:
        items.append(f'  (rectangle (start {snap(x0)} {snap(y0)}) (end {snap(x1)} {snap(y1)})'
                     f' (stroke (width 0.254) (type dash)) (fill (type none)) (uuid "{U()}"))')
        items.append(f'  (text "{DZ.BLOCK_TITLES[blk]}" (at {snap(x0 + 2)} {snap(y0 + 5)} 0)'
                     f' (effects (font (size 2.2 2.2) (thickness 0.44) bold) (justify left bottom)) (uuid "{U()}"))')
    notes = [
        'Generated from design.py by generate_board.py - edit design.py, not this file.',
        'Magnet power switch: a magnet near U2 (SM351LT, always powered by U1, 3 uA) pulls HALL_OUT low -> Q4 drives',
        'LATCH_G high -> Q3 pulls the P-FET gates low -> the ESP32 boots and drives PWR_HOLD (GPIO32) high to stay on.',
        'Shutdown = the firmware releases PWR_HOLD once the magnet is taken away. MAG_SENSE (GPIO15) reads the magnet.',
        'USB-C powers only the 3.3 V side (D5): the shore-station board needs nothing but a USB cable.',
        'All analog inputs are on ADC1 (GPIO34/35/36/39), which keeps working while Wi-Fi talks to the camera.',
    ]
    for i, t in enumerate(notes):
        items.append(f'  (text "{t}" (at {snap(margin_x)} {snap(sheet_h - 20 + i * 3.2)} 0)'
                     f' (effects (font (size 1.6 1.6)) (justify left bottom)) (uuid "{U()}"))')
    libs = '\n'.join('    ' + lib_symbol(l)[0].replace('\n', '\n    ') for l in lib_ids)
    head = [f'(kicad_sch (version 20230121) (generator eeschema)', '',
            f'  (uuid {root})', '',
            f'  (paper "{paper}")', '',
            '  (title_block',
            f'    (title "{DZ.TITLE}")',
            '    (date "2026-11-11")',
            f'    (rev "{DZ.REV}")',
            '    (company "BIOHUB / submarine")',
            '    (comment 1 "All-in-one, JLCPCB-assembled: ESP32, USB-C, magnet power latch, 5V/3.3V, IMU, hull sensor, LoRa, camera port")',
            '    (comment 2 "Single sheet. Nets are connected by name (labels).")',
            '  )', '',
            '  (lib_symbols', libs, '  )', '']
    tail = ['', '  (sheet_instances', '    (path "/" (page "1"))', '  )', ')']
    path = os.path.join(HERE, f'{PROJECT}.kicad_sch')
    open(path, 'w').write('\n'.join(head + items + tail) + '\n')
    print(f'[sch] {len(placed)} symbols on {paper} ({sheet_w:.0f} x {sheet_h:.0f} mm needed) -> {path}')


def step_verify_sch():
    """Export the netlist from the schematic with kicad-cli and compare it with design.py."""
    out = os.path.join(HERE, 'build', 'schematic.net')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', out,
                    os.path.join(HERE, f'{PROJECT}.kicad_sch')], check=True, capture_output=True)
    tree = sexp(open(out).read())
    nets_sec = next(x for x in tree if isinstance(x, list) and x[0] == 'nets')
    got = {}
    for n in nets_sec[1:]:
        name = _unq(next(x for x in n if isinstance(x, list) and x[0] == 'name')[1])
        nodes = set()
        for x in n:
            if isinstance(x, list) and x[0] == 'node':
                ref = _unq(next(y for y in x if isinstance(y, list) and y[0] == 'ref')[1])
                pin = _unq(next(y for y in x if isinstance(y, list) and y[0] == 'pin')[1])
                nodes.add((ref, pin))
        got[name.lstrip('/')] = nodes
    want = {}
    for p in DZ.PARTS:
        for pin, net in p['pins'].items():
            if net:
                want.setdefault(net, set()).add((p['ref'], pin))
    bad = []
    for net, nodes in want.items():
        if got.get(net) != nodes:
            bad.append((net, sorted(nodes ^ got.get(net, set()))))
    extra = [n for n in got if n not in want and not n.startswith('unconnected') and not n.startswith('Net-(')]
    print(f'[verify] schematic netlist: {len(got)} nets; design: {len(want)} nets; mismatches: {len(bad)}; extra: {extra}')
    for b in bad[:20]:
        print('   ', b)
    return not bad


# =============================================================================
# 4. PROJECT FILE, PRE-ROUTES, AUTOROUTING
# =============================================================================

def write_project():
    classes = []
    patterns = []
    for name, c in DZ.NETCLASSES.items():
        classes.append({
            'name': name, 'clearance': c['clearance'], 'track_width': c['width'],
            'via_diameter': c['via_d'], 'via_drill': c['via_drill'],
            'microvia_diameter': 0.3, 'microvia_drill': 0.1, 'diff_pair_gap': 0.25,
            'diff_pair_via_gap': 0.25, 'diff_pair_width': 0.2, 'line_style': 0, 'bus_width': 12,
            'wire_width': 6, 'pcb_color': 'rgba(0, 0, 0, 0.000)', 'schematic_color': 'rgba(0, 0, 0, 0.000)'})
        for n in c['nets']:
            patterns.append({'netclass': name, 'pattern': n})
    pro = {
        'board': {'design_settings': {
            'defaults': {'board_outline_line_width': 0.1, 'copper_line_width': 0.2, 'copper_text_size_h': 1.5,
                         'copper_text_size_v': 1.5, 'copper_text_thickness': 0.3, 'silk_line_width': 0.12,
                         'silk_text_size_h': 1.0, 'silk_text_size_v': 1.0, 'silk_text_thickness': 0.15},
            'rules': {'min_clearance': 0.15, 'min_copper_edge_clearance': 0.4, 'min_hole_clearance': 0.25,
                      'min_hole_to_hole': 0.25, 'min_through_hole_diameter': 0.3, 'min_track_width': 0.15,
                      'min_via_annular_width': 0.1, 'min_via_diameter': 0.6, 'min_silk_clearance': 0.0,
                      'solder_mask_to_copper_clearance': 0.0, 'use_height_for_length_calcs': True},
            'track_widths': [0.0, 0.3, 0.5, 0.6, 0.8, 1.2, 1.5, 2.0, 2.5, 3.0],
            'via_dimensions': [{'diameter': 0.0, 'drill': 0.0}, {'diameter': 0.7, 'drill': 0.35},
                               {'diameter': 0.9, 'drill': 0.45}, {'diameter': 1.2, 'drill': 0.6}],
            # the footprint-vs-library check needs KiCad's global library table, which a
            # fresh KiCad install has; it is silenced so CI-style DRC runs stay clean
            'rule_severities': {'lib_footprint_issues': 'ignore', 'lib_footprint_mismatch': 'ignore'},
        }},
        'net_settings': {'classes': classes, 'meta': {'version': 3}, 'netclass_patterns': patterns},
        'meta': {'filename': f'{PROJECT}.kicad_pro', 'version': 1},
        'pcbnew': {'last_paths': {}},
        'schematic': {'legacy_lib_dir': '', 'legacy_lib_list': []},
        'sheets': [[sym_uuids()['ROOT'], '']],
        'text_variables': {},
    }
    json.dump(pro, open(os.path.join(HERE, f'{PROJECT}.kicad_pro'), 'w'), indent=2)
    open(os.path.join(HERE, f'{PROJECT}.kicad_dru'), 'w').write(
        '(version 1)\n'
        '# Small connector pins next to the board edge only fit one thermal spoke on F.Cu;\n'
        '# they are also connected to the B.Cu ground pour.\n'
        '(rule "one spoke is enough"\n  (constraint min_resolved_spokes 1))\n')


def pad_xy(board, ref, num, largest=False):
    import pcbnew
    fp = board.FindFootprintByReference(ref)
    pads = [p for p in fp.Pads() if p.GetNumber() == num]
    if largest:
        pads.sort(key=lambda p: -p.GetSize().x * p.GetSize().y)
    pos = pads[0].GetPosition()
    return pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y)


def add_track(board, net, pts, width, layer='F.Cu', locked=True):
    import pcbnew
    F = pcbnew.FromMM
    lay = pcbnew.F_Cu if layer == 'F.Cu' else pcbnew.B_Cu
    ni = board.FindNet(net)
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(F(x1), F(y1)))
        t.SetEnd(pcbnew.VECTOR2I(F(x2), F(y2)))
        t.SetWidth(F(width))
        t.SetLayer(lay)
        t.SetNet(ni)
        t.SetLocked(locked)
        board.Add(t)


def add_via(board, net, x, y, dia=0.8, drill=0.4, locked=True):
    import pcbnew
    F = pcbnew.FromMM
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(F(x), F(y)))
    v.SetWidth(F(dia))
    v.SetDrill(F(drill))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(board.FindNet(net))
    v.SetLocked(locked)
    board.Add(v)


def pre_route(board):
    """Hand-placed wide copper for the high-current paths (board mm + KiCad offset)."""
    P = lambda r, n, big=False: pad_xy(board, r, n, big)  # noqa: E731
    K = lambda x, y: (OX + x, OY + y)  # noqa: E731
    j1v, f1a, f1b = P('J1', '2'), P('F1', '1'), P('F1', '2')
    q1s, q2s = P('Q1', '3'), P('Q2', '3')
    q1t, q2t = P('Q1', '2', True), P('Q2', '2', True)
    # battery + -> fuse -> both FET sources
    add_track(board, 'VBAT_IN', [j1v, f1a], 2.5)
    xm = OX + 29.0
    add_track(board, 'VBAT_F', [f1b, (xm, f1b[1]), q2s], 2.5)
    add_track(board, 'VBAT_F', [(xm, f1b[1]), (xm, q1s[1]), q1s], 2.0)
    # switched battery (VSYS): both FET tabs -> trunk -> TVS + bulk caps -> ESC socket
    xt = OX + 40.5
    add_track(board, 'VSYS', [q1t, (xt, q1t[1]), (xt, q2t[1]), q2t], 3.0)
    add_track(board, 'VSYS', [(xt, q2t[1]), K(40.5, 46.5), K(12.0, 46.5), P('J2', '2')], 2.5)
    for ref in ('D3', 'C5', 'C6'):
        tx, ty = P(ref, '1')
        add_track(board, 'VSYS', [(xt, ty), (tx, ty)], 2.0)
    r8 = P('R8', '1')                          # battery-voltage divider, next to the trunk
    add_track(board, 'VSYS', [r8, (r8[0], OY + 33.4), (xt, OY + 33.4)], 0.6)
    # ESC / battery return on the bottom layer
    add_track(board, 'GND', [P('J1', '1'), K(17.5, 43.0), K(13.0, 47.5), K(13.0, 55.0), P('J2', '1')], 3.0,
              layer='B.Cu')
    # buck switch node: narrow between the regulator pins, then wide to the inductor
    sw, l1a = P('U3', '2'), P('L1', '1')
    add_track(board, 'BUCK_SW', [sw, (sw[0], sw[1] + 1.46)], 0.6)
    add_track(board, 'BUCK_SW', [(sw[0], sw[1] + 1.46), l1a], 1.2)
    # LoRa antenna: short, wide, straight
    add_track(board, 'LORA_ANT', [P('J4', '1'), P('U8', '1')], 0.8)


def add_zones(board):
    nets = {n: board.FindNet(n) for n in ('GND',)}
    add_zones_and_text(board, nets, keepout=False)


def patch_dsn(path):
    txt = open(path).read()
    # via padstacks for every class
    vias = {}
    for name, c in DZ.NETCLASSES.items():
        vname = f"Via[0-1]_{int(c['via_d'] * 1000)}:{int(c['via_drill'] * 1000)}_um"
        vias[name] = vname
    lib_add = ''
    for name, vname in vias.items():
        if f'(padstack "{vname}"' in txt:
            continue
        d = int(DZ.NETCLASSES[name]['via_d'] * 1000)
        lib_add += (f'    (padstack "{vname}"\n      (shape (circle F.Cu {d}))\n'
                    f'      (shape (circle B.Cu {d}))\n      (attach off)\n    )\n')
    txt = txt.replace('  (library\n', '  (library\n' + lib_add, 1)
    txt = re.sub(r'    \(via "Via\[0-1\]_700:350_um"\)', '    (via ' + ' '.join(f'"{v}"' for v in sorted(set(vias.values()))) + ')', txt, count=1)
    # replace the default class with ours
    i = txt.index('    (class kicad_default')
    j = i + len(_scan_block(txt, i + 4)) + 4
    all_nets = set()
    for p in DZ.PARTS:
        all_nets |= {n for n in p['pins'].values() if n}
    assigned = set()
    blocks = []
    for name, c in DZ.NETCLASSES.items():
        members = [n for n in c['nets'] if n in all_nets] if name != 'Default' else \
            sorted(all_nets - {n for cc in DZ.NETCLASSES.values() for n in cc['nets']})
        assigned |= set(members)
        if not members:
            continue
        q = lambda n: f'"{n}"' if re.search(r'[^A-Za-z0-9_]', n) else n  # noqa: E731
        blocks.append(f'    (class {name} {" ".join(q(n) for n in members)}\n'
                      f'      (circuit\n        (use_via "{vias[name]}")\n      )\n'
                      f'      (rule\n        (width {int(c["width"] * 1000)})\n'
                      f'        (clearance {c["clearance"] * 1000 + 20:.1f})\n      )\n    )')
    txt = txt[:i] + '\n'.join(blocks) + txt[j:]
    W, H, c, d = DZ.BOARD_W, DZ.BOARD_H, 2.0, 0.35
    ins = [(c, d), (W - c, d), (W - d, c), (W - d, H - c), (W - c, H - d), (c, H - d), (d, H - c), (d, c), (c, d)]
    path_pts = '  '.join(f'{(OX + x) * 1000:.0f} {-(OY + y) * 1000:.0f}' for x, y in ins)
    txt = re.sub(r'\(boundary\s*\(path pcb 0[^)]*\)\s*\)', f'(boundary\n      (path pcb 0  {path_pts})\n    )', txt, count=1)
    open(path, 'w').write(txt)


def parse_ses(path):
    tree = sexp(open(path).read())

    def find(node, key):
        for x in node:
            if isinstance(x, list) and x and x[0] == key:
                yield x
    routes = next(find(tree, 'routes'))
    res = next(find(routes, 'resolution'))
    scale = float(res[2])                      # units per micrometre
    net_out = next(find(routes, 'network_out'))
    wires, vias = [], []
    for net in find(net_out, 'net'):
        name = _unq(net[1])
        for w in find(net, 'wire'):
            pth = next(find(w, 'path'))
            layer, width = _unq(pth[1]), float(pth[2]) / scale / 1000.0
            coords = [float(v) / scale / 1000.0 for v in pth[3:] if not isinstance(v, list)]
            pts = [(coords[k], -coords[k + 1]) for k in range(0, len(coords) - 1, 2)]
            wires.append((name, layer, width, pts))
        for v in find(net, 'via'):
            pad = _unq(v[1])
            x, y = float(v[2]) / scale / 1000.0, -float(v[3]) / scale / 1000.0
            m = re.search(r'_(\d+):(\d+)_um', pad)
            dia, drill = (int(m.group(1)) / 1000.0, int(m.group(2)) / 1000.0) if m else (0.8, 0.4)
            vias.append((name, x, y, dia, drill))
    return wires, vias


def java25():
    for c in ('/usr/lib/jvm/java-25-openjdk-amd64/bin/java', 'java'):
        if c == 'java' or os.path.exists(c):
            return c


def step_route(passes=60):
    import pcbnew
    write_project()
    board, nets = build_pcb()
    add_keepout(board)          # the router must see the antenna keep-out
    pre_route(board)
    build = os.path.join(HERE, 'build')
    os.makedirs(build, exist_ok=True)
    tmp = os.path.join(build, 'preroute.kicad_pcb')
    board.SetFileName(tmp)
    dsn = os.path.join(build, f'{PROJECT}.dsn')
    ses = os.path.join(build, f'{PROJECT}.ses')
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        raise RuntimeError('DSN export failed')
    patch_dsn(dsn)
    jar = FREEROUTING or os.path.join(os.path.dirname(HERE), '..', 'tools', 'freerouting-2.5.0-executable.jar')
    if os.path.exists(ses):
        os.remove(ses)
    cmd = [java25(), '-jar', jar, '-de', dsn, '-do', ses, '-mp', str(passes), '-mt', '3',
           '--gui.enabled=false', '--usage_and_diagnostic_data.disable_analytics=true']
    print('[route] running Freerouting ...', flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    log = (r.stdout or '') + (r.stderr or '')
    open(os.path.join(build, 'freerouting.log'), 'w').write(log)
    if not os.path.exists(ses):
        print(log[-3000:])
        raise RuntimeError('Freerouting produced no session file')
    wires, vias = parse_ses(ses)
    # the session only holds the NEW wires; the locked pre-routes stay on the board
    for name, layer, width, pts in wires:
        # Freerouting necks tracks down at small pads; keep everything >= 0.15 mm for the fab
        add_track(board, name, pts, max(width, 0.15), layer, locked=False)
    for name, x, y, dia, drill in vias:
        add_via(board, name, x, y, dia, drill, locked=False)
    path = os.path.join(HERE, f'{PROJECT}.kicad_pcb')
    board.Save(path)
    # saving a board that was built in memory also rewrites the .kicad_pro without our
    # net classes, so write the project again before re-loading (DRC needs the classes)
    write_project()
    # zones are added and filled on a board re-loaded from disk (filling an
    # in-memory board crashes KiCad 7's python bindings)
    board = pcbnew.LoadBoard(path)
    add_zones(board)
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)
    print(f'[route] {len(wires)} wires, {len(vias)} vias imported -> {path}')
    unrouted = [ln for ln in log.splitlines() if 'unrouted' in ln.lower() or 'incomplete' in ln.lower()]
    for ln in unrouted[-5:]:
        print('   ', ln.strip()[:200])


def step_widen():
    """Freerouting necks tracks down to squeeze through gaps; put the supply nets back to their
    class width (the DRC step afterwards confirms everything still fits)."""
    import pcbnew
    path = os.path.join(HERE, f'{PROJECT}.kicad_pcb')
    board = pcbnew.LoadBoard(path)
    # only the 'Supply' class: the 2-3 mm battery path is pre-routed, and its thin
    # branches to small resistors and capacitors are meant to stay thin
    want = {n: DZ.NETCLASSES['Supply']['width'] for n in DZ.NETCLASSES['Supply']['nets']}
    n = 0
    for t in board.GetTracks():
        if t.GetClass() != 'PCB_VIA' and t.GetNetname() in want and \
                pcbnew.ToMM(t.GetWidth()) < want[t.GetNetname()] - 0.01:
            t.SetWidth(pcbnew.FromMM(want[t.GetNetname()]))
            n += 1
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)
    print(f'[widen] {n} supply track segments set back to their class width')


def step_stitch(pitch=4.0, via_d=0.7, via_drill=0.35):
    """Ground stitching vias in open areas, so the top and bottom ground pours are tied together
    and small bottom-layer islands stay connected (better return paths and shielding)."""
    import pcbnew
    path = os.path.join(HERE, f'{PROJECT}.kicad_pcb')
    board = pcbnew.LoadBoard(path)
    T, F = pcbnew.ToMM, pcbnew.FromMM
    vr, clr = via_d / 2, 0.3        # running it again adds nothing: new vias keep clear of existing ones
    segs, vias = [], []
    for t in board.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            vias.append((T(t.GetPosition().x), T(t.GetPosition().y), T(t.GetWidth()) / 2))
        else:
            segs.append((T(t.GetStart().x), T(t.GetStart().y), T(t.GetEnd().x), T(t.GetEnd().y),
                         T(t.GetWidth()) / 2, t.GetNetname() == 'GND'))
    boxes = []
    for fp in board.GetFootprints():
        fp.BuildCourtyardCaches()
        poly = fp.GetCourtyard(pcbnew.F_CrtYd)
        bb = poly.BBox() if poly.OutlineCount() else fp.GetBoundingBox(False, False)
        if fp.GetReference() == 'U7':
            x0, y0, x1, y1 = module_body('U7')
            boxes.append((OX + x0, OY + y0, OX + x1, OY + y1))
        else:
            boxes.append((T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom())))
        for pad in fp.Pads():
            pb = pad.GetBoundingBox()
            boxes.append((T(pb.GetLeft()) - 0.1, T(pb.GetTop()) - 0.1, T(pb.GetRight()) + 0.1, T(pb.GetBottom()) + 0.1))
    ax0, ay0, ax1, ay1 = antenna_zone()

    def seg_dist(px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        L = dx * dx + dy * dy
        u = 0.0 if L == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L))
        return math.hypot(px - (x1 + u * dx), py - (y1 + u * dy))
    added = 0
    y = 2.5
    while y <= DZ.BOARD_H - 2.5 + 1e-6:
        x = 2.5
        while x <= DZ.BOARD_W - 2.5 + 1e-6:
            px, py = OX + x, OY + y
            ok = not (ax0 - 1.0 <= x <= ax1 and ay0 - 1.0 <= y <= ay1 + 1.0)
            ok = ok and all(math.hypot(x - hx, y - hy) > 4.5 for hx, hy in
                            ((p['pcb'][0], p['pcb'][1]) for p in DZ.PARTS if p['ref'].startswith('H')))
            ok = ok and not any(b0 - vr - clr <= px <= b2 + vr + clr and b1 - vr - clr <= py <= b3 + vr + clr
                                for b0, b1, b2, b3 in boxes)
            ok = ok and all(seg_dist(px, py, x1, y1, x2, y2) >= w + vr + clr for x1, y1, x2, y2, w, g in segs)
            ok = ok and all(math.hypot(px - vx, py - vy) >= r + vr + clr for vx, vy, r in vias)
            if ok:
                add_via(board, 'GND', px, py, via_d, via_drill, locked=False)
                vias.append((px, py, vr))
                added += 1
            x += pitch
        y += pitch
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    removed = drop_stranded_vias(board)
    board.Save(path)
    print(f'[stitch] {added} ground vias added, {removed} removed again (stranded in small copper islands)')


def drop_stranded_vias(board):
    """Remove ground vias that ended up outside the filled ground pour on either layer."""
    import pcbnew
    zones = [z for z in board.Zones() if z.GetNetname() == 'GND' and not z.GetIsRuleArea()]
    ends = set()
    for t in board.GetTracks():
        if t.GetClass() != 'PCB_VIA' and t.GetNetname() == 'GND':
            ends |= {(t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)}
    removed = 0
    for v in [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'GND']:
        pos = v.GetPosition()
        on = {lay for z in zones for lay in (pcbnew.F_Cu, pcbnew.B_Cu)
              if z.IsOnLayer(lay) and z.HitTestFilledArea(lay, pos)}
        if len(on) < 2 and (pos.x, pos.y) not in ends:
            board.Remove(v)
            removed += 1
    if removed:
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    return removed


def step_drc():
    import pcbnew
    path = os.path.join(HERE, f'{PROJECT}.kicad_pcb')
    rpt = os.path.join(HERE, 'build', 'drc.rpt')
    board = pcbnew.LoadBoard(path)
    pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(rpt).read()
    counts = {}
    for m in re.finditer(r'^\[(\w+)\]:.*\n\s+(?:Local override; )?(?:Rule: [^;]*; )?Severity: (\w+)', txt, re.M):
        counts.setdefault((m.group(1), m.group(2)), 0)
        counts[(m.group(1), m.group(2))] += 1
    unc = re.search(r'Found (\d+) unconnected', txt)
    errors = sum(v for (k, s), v in counts.items() if s == 'error')
    print(f"[drc] errors: {errors}, unconnected pads: {unc.group(1) if unc else '?'}")
    for (k, s), v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f'    {v:4d}  {s:8s} {k}')
    return errors, int(unc.group(1)) if unc else -1


# =============================================================================
# 5. OUTPUTS: Gerbers, drill, BOM, position file, schematic PDF, images,
#    placement.json for the Blender model
# =============================================================================
BODY = [  # (footprint name prefix, width, depth, height, colour, shape) for the Blender model
    ('ESP32-WROOM', 0, 0, 3.1, 'esp_silver', 'box'), ('Ai-Thinker-Ra-01', 0, 0, 3.0, 'esp_silver', 'box'),
    ('AMASS_XT60', 0, 0, 8.4, 'yellow', 'box'), ('AMASS_XT30', 0, 0, 9.0, 'yellow', 'box'),
    ('USB_A_', 0, 0, 7.0, 'esp_silver', 'box'), ('USB_C_', 9.0, 7.3, 3.2, 'esp_silver', 'box'),
    ('U.FL', 2.6, 2.6, 1.2, 'esp_silver', 'box'), ('TO-252', 6.6, 6.1, 2.3, 'black', 'box'),
    ('SOT-223', 6.5, 3.5, 1.6, 'black', 'box'), ('SOT-89', 4.5, 2.5, 1.5, 'black', 'box'),
    ('SOT-23-6', 2.9, 1.6, 1.1, 'black', 'box'), ('SOT-23', 2.9, 1.3, 1.1, 'black', 'box'),
    ('SOIC-16', 9.9, 3.9, 1.6, 'black', 'box'), ('LGA-28', 5.2, 3.8, 1.1, 'black', 'box'),
    ('Bosch_LGA-8', 2.5, 2.5, 0.9, 'esp_silver', 'box'), ('D_SOD-323', 1.7, 1.25, 0.9, 'black', 'box'),
    ('D_SMA', 4.3, 2.6, 2.1, 'black', 'box'), ('D_SMB', 4.6, 3.6, 2.2, 'black', 'box'),
    ('R_0805', 2.0, 1.25, 0.6, 'black', 'box'), ('C_0805', 2.0, 1.25, 0.9, 'tan', 'box'),
    ('C_1206', 3.2, 1.6, 1.2, 'tan', 'box'), ('LED_0805', 2.0, 1.25, 0.8, 'led_green', 'box'),
    ('Fuse_1812', 4.5, 3.2, 1.2, 'yellow', 'box'), ('Fuse_1206', 3.2, 1.6, 1.0, 'yellow', 'box'),
    ('CP_Elec_6.3', 6.6, 6.6, 7.7, 'esp_silver', 'cyl'), ('L_Bourns_SRR1260', 12.5, 12.5, 6.0, 'black', 'box'),
    ('Crystal_SMD_3215', 3.2, 1.5, 0.9, 'esp_silver', 'box'), ('SW_Push_1P1T_XKB', 5.1, 5.1, 1.5, 'black', 'box'),
    ('TerminalBlock_Phoenix_PT', 0, 0, 8.5, 'tb_green', 'box'),
]


def placement_records(board):
    import pcbnew
    T = pcbnew.ToMM
    recs = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        name = str(fp.GetFPID().GetLibItemName())
        rot = fp.GetOrientationDegrees()
        spec = next((b for b in BODY if name.startswith(b[0])), None)
        if spec is None:
            continue
        if ref == 'U7':
            x0, y0, x1, y1 = module_body('U7')
            recs.append(dict(ref=ref, kind='part', fp=name, x=(x0 + x1) / 2, y=(y0 + y1) / 2, w=x1 - x0, d=y1 - y0,
                             h=spec[3], color=spec[4], shape=spec[5], rot=0.0))
            continue
        fp.BuildCourtyardCaches()
        poly = fp.GetCourtyard(pcbnew.F_CrtYd)
        bb = poly.BBox() if poly.OutlineCount() else fp.GetBoundingBox(False, False)
        cx, cy = T(bb.GetCenter().x) - OX, T(bb.GetCenter().y) - OY
        w, d = spec[1], spec[2]
        if not w:        # take the size from the courtyard (minus its margin)
            w, d = T(bb.GetWidth()) - 0.5, T(bb.GetHeight()) - 0.5
        elif abs(rot) % 180 == 90:
            w, d = d, w
        recs.append(dict(ref=ref, kind='part', fp=name, x=cx, y=cy, w=w, d=d, h=spec[3], color=spec[4],
                         shape=spec[5], rot=rot))
    return recs


# JLCPCB's pick-and-place machines use a different zero rotation for some packages
# than KiCad. These corrections come from the community database used by
# JLCKicadTools (github.com/matthewlai/JLCKicadTools, cpl_rotations_db.csv).
# Always check the 3D placement preview on JLCPCB's order page before paying.
JLC_ROT = [
    (r'^SOT-223', 180), (r'^SOT-23', -90), (r'^SOT-89', 180), (r'^TSOT-23', 180), (r'^SOIC-', 270),
    (r'^CP_Elec_6.3x7.7', 180), (r'^USB_C_Receptacle_HRO_TYPE-C-31-M-12', 180), (r'^ESP32-W', 270),
    (r'^JST_PH_S', 180),
]
THT_REFS = {'J1', 'J2', 'J13'} | {p['ref'] for p in DZ.PARTS if p['fp'].startswith('TerminalBlock')}


def write_jlc_files(board, out):
    """JLCPCB assembly files: BOM (grouped by LCSC part) and CPL (placement)."""
    import pcbnew
    T = pcbnew.ToMM
    parts = {p['ref']: p for p in DZ.PARTS}
    groups = {}
    for p in DZ.PARTS:
        if not p.get('lcsc'):
            continue
        fpname = p['fp'].split(':')[1]
        groups.setdefault((p['lcsc'], fpname), []).append(p['ref'])

    def refkey(r):
        return (re.sub(r'\d', '', r), int(re.sub(r'\D', '', r) or 0))
    bom = os.path.join(out, f'{PROJECT}-jlcpcb-bom.csv')
    with open(bom, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #', 'Description'])
        for (lcsc, fpn), refs in sorted(groups.items(), key=lambda kv: refkey(sorted(kv[1], key=refkey)[0])):
            refs.sort(key=refkey)
            vals = []
            for r in refs:
                if parts[r]['val'] not in vals:
                    vals.append(parts[r]['val'])
            val = ' / '.join(vals)
            desc = parts[refs[0]]['mpn']
            if len(refs) > 1:          # a note about one part doesn't apply to the whole line
                desc = re.sub(r'\s*\([^)]*\)\s*$', '', desc)
            w.writerow([val, ','.join(refs), fpn, lcsc, desc])
    cpl = os.path.join(out, f'{PROJECT}-jlcpcb-cpl.csv')
    n = 0
    with open(cpl, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for fp in sorted(board.GetFootprints(), key=lambda fp: refkey(fp.GetReference())):
            ref = fp.GetReference()
            if ref not in parts or not parts[ref].get('lcsc'):
                continue
            name = str(fp.GetFPID().GetLibItemName())
            rot = fp.GetOrientationDegrees()
            for pat, d in JLC_ROT:
                if re.match(pat, name):
                    rot += d
                    break
            rot %= 360
            pos = fp.GetPosition()
            w.writerow([ref, f'{T(pos.x):.3f}mm', f'{-T(pos.y):.3f}mm', 'Top', f'{rot:.0f}'])
            n += 1
    smd = sum(len(r) for (l, fpn), r in groups.items() if not set(r) & THT_REFS)
    print(f'[jlc] BOM {len(groups)} lines ({sum(len(r) for r in groups.values())} parts, {smd} SMD) -> {bom}')
    print(f'[jlc] CPL {n} placements -> {cpl}')
    return groups


def step_outputs():
    import pcbnew
    import shutil
    import zipfile
    out = os.path.join(HERE, 'output')
    os.makedirs(out, exist_ok=True)
    pcb = os.path.join(HERE, f'{PROJECT}.kicad_pcb')
    sch = os.path.join(HERE, f'{PROJECT}.kicad_sch')
    gdir = os.path.join(HERE, 'build', 'gerbers')
    shutil.rmtree(gdir, ignore_errors=True)
    os.makedirs(gdir)
    run = lambda *a: subprocess.run(list(a), check=True, capture_output=True, text=True)  # noqa: E731
    run('kicad-cli', 'pcb', 'export', 'gerbers', '-o', gdir + '/', '--layers',
        'F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts', '--subtract-soldermask', pcb)
    run('kicad-cli', 'pcb', 'export', 'drill', '-o', gdir + '/', '--format', 'excellon',
        '--excellon-separate-th', '--generate-map', '--map-format', 'gerberx2', pcb)
    zpath = os.path.join(out, f'{PROJECT}-gerbers.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, fn), fn)
    print(f'[gerbers] {len(os.listdir(gdir))} files -> {zpath}')
    run('kicad-cli', 'sch', 'export', 'pdf', '-o', os.path.join(out, f'{PROJECT}-schematic.pdf'), sch)
    run('kicad-cli', 'pcb', 'export', 'pdf', '-o', os.path.join(out, f'{PROJECT}-layout.pdf'), '--layers',
        'F.Cu,F.SilkS,Edge.Cuts,F.Fab', '--include-border-title', pcb)
    board = pcbnew.LoadBoard(pcb)
    write_jlc_files(board, out)
    # drill holes for the realistic images
    holes = []
    T = pcbnew.ToMM
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetDrillSize().x > 0:
                p = pad.GetPosition()
                holes.append((T(p.x), T(p.y), T(pad.GetDrillSize().x) / 2))
    for t in board.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            holes.append((T(t.GetPosition().x), T(t.GetPosition().y), T(t.GetDrillValue()) / 2))
    hj = os.path.join(HERE, 'build', 'holes.json')
    json.dump(holes, open(hj, 'w'))
    py = os.environ.get('PY_IMAGES', 'python3.11')
    r = subprocess.run([py, os.path.join(HERE, 'render_board_images.py'), pcb, hj, out], capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr[-2000:])
    # schematic image
    sdir = os.path.join(HERE, 'build', 'schsvg')
    shutil.rmtree(sdir, ignore_errors=True)
    os.makedirs(sdir)
    run('kicad-cli', 'sch', 'export', 'svg', '-o', sdir, sch)
    svg = [f for f in os.listdir(sdir) if f.endswith('.svg')][0]
    subprocess.run([py, '-c', 'import cairosvg,sys; cairosvg.svg2png(url=sys.argv[1], write_to=sys.argv[2], '
                    'output_width=4200, background_color="white")', os.path.join(sdir, svg),
                    os.path.join(out, f'{PROJECT}-schematic.png')], check=True)
    # placement for the Blender model
    recs = placement_records(board)
    json.dump(dict(board_w=DZ.BOARD_W, board_h=DZ.BOARD_H, parts=recs),
              open(os.path.join(HERE, 'placement.json'), 'w'), indent=1)
    print(f'[placement] {len(recs)} parts -> placement.json')


if __name__ == '__main__':
    steps = sys.argv[1:] or ['all']
    if 'all' in steps:
        steps = ['sch', 'verify_sch', 'check', 'route', 'widen', 'stitch', 'drc', 'outputs']
    for s in steps:
        globals()[f'step_{s}']()
