#!/usr/bin/env python3
"""
generate_board.py - builds the KiCad project for the Minnow AUV main board
from design.py (single source of truth).

Steps (each can be run on its own):
  libs      write the project symbol/footprint libraries (auv.kicad_sym, auv.pretty)
  sch       write the schematic (auv-mainboard.kicad_sch)
  pcb       place every footprint, assign nets, outline, zones -> auv-mainboard.kicad_pcb
  check     courtyard overlap / board-edge check of the placement
  route     export Specctra DSN, autoroute with Freerouting, import the result
  outputs   DRC report, Gerbers + drill (zip), BOM, placement.json for Blender

Needs KiCad 7+ (pcbnew Python module, kicad-cli) and Java + Freerouting for 'route'.
Usage: python3 generate_board.py all
"""
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

PROJECT = 'auv-mainboard'
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
# 1. PROJECT LIBRARIES
# =============================================================================

def fp_header(name, descr, tags, attr):
    return [f'(footprint "{name}" (version 20221018) (generator pcbnew)',
            '  (layer "F.Cu")',
            f'  (descr "{descr}")',
            f'  (tags "{tags}")',
            f'  (attr {attr})']


def fp_text(kind, text, x, y, layer, size=1.0, hide=False):
    h = ' hide' if hide else ''
    return (f'  (fp_text {kind} "{text}" (at {x:.3f} {y:.3f}) (layer "{layer}"){h}\n'
            f'    (effects (font (size {size} {size}) (thickness {size * 0.15:.3f})))\n  )')


def fp_line(x1, y1, x2, y2, layer, w=0.12):
    return (f'  (fp_line (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f}) '
            f'(stroke (width {w}) (type solid)) (layer "{layer}"))')


def fp_rect(x1, y1, x2, y2, layer, w=0.12):
    return [fp_line(x1, y1, x2, y1, layer, w), fp_line(x2, y1, x2, y2, layer, w),
            fp_line(x2, y2, x1, y2, layer, w), fp_line(x1, y2, x1, y1, layer, w)]


def th_pad(num, x, y, shape='circle', size=1.7, drill=1.0):
    return (f'  (pad "{num}" thru_hole {shape} (at {x:.3f} {y:.3f}) (size {size} {size}) '
            f'(drill {drill}) (layers "*.Cu" "*.Mask"))')


def write_footprints():
    d = os.path.join(HERE, 'auv.pretty')
    os.makedirs(d, exist_ok=True)
    # ---- ESP32-S3-DevKitC-1 on two 1x22 sockets. Origin = J1 pin 1 (3V3, antenna end).
    # Pins run toward -X; J3 row is +22.86 mm in Y (0.9", verified against
    # Espressif's own KiCad footprint and the Wokwi board definition).
    L = fp_header('ESP32-S3-DevKitC-1_Socket',
                  'ESP32-S3-DevKitC-1 (v1.0/v1.1) on 2x22 2.54 mm female headers, rows 22.86 mm apart. '
                  'Antenna end = pin 1 end. Keep copper out from under the antenna.',
                  'ESP32-S3 DevKitC devkit socket', 'through_hole')
    L.append(fp_text('reference', 'REF**', -26.67, 11.43, 'F.SilkS', 1.2))
    L.append(fp_text('value', 'ESP32-S3-DevKitC-1', -26.67, 14.0, 'F.Fab', 1.0))
    y0, y1 = -1.333, 22.86 + 1.333           # board 25.53 mm wide
    xa, xb = 7.667, -53.34 - 9.05            # antenna end / USB end (Wokwi outline)
    L += fp_rect(xb, y0, xa, y1, 'F.SilkS', 0.15)
    for yy in (0.0, 22.86):        # courtyard = the two socket strips only
        L += fp_rect(-53.34 - 1.6, yy - 1.6, 1.6, yy + 1.6, 'F.CrtYd', 0.05)
    L += fp_rect(xb, y0, xa, y1, 'F.Fab', 0.1)
    L.append(fp_line(1.6, y0, 1.6, y1, 'F.SilkS', 0.12))
    L.append(fp_text('user', 'ANTENNA', 4.6, 11.43, 'F.SilkS', 0.8))
    L.append(fp_text('user', 'USB', xb + 3.0, 11.43, 'F.SilkS', 0.8))
    L.append(fp_text('user', 'J1  3V3', -4.0, 1.9, 'F.SilkS', 0.8))
    L.append(fp_text('user', 'J3  GND', -4.0, 20.9, 'F.SilkS', 0.8))
    for n in range(1, 23):
        x = -(n - 1) * 2.54
        L.append(th_pad(str(n), x, 0.0, 'rect' if n == 1 else 'circle'))
        L.append(th_pad(str(22 + n), x, 22.86))
    L.append(')')
    open(os.path.join(d, 'ESP32-S3-DevKitC-1_Socket.kicad_mod'), 'w').write('\n'.join(L) + '\n')
    # ---- Ebyte E220-900T22D on a 1x7 socket. Origin = pin 1 (M0). Pins along +Y,
    # module body extends toward +X with the SMA connector at the far end.
    L = fp_header('E220-900T22D_Socket',
                  'Ebyte E220-900T22D LoRa module on a 1x7 2.54 mm female header. Pinout M0,M1,RXD,TXD,AUX,VCC,GND. '
                  'Outline 21 x 36 mm is approximate (check your module).',
                  'LoRa E220 Ebyte', 'through_hole')
    L.append(fp_text('reference', 'REF**', 17.0, 7.62, 'F.SilkS', 1.2))
    L.append(fp_text('value', 'E220-900T22D', 17.0, 10.0, 'F.Fab', 1.0))
    L += fp_rect(-1.3, -2.88, 34.7, 18.12, 'F.SilkS', 0.15)
    L += fp_rect(-1.6, -1.6, 1.6, 6 * 2.54 + 1.6, 'F.CrtYd', 0.05)   # socket strip only
    L += fp_rect(34.7, 4.1, 41.0, 11.1, 'F.Fab', 0.1)
    L.append(fp_text('user', 'SMA ->', 30.0, 7.62, 'F.SilkS', 0.8))
    for i, nm in enumerate(['M0', 'M1', 'RXD', 'TXD', 'AUX', 'VCC', 'GND']):
        L.append(th_pad(str(i + 1), 0.0, i * 2.54, 'rect' if i == 0 else 'circle'))
        L.append(fp_text('user', nm, 3.2, i * 2.54, 'F.SilkS', 0.8))
    L.append(')')
    open(os.path.join(d, 'E220-900T22D_Socket.kicad_mod'), 'w').write('\n'.join(L) + '\n')


def sym_pin(ptype, x, y, rot, name, num, length=5.08):
    return (f'      (pin {ptype} line (at {x:.2f} {y:.2f} {rot}) (length {length})\n'
            f'        (name "{name}" (effects (font (size 1.27 1.27))))\n'
            f'        (number "{num}" (effects (font (size 1.27 1.27))))\n      )')


def write_symbols():
    out = ['(kicad_symbol_lib (version 20220914) (generator kicad_symbol_editor)']
    # ---- DevKit
    n = 'ESP32-S3-DevKitC-1'
    h = 21 * 2.54 / 2
    out.append(f'  (symbol "{n}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)')
    out.append(f'    (property "Reference" "U" (at 0 {h + 5.08:.2f} 0) (effects (font (size 1.27 1.27))))')
    out.append(f'    (property "Value" "{n}" (at 0 {-(h + 5.08):.2f} 0) (effects (font (size 1.27 1.27))))')
    out.append('    (property "Footprint" "auv:ESP32-S3-DevKitC-1_Socket" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
    out.append('    (property "Datasheet" "https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide.html" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
    out.append(f'    (symbol "{n}_0_1"')
    out.append(f'      (rectangle (start -12.7 {h + 2.54:.2f}) (end 12.7 {-(h + 2.54):.2f}) (stroke (width 0.254) (type default)) (fill (type background)))')
    out.append('    )')
    out.append(f'    (symbol "{n}_1_1"')
    for i, name in enumerate(DZ.DEVKIT_J1):
        pt = 'power_out' if name == '3V3' else 'power_in' if name in ('5V', 'GND') else 'input' if name == 'RST' else 'bidirectional'
        out.append(sym_pin(pt, -17.78, h - i * 2.54, 0, name, i + 1))
    for i, name in enumerate(DZ.DEVKIT_J3):
        pt = 'power_in' if name == 'GND' else 'bidirectional'
        out.append(sym_pin(pt, 17.78, h - i * 2.54, 180, name, 22 + i + 1))
    out.append('    )')
    out.append('  )')
    # ---- E220
    n = 'E220-900T22D'
    out.append(f'  (symbol "{n}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)')
    out.append('    (property "Reference" "J" (at 0 11.43 0) (effects (font (size 1.27 1.27))))')
    out.append(f'    (property "Value" "{n}" (at 0 -11.43 0) (effects (font (size 1.27 1.27))))')
    out.append('    (property "Footprint" "auv:E220-900T22D_Socket" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
    out.append('    (property "Datasheet" "https://www.cdebyte.com/products/E220-900T22D" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
    out.append(f'    (symbol "{n}_0_1"')
    out.append('      (rectangle (start -7.62 10.16) (end 7.62 -10.16) (stroke (width 0.254) (type default)) (fill (type background)))')
    out.append('    )')
    out.append(f'    (symbol "{n}_1_1"')
    for i, (name, pt) in enumerate((('M0', 'input'), ('M1', 'input'), ('RXD', 'input'), ('TXD', 'output'),
                                     ('AUX', 'output'), ('VCC', 'power_in'), ('GND', 'power_in'))):
        out.append(sym_pin(pt, -12.7, 7.62 - i * 2.54, 0, name, i + 1))
    out.append('    )')
    out.append('  )')
    out.append(')')
    open(os.path.join(HERE, 'auv.kicad_sym'), 'w').write('\n'.join(out) + '\n')


def write_lib_tables():
    open(os.path.join(HERE, 'sym-lib-table'), 'w').write(
        '(sym_lib_table\n  (lib (name "auv")(type "KiCad")(uri "${KIPRJMOD}/auv.kicad_sym")(options "")(descr "Minnow AUV parts"))\n)\n')
    open(os.path.join(HERE, 'fp-lib-table'), 'w').write(
        '(fp_lib_table\n  (lib (name "auv")(type "KiCad")(uri "${KIPRJMOD}/auv.pretty")(options "")(descr "Minnow AUV parts"))\n)\n')


def step_libs():
    write_footprints()
    write_symbols()
    write_lib_tables()
    print('[libs] auv.pretty, auv.kicad_sym, lib tables written')


# =============================================================================
# 2. PCB
# =============================================================================

def load_fp(fpid):
    import pcbnew
    lib, name = fpid.split(':')
    path = os.path.join(HERE, 'auv.pretty') if lib == 'auv' else os.path.join(KFP, f'{lib}.pretty')
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


def step_check(board=None):
    if board is None:
        board, _ = build_pcb()
    import pcbnew
    board.BuildConnectivity()
    for fp in board.GetFootprints():
        fp.BuildCourtyardCaches()
    boxes = courtyard_boxes(board)
    probs = []
    # raised module bodies (DevKit on 8.5 mm sockets, E220 likewise): only low parts underneath
    bodies = {}
    for ref, (x0, y0, x1, y1) in (('U2', (-62.39, -1.333, 8.17, 24.19)), ('J4', (-1.3, -2.88, 41.5, 18.12))):
        bx, by, _ = next(p for p in DZ.PARTS if p['ref'] == ref)['pcb']
        bodies[ref] = (bx + x0, by + y0, bx + x1, by + y1)
    for ref, (ax0, ay0, ax1, ay1) in boxes.items():
        if ref in bodies:
            continue
        for mref, (mx0, my0, mx1, my1) in bodies.items():
            if min(ax1, mx1) - max(ax0, mx0) > 0.05 and min(ay1, my1) - max(ay0, my0) > 0.05:
                if not _low_under_socket(ref):
                    probs.append(f'{ref} is under the raised {mref} but is not a low-profile part')
    refs = sorted(boxes)
    for i, a in enumerate(refs):
        ax0, ay0, ax1, ay1 = boxes[a]
        if ax0 < -0.01 or ay0 < -0.01 or ax1 > DZ.BOARD_W + 0.01 or ay1 > DZ.BOARD_H + 0.01:
            if a not in ('U2', 'J4'):     # the DevKit antenna end and the SMA may overhang
                probs.append(f'{a} outside board: {tuple(round(v, 1) for v in boxes[a])}')
        for b in refs[i + 1:]:
            bx0, by0, bx1, by1 = boxes[b]
            ox = min(ax1, bx1) - max(ax0, bx0)
            oy = min(ay1, by1) - max(ay0, by0)
            if ox > 0.05 and oy > 0.05:
                pa = {'U2': 'socketed', 'J4': 'socketed'}
                if (a in pa) != (b in pa) and _low_under_socket(a if b in pa else b):
                    continue      # low SMD parts are allowed under the raised DevKit / E220
                probs.append(f'{a} overlaps {b} by {ox:.1f} x {oy:.1f} mm')
    print(f'[check] {len(boxes)} footprints, {len(probs)} problems')
    for p in probs:
        print('   ', p)
    return probs


def _low_under_socket(ref):
    part = next(p for p in DZ.PARTS if p['ref'] == ref)
    low = ('Resistor_SMD', 'Capacitor_SMD', 'TestPoint', 'Diode_SMD:D_SOD', 'LED_SMD')
    return part['fp'].startswith(low) or part['fp'] == DZ.SOT23


def add_keepout(board):
    import pcbnew
    F = pcbnew.FromMM
    W, H = DZ.BOARD_W, DZ.BOARD_H
    # no copper under the ESP32 module antenna (DevKit antenna end overhangs the front edge)
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
    x0 = DZ.PARTS[[p['ref'] for p in DZ.PARTS].index('U2')]['pcb'][0] + 1.4
    for x, y in ((x0, 29.5), (W + 1, 29.5), (W + 1, H + 1), (x0, H + 1)):
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
    # silkscreen
    texts = [
        ('MINNOW AUV MAIN BOARD  rev ' + DZ.REV, 75.0, 30.0, 1.4, pcbnew.B_SilkS),
        ('ESP32-S3 / LM2596 / E220 LoRa / 4-in-1 ESC', 75.0, 32.5, 1.0, pcbnew.B_SilkS),
        ('github.com: BIOHUB/submarine', 70.0, 58.6, 0.8, pcbnew.B_SilkS),
        ('BATTERY 3S  + / -', 9.5, 21.0, 1.0, pcbnew.F_SilkS),
        ('CHECK POLARITY', 9.5, 39.0, 1.0, pcbnew.F_SilkS),
        ('ESC POWER', 8.0, 57.6, 0.9, pcbnew.F_SilkS),
        ('ESC: G CUR TLM M1-M4', 16.5, 17.2, 0.8, pcbnew.F_SilkS),
    ]
    for txt, x, y, s, layer in texts:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(txt)
        t.SetPosition(V(kx(x), ky(y)))
        t.SetLayer(layer)
        t.SetTextSize(V(s, s))
        t.SetTextThickness(F(s * 0.15))
        if layer == pcbnew.B_SilkS:
            t.SetMirrored(True)
        board.Add(t)


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
    flags = [('GND', '#FLG01'), ('VSYS', '#FLG02'), ('+5V', '#FLG03'), ('DEVKIT_5V', '#FLG04')]
    lib_ids = sorted({p['sym'] for p in parts} | {'power:PWR_FLAG'})
    items = []          # schematic body lines
    # --- layout: blocks in columns
    order = ['power', 'buck', 'outputs', 'mcu', 'lora', 'esc', 'sensors', 'camera', 'misc']
    col_w = 176.0
    margin_x, margin_y = 20.0, 22.0
    cols = [[], [], []]
    col_assign = {'power': 0, 'buck': 0, 'outputs': 0, 'mcu': 1, 'lora': 1, 'esc': 1, 'sensors': 2,
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
                if p['ref'] == 'U2' or q['num'] in p['pins']:
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
        'Magnet power switch: holding a magnet on the hull closes the reed switch -> Q3 pulls the P-FET gates low ->',
        'the ESP32 boots and drives PWR_HOLD (GPIO21) high to keep power on. Shutdown = firmware releases PWR_HOLD.',
        'All ADC inputs are on ADC1 (GPIO1-10) so they keep working while Wi-Fi talks to the camera.',
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
            '    (date "2026-11-08")',
            f'    (rev "{DZ.REV}")',
            '    (company "BIOHUB / submarine")',
            '    (comment 1 "ESP32-S3 DevKitC-1 carrier: 3S power latch, 5V buck, LoRa, 4-in-1 ESC, 4K camera control")',
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
            'rules': {'min_clearance': 0.2, 'min_copper_edge_clearance': 0.4, 'min_hole_clearance': 0.25,
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
    """Hand-placed wide copper for the high-current paths."""
    P = lambda r, n, big=False: pad_xy(board, r, n, big)  # noqa: E731
    j1v, f1a, f1b = P('J1', '2'), P('F1', '1'), P('F1', '2')
    q1s, q2s = P('Q1', '3'), P('Q2', '3')
    q1t, q2t = P('Q1', '2', True), P('Q2', '2', True)
    c2p, j2v = P('C2', '1'), P('J2', '2')
    j1g, j2g = P('J1', '1'), P('J2', '1')
    d4k = P('D4', '1')
    # battery + -> fuse
    add_track(board, 'VBAT_IN', [j1v, f1a], 3.0)
    # fuse -> both FET sources
    add_track(board, 'VBAT_F', [f1b, q1s], 2.5)
    xm = f1b[0] + 4.0
    add_track(board, 'VBAT_F', [f1b, (xm, f1b[1]), (xm, q2s[1]), q2s], 2.0)
    # FET drains (tabs) -> bulk cap -> ESC XT30, and to the TVS
    add_track(board, 'VSYS', [q1t, q2t], 3.0)
    add_track(board, 'VSYS', [q2t, (q2t[0], q2t[1] + 2.5), (c2p[0], c2p[1] - 5.0), c2p], 2.5)
    add_track(board, 'VSYS', [c2p, (c2p[0] - 3.0, c2p[1] + 3.0), (j2v[0] + 5.5, c2p[1] + 3.0),
                              (j2v[0], j2v[1] - 1.0), j2v], 2.5)
    add_track(board, 'VSYS', [(q2t[0], d4k[1] - 0.15), d4k], 1.5)
    # ESC / battery return on the bottom layer
    add_track(board, 'GND', [j1g, (j1g[0] + 2.3, j1g[1] + 2.3), (j1g[0] + 2.3, j2g[1] - 2.5),
                             (j2g[0] + 2.3, j2g[1]), j2g], 3.0, layer='B.Cu')
    # LM2596 switch node -> inductor and catch diode, output to the bulk cap
    u1sw, l1a, d5k = P('U1', '2'), P('L1', '1'), P('D5', '1')
    x_out = u1sw[0] + 3.5
    add_track(board, 'BUCK_SW', [u1sw, (x_out, u1sw[1]), (l1a[0] - 0.6, l1a[1] + 1.5)], 1.2)
    add_track(board, 'BUCK_SW', [(x_out, u1sw[1]), (d5k[0], u1sw[1] + 2.3), d5k], 1.2)
    l1b, c5p = P('L1', '2'), P('C5', '1')
    add_track(board, '+5V', [l1b, c5p], 1.2)
    # thermal vias in the regulator tab
    tx, ty = P('U1', '3', True)
    for dx in (-2.0, 0.0, 2.0):
        for dy in (-2.6, 2.6):
            add_via(board, 'GND', tx + dx, ty + dy)


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
        add_track(board, name, pts, width, layer, locked=False)
    for name, x, y, dia, drill in vias:
        add_via(board, name, x, y, dia, drill, locked=False)
    path = os.path.join(HERE, f'{PROJECT}.kicad_pcb')
    board.Save(path)
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
BODY = [  # (footprint name prefix, width, depth, height, colour, shape)
    ('AMASS_XT60', 0, 0, 8.4, 'yellow', 'box'), ('AMASS_XT30', 0, 0, 5.4, 'yellow', 'box'),
    ('Fuseholder_Blade_ATO', 0, 0, 19.0, 'fuse_blue', 'box'), ('TO-252', 6.6, 6.1, 2.3, 'black', 'box'),
    ('TO-263', 10.2, 9.0, 4.5, 'black', 'box'), ('SOT-23', 2.9, 1.3, 1.1, 'black', 'box'),
    ('D_SOD-123', 2.7, 1.6, 1.1, 'black', 'box'), ('D_SOD-323', 1.7, 1.25, 0.9, 'black', 'box'),
    ('D_SMA', 4.3, 2.6, 2.1, 'black', 'box'), ('D_SMB', 4.6, 3.6, 2.2, 'black', 'box'),
    ('D_SMC', 6.9, 5.9, 2.3, 'black', 'box'), ('R_0805', 2.0, 1.25, 0.6, 'black', 'box'),
    ('C_0805', 2.0, 1.25, 0.9, 'tan', 'box'), ('C_1206', 3.2, 1.6, 1.2, 'tan', 'box'),
    ('LED_0805', 2.0, 1.25, 0.8, 'led_green', 'box'), ('Fuse_1812', 4.5, 3.2, 1.2, 'yellow', 'box'),
    ('CP_Radial_D10', 10.0, 10.0, 12.5, 'cap_blue', 'cyl'), ('CP_Radial_D8', 8.0, 8.0, 11.5, 'cap_blue', 'cyl'),
    ('L_Bourns_SRR1260', 12.0, 12.0, 6.0, 'black', 'box'), ('DIP-4', 6.5, 4.6, 3.5, 'black', 'box'),
    ('JST_PH', 0, 0, 6.0, 'beige', 'box'), ('JST_XH', 0, 0, 7.0, 'beige', 'box'),
]


def placement_records(board):
    import pcbnew
    T = pcbnew.ToMM
    recs = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        name = fp.GetFPID().GetLibItemName().wx_str() if hasattr(fp.GetFPID().GetLibItemName(), 'wx_str') \
            else str(fp.GetFPID().GetLibItemName())
        pos = fp.GetPosition()
        rot = fp.GetOrientationDegrees()
        if ref == 'U2':
            recs.append(dict(ref=ref, kind='devkit', x=T(pos.x) - OX, y=T(pos.y) - OY, rot=rot))
            continue
        if ref == 'J4':
            recs.append(dict(ref=ref, kind='e220', x=T(pos.x) - OX, y=T(pos.y) - OY, rot=rot))
            continue
        spec = next((b for b in BODY if name.startswith(b[0])), None)
        if spec is None:
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


PRICE = {  # rough UK unit prices (GBP) for one-off quantities, used for the budget
    'R_0805': 0.02, 'C_0805': 0.03, 'C_1206': 0.10, 'LED_0805': 0.05, 'SOT-23': 0.10, 'D_SOD': 0.05,
    'D_SMA': 0.08, 'D_SMB': 0.20, 'D_SMC': 0.30, 'TO-252': 0.60, 'TO-263': 1.20, 'L_Bourns': 0.90,
    'CP_Radial_D10': 0.30, 'CP_Radial_D8': 0.20, 'DIP-4': 0.15, 'Fuse_1812': 0.20, 'Fuseholder': 1.20,
    'AMASS_XT60': 0.90, 'AMASS_XT30': 0.60, 'JST_PH': 0.15, 'JST_XH': 0.15, 'PinSocket': 0.40,
    'ESP32-S3-DevKitC': 0.80, 'E220': 0.25, 'TestPoint': 0.0, 'MountingHole': 0.0,
}


def write_bom(out):
    groups = {}
    for p in DZ.PARTS:
        if p['fp'].startswith(('TestPoint', 'MountingHole')):
            continue
        key = (p['val'], p['fp'], p.get('mpn', ''))
        groups.setdefault(key, []).append(p['ref'])
    rows = []
    total = 0.0
    for (val, fp, mpn), refs in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        refs.sort(key=lambda r: (re.sub(r'\d', '', r), int(re.sub(r'\D', '', r) or 0)))
        name = fp.split(':')[1]
        unit = next((v for k, v in PRICE.items() if name.startswith(k)), 0.1)
        note = ''
        if fp.startswith('auv:ESP32'):
            note = 'module itself is in the main BOM; price = 2x 22-pin female headers'
        if fp.startswith('auv:E220'):
            note = 'module itself is in the main BOM; price = 7-pin female header'
        if fp.startswith('Fuse:Fuseholder'):
            note = 'fuse clips + 15 A ATO blade fuse'
        cost = unit * len(refs)
        total += cost
        rows.append(dict(refs=' '.join(refs), qty=len(refs), value=val, footprint=fp, part=mpn,
                         unit_gbp=f'{unit:.2f}', line_gbp=f'{cost:.2f}', note=note))
    import csv
    path = os.path.join(out, f'{PROJECT}-bom.csv')
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f'[bom] {len(rows)} lines, {sum(r["qty"] for r in rows)} parts, approx GBP {total:.2f} -> {path}')
    return total


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
    run('kicad-cli', 'pcb', 'export', 'pos', '-o', os.path.join(out, f'{PROJECT}-pos.csv'), '--format', 'csv',
        '--units', 'mm', '--side', 'both', pcb)
    run('kicad-cli', 'sch', 'export', 'pdf', '-o', os.path.join(out, f'{PROJECT}-schematic.pdf'), sch)
    run('kicad-cli', 'pcb', 'export', 'pdf', '-o', os.path.join(out, f'{PROJECT}-layout.pdf'), '--layers',
        'F.Cu,F.SilkS,Edge.Cuts,F.Fab', '--include-border-title', pcb)
    # drill holes for the realistic images
    board = pcbnew.LoadBoard(pcb)
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
    write_bom(out)


if __name__ == '__main__':
    steps = sys.argv[1:] or ['all']
    if 'all' in steps:
        steps = ['libs', 'sch', 'verify_sch', 'check', 'route', 'drc', 'outputs']
    for s in steps:
        globals()[f'step_{s}']()
