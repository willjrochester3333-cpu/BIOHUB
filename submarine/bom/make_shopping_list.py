#!/usr/bin/env python3
"""
make_shopping_list.py - turns the parts list into a shopping list with links.

Writes two lists, grouped by the shop you would order from, with a checkbox,
quantity, rough price and search links:
  shopping_list.md       the solder-free build: the Minnow Core board (assembled by
                         JLCPCB), single ESCs with wires, screw terminals, crimp splices
  shopping_list_rev1.md  the rev 1 build: every item in make_bom.py plus every part on the
                         rev 1 board (../pcb/output/auv-mainboard-bom.csv), which you solder

The links are SEARCH links, not links to single listings: listings on Amazon
and eBay change every week, while a search for the exact spec keeps working.
Prices and totals come from make_bom.py, so the two files always agree.
"""
import csv
import re
import os
from urllib.parse import quote_plus

from make_bom import B, TOOLS

HERE = os.path.dirname(os.path.abspath(__file__))
A, E = 'Amazon UK', 'eBay UK'
PCB_BOM = os.path.join(HERE, '..', 'pcb', 'output', 'auv-mainboard-bom.csv')

SEARCH = {
    'Amazon UK': 'https://www.amazon.co.uk/s?k={q}',
    'eBay UK': 'https://www.ebay.co.uk/sch/i.html?_nkw={q}',
    'LCSC': 'https://www.lcsc.com/search?q={q}',
    'Screwfix': 'https://www.screwfix.com/search?search={q}',
    'B&Q': 'https://www.diy.com/search?term={q}',
    'The Pi Hut': 'https://thepihut.com/search?q={q}',
    'CeX': 'https://uk.webuy.com/search?stext={q}',
}


def link(shop, q):
    return f"[{shop}]({SEARCH[shop].format(q=quote_plus(q))})"


# item name in make_bom.B -> (basket, [(shop, search words), ...], what to check before buying)
# The first link is the suggested shop; the others are alternatives.
WHERE = {
    # ---- hull & seals
    'Pressure hull pipe': ('ebay', [(E, '90mm PVC pressure pipe PN10 1m'), (A, '90mm PVC pressure pipe')],
                           'Must be PRESSURE pipe (PN10, 4.3 mm wall), 90.0 mm outside. Not grey/white drain pipe. '
                           'Amazon rarely sells short lengths of it, so this one is from eBay.'),
    'O-rings': ('amazon', [(A, 'AS568-238 o-ring nitrile'), (A, 'o-ring 89mm x 3.5mm'), (E, 'AS568-238 nitrile o-ring')],
                'Size 238 = 88.49 x 3.53 mm, NBR 70.'),
    'O-ring grease': ('amazon', [(A, 'silicone o-ring grease')], 'Silicone only. No Vaseline or petroleum grease.'),
    'Camera window': ('amazon', [(A, 'clear acrylic disc 80mm 8mm'), (E, 'cast acrylic disc 80mm 8mm')],
                      'CAST acrylic, 80 mm across, 8 mm thick. Or send cad/drawings/window_80x8.dxf to a laser-cutting service.'),
    'Window sealant': ('amazon', [(A, 'clear neutral cure silicone sealant'), (A, 'Sikaflex 291i')],
                       'Neutral cure (no vinegar smell).'),
    'Epoxy': ('amazon', [(A, 'laminating epoxy resin small kit'), (A, '5 minute epoxy')],
              'One thin laminating epoxy + one 5-minute epoxy.'),
    'Cable glands': ('amazon', [(A, 'M12 x 1.5 cable gland IP68 nylon 3-6.5mm')], 'Thread M12 x 1.5, cable range 3-6.5 mm.'),
    'Tap': ('amazon', [(A, 'M12 x 1.5 tap')], 'M12 x 1.5 (fine pitch). Not the standard M12 x 1.75.'),
    'Vent / vacuum-test port': ('amazon', [(A, '6mm OD silicone tube'), (A, 'M3 x 10 stainless screw')],
                                '6 mm outside diameter so it seals in a gland.'),
    'High-vis paint': ('amazon', [(A, 'plastic primer spray paint'), (A, 'orange spray paint')], ''),
    # ---- structure
    'PETG filament': ('amazon', [(A, 'PETG filament 1.75mm 1kg')], ''),
    'Keel bar': ('amazon', [(A, 'aluminium flat bar 25mm x 3mm 1m'), (E, 'aluminium flat bar 25mm x 3mm 1m')],
                 'Aluminium, not steel (steel upsets the compass).'),
    'Sled rods': ('amazon', [(A, 'aluminium round tube 6mm 1m'), (E, 'aluminium round tube 6mm 1m')], ''),
    'M4 bolts': ('amazon', [(A, 'M4 stainless socket cap screw assortment nyloc'), (A, 'M4 x 30 stainless socket cap')],
                 'A2 stainless. You need 12 x M4x30 with nyloc nuts and washers.'),
    'M4 countersunk screws': ('amazon', [(A, 'M4 x 12 countersunk stainless')], ''),
    'M3 studs': ('amazon', [(A, 'M3 threaded rod stainless 300mm'), (A, 'M3 nuts washers stainless assortment')],
                 'A2 stainless. Cut with a hacksaw; file the ends so the nuts start easily.'),
    'M3 short screws': ('amazon', [(A, 'M3 stainless socket cap screw assortment')],
                        'An M3 assortment box (6-20 mm) covers these.'),
    'Standoffs': ('amazon', [(A, 'M3 x 20 brass hex standoff male female')], 'Male-female: one threaded pin end.'),
    'Ballast': ('amazon', [(A, 'lead shot fishing 1kg'), (E, 'lead shot 1kg')], 'Lead, not steel shot.'),
    'Straps, ties, foam': ('amazon', [(A, 'velcro battery strap'), (A, 'black EVA foam sheet 3mm')], ''),
    # ---- propulsion
    'Thruster motors': ('amazon_e', [(A, 'A2212 1000KV brushless motor'), (E, 'A2212 1000KV brushless motor')],
                        '1000KV, with the prop adapter. Buy 4 (5 with the spare). Packs of 4 are often cheapest.'),
    'Spare motor': ('amazon_e', [(A, 'A2212 1000KV brushless motor')], 'Same listing as the other four.'),
    '4-in-1 ESC': ('amazon_e', [(A, '4 in 1 ESC 45A 30.5mm BLHeli_S'), (E, '4 in 1 ESC 30.5mm')],
                   'BLHeli_S, Bluejay or AM32 (NOT BLHeli_32 only, NOT an 8-bit PWM-only ESC), 2-6S, 30.5 mm hole spacing.'),
    'Thruster cable': ('amazon', [(A, '3 core 0.5mm round flex cable'), (E, '3 core 0.5mm round flex cable')],
                       'Round, about 5.5 mm across, so the glands seal on it.'),
    'Heat-shrink': ('amazon', [(A, 'adhesive lined heat shrink assortment')], 'Adhesive-lined (glue inside).'),
    'Corrosion inhibitor': ('amazon', [(A, 'ACF-50'), (A, 'Corrosion-X')], ''),
    # ---- power
    'Battery': ('amazon_e', [(A, '3S 18650 battery pack BMS 11.1V XT60'), (E, '3S1P 18650 battery pack BMS XT60')],
                'Must have a BMS (protection board) and branded cells (Samsung, Molicel, LG, Sony). Max 65 x 56 x 19 mm to fit the sled.'),
    'Second battery pack': ('amazon_e', [(A, '3S 18650 battery pack BMS 11.1V XT60')], 'Identical to the first pack.'),
    'Charger': ('amazon_e', [(A, '12.6V 2A lithium charger'), (A, 'XT60 charge lead')], ''),
    # ---- electronics
    'Microcontroller': ('amazon_e', [(A, 'ESP32-S3-DevKitC-1 N16R8'), ('The Pi Hut', 'ESP32-S3-DevKitC-1')],
                        'Must be the DevKitC-1 layout: 2 x 22 pins, two USB-C ports. Other ESP32-S3 boards will not fit the socket.'),
    'Main board PCB': ('jlc', [], ''),
    'Main board components': ('lcsc', [], ''),
    'GPS': ('amazon_e', [(A, 'Beitian BN-220 GPS'), (E, 'BN-220 GPS')], 'BN-220 is 22 x 20 mm; the mast is sized for it.'),
    'IMU / compass': ('amazon_e', [(A, 'BNO085'), ('The Pi Hut', 'BNO085')],
                      'BNO085 (or BNO086). Not the BNO055: the firmware is written for the 085.'),
    'Depth + water temp': ('amazon_e', [(A, 'MS5837-30BA'), (E, 'MS5837-30BA')],
                           '30BA (30 bar) version, not 02BA. If Amazon has none in stock, use the eBay link.'),
    'Hull monitor': ('amazon_e', [(A, 'BME280 module I2C 3.3V')], 'BME280, not BMP280 (the BMP has no humidity sensor).'),
    'Magnet switch': ('amazon_e', [(A, 'reed switch normally open glass'), (A, 'N52 neodymium magnet with hole')], ''),
    'Strobe': ('amazon_e', [(A, '1W white LED star'), (A, '47 ohm 1W resistor')], ''),
    'Leak probes': ('amazon_e', [(A, 'stripboard')], 'Or two bare wires per probe, on the JST leads below.'),
    'Connectors & wire': ('amazon_e', [(A, 'JST PH 2.0 connector kit pre-crimped'), (A, 'JST XH 2.54 pre-crimped cable'),
                                       (A, '14 AWG silicone wire'), (A, '26 AWG hook up wire')],
                         'PH = 2.0 mm pitch (2, 4, 5 and 7 pin). XH = 2.5 mm pitch (2 pin).'),
    'Camera power socket': ('amazon_e', [(A, 'USB A female breakout board')], ''),
    # ---- camera
    '4K camera': ('ebay', [(E, 'GoPro HERO5 Black'), ('CeX', 'GoPro HERO5 Black'), (A, 'GoPro HERO5 Black renewed')],
                  'BLACK edition (Session and White models do not record 4K or fit the cradle). A dead battery is fine. '
                  'Used ones are much cheaper on eBay or CeX than on Amazon.'),
    'microSD card': ('amazon_e', [(A, '64GB microSD U3 V30')], 'U3 / V30. Branded (SanDisk, Samsung, Kingston).'),
    'USB cable': ('amazon_e', [(A, 'short USB A to USB C cable 20cm')], ''),
    # ---- LoRa (phase 2)
    'LoRa radios': ('amazon_e', [(A, 'Ebyte E220-900T22D'), (E, 'E220-900T22D')],
                    'E220-900T22D exactly (868/915 MHz, DIP pins). Not the 400 MHz E220-400.'),
    'Sub antenna': ('amazon_e', [(A, '868MHz FPC antenna IPEX'), (A, 'u.FL IPEX to SMA male pigtail')], ''),
    'Shore antenna': ('amazon_e', [(A, '868MHz SMA antenna')], '868 MHz, SMA male.'),
    'USB-serial adapter': ('amazon_e', [(A, 'CP2102 USB TTL 3.3V')], 'Must have a 3.3 V option.'),
}

BASKETS = [
    ('jlc', 'Order 1: JLCPCB (the main board) - about £14', 'Order this first: it takes 1-2 weeks.'),
    ('lcsc', 'Order 2: LCSC (parts for the main board) - about £15',
     'LCSC belongs to JLCPCB, so if you order both on the same day they can often ship in one parcel. '
     'These are the only parts not from Amazon: Amazon does not sell several of the chips (SRR1260 inductor, '
     'AOD4185, BAT54WS, SMBJ18A), and one LCSC order with exact parts is cheaper than buying kits.'),
    ('amazon_e', 'Order 3: Amazon UK - electronics, motors, battery, radios', ''),
    ('amazon', 'Order 4: Amazon UK - hull, hardware and supplies', 'Skip anything you already have (marked 🏠).'),
    ('ebay', 'Order 5: eBay UK - the two things Amazon is bad for', 'The pressure pipe and a used GoPro.'),
]

PHASE = {1: 'Phase 1', 2: 'Phase 2 (LoRa)', 'opt': 'Optional'}


def pcb_query(value, part):
    """Words to search LCSC for one row of the main-board BOM."""
    p = part.split(' (')[0]
    if 'second FET' in part:
        return 'AOD4185'
    for mpn in ['AO3400A', 'AO3401A', 'AOD4185', 'LM2596S-5.0', 'SRR1260-330M', 'PC817', 'SS34', 'SS54', 'SMBJ18A',
                'BZT52C15', 'BAT54WS', 'XT60PW-M', 'XT30PW-F']:
        if mpn in part:
            return mpn
    for pins in '2457':
        if f'PH {pins}-pin' in part:
            return f'B{pins}B-PH-K-S'
    if 'XH 2-pin' in part:
        return 'B2B-XH-A'
    if 'PTC' in part:
        return '1812 PTC resettable fuse 1.5A'
    if 'PC817' in part:
        return 'PC817 opto-isolator, DIP-4 (presses the camera buttons)'
    if 'ATO' in part:
        return 'ATO blade fuse holder PCB'
    if 'electrolytic' in part:
        uf, v = value.split()
        return f'{uf} {v} aluminum electrolytic low ESR'
    if 'LED' in part:
        return '0805 green LED'
    if '22-pin' in part and 'female' in part:
        return '2.54mm 1x22 female header'
    if '7-pin female' in part:
        return '2.54mm 1x7 female header'
    if p.startswith('0805') and value.endswith(('R', 'k')):
        return f"0805 {value.replace('R', ' ohm')} 1%"
    size = '0805' if '0805' in part else '1206'
    return f"{size} {value.split()[0]} {' '.join(part.split()[1:3])}"


def pcb_label(value, part):
    """A short, clean name for one row of the main-board BOM."""
    m = re.match(r'(0805|1206) (X\dR) (\d+V)', part)
    if m:
        return f"{value.split()[0]} ceramic capacitor, {m[1]}, {m[2]} {m[3]}"
    if part.startswith('0805 1%') or part.startswith('0805 (') or part == '0805 1% thick film':
        return f"{value.replace('R', ' ohm')} resistor, 0805, 1%"
    m = re.search(r'JST (PH|XH) (\d)-pin', part)
    if m:
        mpn = f"B{m[2]}B-PH-K-S" if m[1] == 'PH' else f"B{m[2]}B-XH-A"
        return f"JST {m[1]} {m[2]}-pin vertical header ({mpn})"
    if 'female header' in part:
        n = '22' if '22-pin' in part else '7'
        return f"{n}-pin 2.54 mm female header (socket only; the module itself is in Order 1)"
    if 'second FET' in part or 'AOD4185' in part:
        return 'AOD4185 P-MOSFET, DPAK (or SQD40031EL / IPD50P04P4L-11). The second one (Q2) is optional below 8 A'
    if 'PC817' in part:
        return 'PC817 opto-isolator, DIP-4 (presses the camera buttons)'
    if 'ATO' in part:
        return 'ATO blade fuse PCB holder (2-pin) + 15 A ATO blade fuse'
    return part.split(';')[0]


def pcb_section():
    rows = list(csv.DictReader(open(PCB_BOM)))
    out = ['| ✓ | Qty | Part | Board refs | Link |', '|---|---:|---|---|---|']
    merged = {}
    for r in rows:
        q = pcb_query(r['value'], r['part'])
        qty, part = int(r['qty']), pcb_label(r['value'], r['part'])
        if '2 x 22-pin' in r['part']:
            qty = 2
        if q in merged:
            merged[q]['qty'] += qty
            merged[q]['refs'] += ' ' + r['refs']
        else:
            merged[q] = dict(qty=qty, refs=r['refs'], part=part)
    for q, m in merged.items():
        part = m['part'].replace('|', '/')
        out.append(f"| ☐ | {m['qty']} | {part} | {m['refs']} | {link('LCSC', q)} |")
    n = sum(int(r['qty']) for r in rows)
    out += ['', f'{n} parts in {len(merged)} lines. LCSC sells resistors and small capacitors in packs of 20-100, '
            'which still costs pennies. The fuse holder must have two 2 mm pins 9.2 mm apart plus a locating peg '
            '(the Littelfuse / Pudenz 2-pin ATO holder). '
            'Check the drawing in the datasheet before ordering. Add one **15 A ATO blade fuse** (any car shop, or '
            f"{link('Amazon UK', '15A ATO blade fuse')}).", '',
            f"**Amazon option for the resistors and capacitors:** an 0805 resistor + capacitor assortment kit "
            f"({link('Amazon UK', '0805 resistor capacitor assortment kit')}) covers every R and C on the board, "
            'and leaves you spares for the next project.']
    return out


def main():
    tot = lambda pred: sum(r[3] * r[4] for r in B if pred(r))  # noqa: E731
    p1, p2, opt = tot(lambda r: r[5] == 1), tot(lambda r: r[5] == 2), tot(lambda r: r[5] == 'opt')
    own = tot(lambda r: r[5] in (1, 2) and r[6])
    missing = [r[1] for r in B if r[1] not in WHERE]
    assert not missing, f'no shop for {missing}'

    L = ['# Minnow shopping list: rev 1 board (you solder it)', '',
         '> **Want a build with no soldering at all?** Use the [solder-free shopping list](shopping_list.md) instead. '
         'This list is for the cheaper rev 1 board, which you assemble and solder yourself.', '',
         'Everything needed to build the rev 1 Minnow design, grouped by the shop you would order it from. '
         'Generated by `bom/make_shopping_list.py` from the same data as [`bom.csv`](bom.csv), so quantities and '
         'prices match the parts list.', '',
         '**About the links.** They are *search* links for the exact part, not links to one listing: listings on '
         'Amazon and eBay change weekly, and a search keeps working. Pick a listing that matches the '
         '"Check" column. Prices are rough UK prices (late 2026), delivered; check them before you buy.', '',
         '**Buying from Amazon costs more.** The prices and totals below are the parts-list prices, which assume '
         'the cheapest source. Buying the motors, ESC, sensors and radios on Amazon UK instead of from overseas sellers '
         'typically adds something like £50-90 in total (my estimate, not checked), in exchange for next-day delivery '
         'and easy returns.', '',
         '| | Cost |', '|---|---:|',
         f'| Phase 1: pool-ready sub with the 4K camera | £{p1:.0f} |',
         f'| Phase 2: LoRa telemetry for lake missions | £{p2:.0f} |',
         f'| **Everything, from scratch** | **£{p1 + p2:.0f}** |',
         f'| Items marked 🏠 that most makers already own | -£{own:.0f} |',
         f'| **Everything, if you have the usual supplies** | **£{p1 + p2 - own:.0f}** |',
         f'| Optional extras (second battery, charger, spare motor, paint, spray) | +£{opt:.0f} |',
         '| Vacuum pump for leak testing (tool, strongly recommended) | +£18 |', '',
         'Key: 🏠 = you probably already have it. **P2** = phase 2 (only needed for lake missions; can wait). '
         '**Opt** = optional.', '',
         ]

    for key, title, blurb in BASKETS:
        L += [f'## {title}', '']
        if blurb:
            L += [blurb, '']
        if key == 'jlc':
            L += ['1. Go to the [JLCPCB quote page](https://cart.jlcpcb.com/quote) and upload '
                  '[`pcb/output/auv-mainboard-gerbers.zip`](../pcb/output/auv-mainboard-gerbers.zip).',
                  '2. It reads the size by itself (150 x 60 mm, 2 layers). Leave thickness 1.6 mm, quantity 5, '
                  'HASL lead-free. Any colour.',
                  '3. Do not tick PCB assembly: every part is 0805 or bigger, so it is easy to solder by hand.',
                  '4. Alternative: [PCBWay](https://www.pcbway.com/orderonline.aspx) takes the same zip file.', '']
            continue
        if key == 'lcsc':
            L += pcb_section() + ['']
            continue
        L += ['| ✓ | Qty | Item | Phase | ~£ | Links | Check |', '|---|---:|---|---|---:|---|---|']
        sub = 0.0
        for sub_name, item, spec, qty, unit, phase, owned, _, _ in B:
            basket, links, check = WHERE[item]
            if basket != key:
                continue
            tag = (' 🏠' if owned else '')
            ph = {1: '', 2: 'P2', 'opt': 'Opt'}[phase]
            cost = unit * qty
            if phase != 'opt':
                sub += cost
            ls = ' · '.join(link(s, q) for s, q in links)
            L.append(f'| ☐ | {qty} | **{item}**{tag}<br>{spec} | {ph} | {cost:.0f} | {ls} | {check} |')
        L += ['', f'Subtotal (without optional items): about **£{sub:.0f}**.', '']

    L += ['## Tools', '',
          '| ✓ | Tool | Cost | Links |', '|---|---|---|---|',
          f"| ☐ | **Hand vacuum pump with gauge** (brake-bleeder type), for the leak test before every dive | about £18 | "
          f"{link('Amazon UK', 'hand vacuum pump brake bleeder gauge')} · {link('eBay UK', 'brake bleeder vacuum pump')} |",
          f"| ☐ | Hacksaw + mitre box (or a plastic pipe cutter) and a deburring tool | about £10 if needed | "
          f"{link('Amazon UK', 'plastic pipe cutter')} · {link('Amazon UK', 'deburring tool')} |",
          ]
    L += [f'| | {t} | {c} | |' for t, c in TOOLS if c == 'assumed']
    L += ['',
          '## Not on this list', '',
          '* The relay buoy and underwater sound link discussed earlier: they are not designed yet, so there are no '
          'parts to buy for them. Pool and lake missions with LoRa work without them.',
          '* Printed parts: they come out of the 1 kg of PETG above. See the print list in '
          '[`docs/01-mechanical.md`](../docs/01-mechanical.md#111-print-list).', '',
          '## Before you click buy', '',
          '1. Order the PCB and the LCSC parts first: they take 1-2 weeks. Print the O-ring fit test while you wait.',
          '2. Measure the pipe as soon as it arrives (outside diameter in several places). If it is not 90.0 mm, '
          'change `pipe_od` in `cad/build_sub.py` before printing the end caps.',
          '3. Check the camera and the battery pack sizes against the CAD (`cam_*`, `batt_*` in `build_sub.py`) '
          'before printing the sled and cradle.']
    open(os.path.join(HERE, 'shopping_list_rev1.md'), 'w').write('\n'.join(L) + '\n')
    print(f'shopping_list_rev1.md: p1 £{p1:.0f} p2 £{p2:.0f} own £{own:.0f} opt £{opt:.0f}')


# ---------------------------------------------------------------------------
# The solder-free build (Minnow Core board)
# ---------------------------------------------------------------------------
# rev 1 items the Core build does not need: they are on the assembled board, or replaced below
CORE_SKIPS = ['Microcontroller', 'Main board PCB', 'Main board components', 'IMU / compass', 'Hull monitor',
              'Magnet switch', 'Camera power socket', 'LoRa radios', 'Sub antenna', 'Shore antenna',
              'USB-serial adapter', '4-in-1 ESC', 'Connectors & wire', 'Strobe', 'Leak probes']
CORE_BOARDS_GBP = 198.0      # two assembled boards delivered incl. VAT, see pcb-core/README.md (cost)

# changed specs / checks for items that stay
CORE_OVERRIDE = {
    'Depth + water temp': ('MS5837-30BA module **with the header pins already soldered** (or a sensor with its '
                           'cable already fitted)',
                           '30BA (30 bar) version. The listing photos must show the pins already fitted. It plugs onto '
                           'female-to-male jumper wires, whose pin ends go into the board\'s DEPTH screw terminals.'),
    'GPS': ('Beitian BN-220 (comes with a 4-wire cable)',
            'Cut the plug off the free end of its cable and strip 5 mm of each wire for the screw terminals.'),
}

# (subsystem, item, spec, qty, unit GBP, phase, likely owned, basket, links, check)
CORE_EXTRA = [
    ('Electronics', 'Minnow Core boards', 'Two boards fully assembled by JLCPCB: one for the sub, one is the shore '
     'radio (USB-C to a laptop)', 1, CORE_BOARDS_GBP, 1, False, 'jlc', [], ''),
    ('Propulsion', 'ESCs', 'Single BLHeli_S / Bluejay ESC, 20-30 A, 2-4S, DShot, with the motor, power and signal '
     'wires **already attached**', 4, 7.50, 1, False, 'amazon_e',
     [(A, 'BLHeli_S 30A ESC 2-4S 4 pack'), (A, 'Bluejay 30A ESC'), (E, 'BLHeli_S 30A ESC')],
     'Check the photos: 3 motor wires, 2 power wires and a signal wire must already be attached. Avoid ESCs with '
     'only solder pads, and avoid 4-in-1 boards.'),
    ('Propulsion', 'Motor wire splices', 'Adhesive-lined heat-shrink crimp butt splices, 22-16 AWG (red), pack of 50',
     1, 7.0, 1, False, 'amazon_e', [(A, 'heat shrink butt connectors waterproof 22-16 AWG')],
     '24 used: ESC to thruster cable inside the hull, thruster cable to motor outside. Crimp, then heat: the glue '
     'inside seals the outside ones against water.'),
    ('Power', 'ESC power splitter', '2 x Wago 221-415 lever connectors (5-way) + an XT30 male lead with bare wires',
     1, 6.0, 1, False, 'amazon_e', [(A, 'Wago 221-415'), (A, 'XT30 male pigtail 14AWG')],
     'All four ESC + wires and the XT30 lead\'s + wire in one Wago, all - wires in the other. The XT30 plugs into the '
     'board\'s ESC POWER socket.'),
    ('Electronics', 'Strobe light', '12 V white LED with its wires already attached (built-in resistor)', 1, 3.0, 1,
     False, 'amazon_e', [(A, '12V white LED pre wired')],
     'Must say 12 V: it runs straight from the battery. Goes in the mast.'),
    ('Electronics', 'Jumper wires', 'Female-to-male jumper wires (Dupont), 20 cm', 1, 3.0, 1, True, 'amazon_e',
     [(A, 'dupont jumper wires female to male 20cm')], 'For the depth sensor\'s pins.'),
    ('Electronics', 'Magnet', 'Neodymium disc magnet, 6-10 mm', 1, 3.0, 1, False, 'amazon_e',
     [(A, 'N52 neodymium magnet 10mm x 5mm')], 'The on/off key: hold it against the mark on the hull side.'),
    ('LoRa telemetry', '868 MHz antennas', '868 MHz antenna with a U.FL (IPEX) plug', 2, 4.0, 2, False, 'amazon_e',
     [(A, '868MHz antenna IPEX u.fl')], 'U.FL / IPEX-1 plug. One with a ~30 cm cable for the mast; the shore one can be '
     'any length.'),
]

CORE_TOOLS = [
    ('Ratchet crimper for insulated terminals (red/blue/yellow)', 'about £15',
     [(A, 'ratchet crimper insulated terminals')]),
    ('Wire stripper', 'about £8', [(A, 'automatic wire stripper')]),
    ('Heat gun (a lighter also works for the splices)', 'about £15', [(A, 'mini heat gun')]),
    ('Small flat screwdriver (2.5 mm) for the screw terminals', 'assumed', []),
    ('Hand vacuum pump with gauge (brake-bleeder type), for the leak test before every dive', 'about £18',
     [(A, 'hand vacuum pump brake bleeder gauge')]),
    ('Hacksaw + mitre box (or a plastic pipe cutter) and a deburring tool: for the pipe and the M3 studs',
     'about £10 if needed', [(A, 'plastic pipe cutter')]),
    ('3D printer that prints PETG, multimeter, drill + 4.2 mm and 3.2 mm bits, kitchen scale, bucket', 'assumed', []),
]

CORE_BASKETS = [
    ('jlc', 'Order 1: JLCPCB - the two assembled Minnow Core boards', 'Order this first: it takes 1-2 weeks.'),
    ('amazon_e', 'Order 2: Amazon UK - electronics, motors, battery, wiring', ''),
    ('amazon', 'Order 3: Amazon UK - hull, hardware and supplies', 'Skip anything you already have (marked 🏠).'),
    ('ebay', 'Order 4: eBay UK - the two things Amazon is bad for', 'The pressure pipe and a used GoPro.'),
]


def core_items():
    rows = []
    for sub, item, spec, qty, unit, phase, owned, _, _ in B:
        if item in CORE_SKIPS:
            continue
        basket, links, check = WHERE[item]
        if item in CORE_OVERRIDE:
            spec, check = CORE_OVERRIDE[item]
        rows.append((sub, item, spec, qty, unit, phase, owned, basket, links, check))
    return rows + CORE_EXTRA


def main_core():
    rows = core_items()
    tot = lambda pred: sum(r[3] * r[4] for r in rows if pred(r))  # noqa: E731
    p1, p2, opt = tot(lambda r: r[5] == 1), tot(lambda r: r[5] == 2), tot(lambda r: r[5] == 'opt')
    own = tot(lambda r: r[5] in (1, 2) and r[6])
    L = ['# Minnow shopping list (no soldering)', '',
         'Everything needed to build Minnow **without soldering anything**, grouped by the shop you would order it '
         'from. The electronics are the [Minnow Core board](../pcb-core/README.md), which JLCPCB assembles '
         'completely; every other connection is a plug, a screw terminal, a lever connector or a crimp splice, and '
         'the 3D-printed parts need no heat-set inserts (screws cut their own thread, and the end-cap retainers use '
         'glued studs and nuts), so **nothing in the build needs a soldering iron or any other hot tool except a heat '
         'gun or lighter for the splices**. '
         'Generated by `bom/make_shopping_list.py` (the rev 1 build, which you solder, is in '
         '[`shopping_list_rev1.md`](shopping_list_rev1.md)).', '',
         '**About the links.** They are *search* links for the exact part, not links to one listing: listings on '
         'Amazon and eBay change weekly, and a search keeps working. Pick a listing that matches the '
         '"Check" column. Prices are rough UK prices (late 2026), delivered; check them before you buy.', '',
         '| | Cost |', '|---|---:|',
         f'| Phase 1: pool-ready sub with the 4K camera (incl. two assembled boards, about £{CORE_BOARDS_GBP:.0f}) '
         f'| £{p1:.0f} |',
         f'| Phase 2: two 868 MHz antennas for LoRa telemetry on a lake | £{p2:.0f} |',
         f'| **Everything, from scratch** | **£{p1 + p2:.0f}** |',
         f'| Items marked 🏠 that most makers already own | -£{own:.0f} |',
         f'| **Everything, if you have the usual supplies** | **£{p1 + p2 - own:.0f}** |',
         f'| Optional extras (second battery, charger, spare motor, paint, spray) | +£{opt:.0f} |',
         '| Tools you may need (crimper, stripper, heat gun, vacuum pump, hacksaw) | +£40-70 |', '',
         'Key: 🏠 = you probably already have it. **P2** = phase 2 (only needed for lake missions; can wait). '
         '**Opt** = optional.', '',
         '## How everything connects without solder', '',
         '| Connection | How |', '|---|---|',
         '| Battery to board | XT60 plug (already on the battery) |',
         '| Board to ESCs (power) | XT30 lead from the board, joined to the four ESC power leads with two Wago lever '
         'connectors |',
         '| ESC signal wires, GPS, depth sensor, leak probes, strobe, AUX | Screw terminals on the board: strip 5 mm, '
         'push in, tighten |',
         '| ESC motor wires to the thruster cables, cables to the motors | Heat-shrink crimp splices (crimp, then heat; '
         'the glue seals the ones in the water) |',
         '| Depth sensor | Pins already fitted, female-to-male jumper wires into the screw terminals |',
         '| Camera, antennas, laptop | Plugs: USB-A, U.FL, USB-C |', '']
    for key, title, blurb in CORE_BASKETS:
        L += [f'## {title}', '']
        if blurb:
            L += [blurb, '']
        if key == 'jlc':
            L += [f'About **£{CORE_BOARDS_GBP:.0f}** for two finished boards, delivered with VAT. Upload the three files '
                  'in [`pcb-core/output`](../pcb-core/output) (Gerbers, BOM, CPL) on the '
                  '[JLCPCB quote page](https://cart.jlcpcb.com/quote) and choose **Standard** PCB assembly, top side, '
                  'quantity 2. The step-by-step is in the '
                  '[Core board guide](../pcb-core/README.md#ordering-from-jlcpcb-step-by-step).', '']
            continue
        L += ['| ✓ | Qty | Item | Phase | ~£ | Links | Check |', '|---|---:|---|---|---:|---|---|']
        sub = 0.0
        for _, item, spec, qty, unit, phase, owned, basket, links, check in rows:
            if basket != key:
                continue
            tag = ' 🏠' if owned else ''
            ph = {1: '', 2: 'P2', 'opt': 'Opt'}[phase]
            cost = unit * qty
            if phase != 'opt':
                sub += cost
            ls = ' · '.join(link(sh, q) for sh, q in links)
            L.append(f'| ☐ | {qty} | **{item}**{tag}<br>{spec} | {ph} | {cost:.0f} | {ls} | {check} |')
        L += ['', f'Subtotal (without optional items): about **£{sub:.0f}**.', '']
    L += ['## Tools', '', '| ✓ | Tool | Cost | Links |', '|---|---|---|---|']
    for t, c, links in CORE_TOOLS:
        L.append(f"| ☐ | {t} | {c} | {' · '.join(link(sh, q) for sh, q in links)} |")
    L += ['', '## Not on this list', '',
          '* Leak probes: nothing to buy. Use two bare wire ends (an offcut of the thruster cable) per probe.',
          '* The relay buoy and underwater sound link discussed earlier are not designed yet.',
          '* Printed parts: they come out of the 1 kg of PETG above. See the print list in '
          '[`docs/01-mechanical.md`](../docs/01-mechanical.md#111-print-list).', '',
          '## Before you click buy', '',
          '1. Order the boards first: they take 1-2 weeks. Print the O-ring fit test while you wait.',
          '2. Measure the pipe as soon as it arrives (outside diameter in several places). If it is not 90.0 mm, '
          'change `pipe_od` in `cad/build_sub.py` before printing the end caps.',
          '3. Check the camera and the battery pack sizes against the CAD (`cam_*`, `batt_*` in `build_sub.py`) '
          'before printing the sled and cradle.']
    open(os.path.join(HERE, 'shopping_list.md'), 'w').write('\n'.join(L) + '\n')
    print(f'shopping_list.md (solder-free): p1 £{p1:.0f} p2 £{p2:.0f} own £{own:.0f} opt £{opt:.0f}')


if __name__ == '__main__':
    main()
    main_core()
