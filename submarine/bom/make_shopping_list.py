#!/usr/bin/env python3
"""
make_shopping_list.py - turns the parts list into a shopping list with links.

Writes shopping_list.md: every item in make_bom.py, every part on the main board
(../pcb/output/auv-mainboard-bom.csv) and the tools, grouped by the shop you would
order them from, with a checkbox, quantity, rough price and search links.

The links are SEARCH links, not links to single listings: listings on AliExpress,
eBay and Amazon change every week, while a search for the exact spec keeps working.
Prices and totals come from make_bom.py, so the two files always agree.
"""
import csv
import re
import os
from urllib.parse import quote_plus

from make_bom import B, TOOLS

HERE = os.path.dirname(os.path.abspath(__file__))
PCB_BOM = os.path.join(HERE, '..', 'pcb', 'output', 'auv-mainboard-bom.csv')

SEARCH = {
    'AliExpress': 'https://www.aliexpress.com/wholesale?SearchText={q}',
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
    'Pressure hull pipe': ('ebay', [('eBay UK', '90mm PVC pressure pipe PN10 1m'),
                                    ('Amazon UK', '90mm PVC pressure pipe')],
                           'Must be PRESSURE pipe (PN10, 4.3 mm wall), 90.0 mm outside. Not grey/white drain pipe.'),
    'O-rings': ('ebay', [('eBay UK', 'AS568-238 nitrile o-ring'), ('eBay UK', 'o-ring 89mm x 3.5mm nitrile'),
                         ('Amazon UK', 'AS568 238 o ring')],
                'Size 238 = 88.49 x 3.53 mm, NBR 70.'),
    'O-ring grease': ('amazon', [('Amazon UK', 'silicone o-ring grease'), ('Screwfix', 'silicone grease')],
                      'Silicone only. No Vaseline or petroleum grease.'),
    'Camera window': ('ebay', [('eBay UK', 'cast acrylic disc 80mm 8mm'), ('eBay UK', 'laser cut acrylic circle 8mm')],
                      'CAST acrylic, 80 mm across, 8 mm thick. Or send cad/drawings/window_80x8.dxf to a laser-cutting service.'),
    'Window sealant': ('local', [('Screwfix', 'clear neutral cure silicone'), ('B&Q', 'Sikaflex 291i')],
                       'Neutral cure (no vinegar smell).'),
    'Epoxy': ('amazon', [('Amazon UK', 'laminating epoxy resin small kit'), ('Amazon UK', '5 minute epoxy')],
              'One thin laminating epoxy + one 5-minute epoxy.'),
    'Cable glands': ('aliexpress', [('AliExpress', 'M12x1.5 nylon cable gland IP68 3-6.5mm'),
                                    ('Amazon UK', 'M12 cable gland IP68 nylon 10 pack')],
                     'Thread M12 x 1.5, cable range 3-6.5 mm.'),
    'Tap': ('amazon', [('Amazon UK', 'M12 x 1.5 tap'), ('eBay UK', 'M12 x 1.5 hand tap')],
            'M12 x 1.5 (fine pitch). Not the standard M12 x 1.75.'),
    'Vent / vacuum-test port': ('amazon', [('Amazon UK', '6mm OD silicone tube'), ('Amazon UK', 'M3 x 10 stainless screw')],
                                '6 mm outside diameter so it seals in a gland.'),
    'High-vis paint': ('local', [('B&Q', 'plastic primer spray'), ('B&Q', 'orange spray paint')], ''),
    # ---- structure
    'PETG filament': ('amazon', [('Amazon UK', 'PETG filament 1.75mm 1kg'), ('AliExpress', 'PETG filament 1.75mm 1kg')], ''),
    'Keel bar': ('ebay', [('eBay UK', 'aluminium flat bar 25mm x 3mm 1m'), ('B&Q', 'aluminium flat bar 25mm')],
                 'Aluminium, not steel (steel upsets the compass).'),
    'Sled rods': ('ebay', [('eBay UK', 'aluminium round tube 6mm 1m'), ('B&Q', 'aluminium tube 6mm')], ''),
    'M4 bolts': ('amazon', [('Amazon UK', 'M4 stainless socket cap screw assortment nyloc'),
                            ('Amazon UK', 'M4 x 30 stainless socket cap')],
                 'A2 stainless. You need 12 x M4x30 with nyloc nuts and washers.'),
    'M4 countersunk screws': ('amazon', [('Amazon UK', 'M4 x 12 countersunk stainless')], ''),
    'M3 screws': ('amazon', [('Amazon UK', 'M3 stainless socket cap screw assortment'),
                             ('Amazon UK', 'M3 x 20 stainless socket cap')],
                  'An M3 assortment box (6-20 mm) covers this line and the next.'),
    'M3 short screws': ('amazon', [('Amazon UK', 'M3 x 8 stainless socket cap')], 'M3 x 6 and M3 x 8.'),
    'Heat-set inserts': ('aliexpress', [('AliExpress', 'brass heat set insert M3 M4'),
                                        ('Amazon UK', 'heat set inserts M3 M4 brass')],
                         'For 3D prints (knurled brass).'),
    'Standoffs': ('amazon', [('Amazon UK', 'M3 x 20 brass hex standoff')], ''),
    'Ballast': ('ebay', [('eBay UK', 'lead shot 1kg'), ('eBay UK', 'fishing lead shot')], 'Lead, not steel shot.'),
    'Straps, ties, foam': ('amazon', [('Amazon UK', 'velcro battery strap'), ('Amazon UK', 'black EVA foam sheet 3mm')], ''),
    # ---- propulsion
    'Thruster motors': ('aliexpress', [('AliExpress', 'A2212 1000KV brushless motor'),
                                       ('eBay UK', 'A2212 1000KV brushless motor')],
                        '1000KV, with the prop adapter. Buy 4 (5 with the spare).'),
    'Spare motor': ('aliexpress', [('AliExpress', 'A2212 1000KV brushless motor')], 'Add to the same order as the other four.'),
    '4-in-1 ESC': ('aliexpress', [('AliExpress', '4 in 1 ESC 45A BLHeli_S 30.5mm DShot'),
                                  ('AliExpress', '4 in 1 ESC AM32 30.5mm'),
                                  ('eBay UK', '4 in 1 ESC 30.5mm')],
                   'BLHeli_S, Bluejay or AM32 (NOT BLHeli_32 only, NOT an 8-bit PWM-only ESC), 2-6S, 30.5 mm hole spacing.'),
    'Thruster cable': ('local', [('Screwfix', '3 core flex 0.5mm'), ('eBay UK', '3 core 0.5mm round flex cable')],
                       'Round, about 5.5 mm across, so the glands seal on it.'),
    'Heat-shrink': ('amazon', [('Amazon UK', 'adhesive lined heat shrink assortment')], 'Adhesive-lined (glue inside).'),
    'Corrosion inhibitor': ('amazon', [('Amazon UK', 'ACF-50'), ('Amazon UK', 'Corrosion-X')], ''),
    # ---- power
    'Battery': ('ebay', [('eBay UK', '3S1P 18650 battery pack BMS XT60'), ('eBay UK', '11.1V 18650 pack 3S BMS'),
                         ('AliExpress', '3S1P 18650 pack BMS')],
                'Must have a BMS (protection board) and branded cells (Samsung, Molicel, LG, Sony). Max 65 x 56 x 19 mm to fit the sled.'),
    'Second battery pack': ('ebay', [('eBay UK', '3S1P 18650 battery pack BMS XT60')], 'Identical to the first pack.'),
    'Charger': ('amazon', [('Amazon UK', '12.6V 2A lithium charger'), ('Amazon UK', 'XT60 charge lead')], ''),
    # ---- electronics
    'Microcontroller': ('aliexpress', [('AliExpress', 'ESP32-S3-DevKitC-1 N16R8'), ('The Pi Hut', 'ESP32-S3-DevKitC-1'),
                                       ('Amazon UK', 'ESP32-S3-DevKitC-1 N16R8')],
                        'Must be the DevKitC-1 layout: 2 x 22 pins, two USB-C ports. Other ESP32-S3 boards will not fit the socket.'),
    'Main board PCB': ('jlc', [], ''),
    'Main board components': ('lcsc', [], ''),
    'GPS': ('aliexpress', [('AliExpress', 'Beitian BN-220 GPS'), ('eBay UK', 'BN-220 GPS')], 'BN-220 is 22 x 20 mm; the mast is sized for it.'),
    'IMU / compass': ('aliexpress', [('AliExpress', 'BNO085 module'), ('The Pi Hut', 'BNO085'), ('Amazon UK', 'BNO085')],
                      'BNO085 (or BNO086). Not the BNO055: the firmware is written for the 085.'),
    'Depth + water temp': ('aliexpress', [('AliExpress', 'MS5837-30BA module'), ('AliExpress', 'MS5837-30BA waterproof sensor')],
                           '30BA (30 bar) version, not 02BA.'),
    'Hull monitor': ('aliexpress', [('AliExpress', 'BME280 module 3.3V I2C'), ('Amazon UK', 'BME280 breakout')],
                     'BME280, not BMP280 (the BMP has no humidity sensor).'),
    'Magnet switch': ('amazon', [('Amazon UK', 'reed switch normally open glass'), ('Amazon UK', 'N52 neodymium magnet with hole')], ''),
    'Strobe': ('amazon', [('Amazon UK', '1W white LED star'), ('Amazon UK', '47 ohm 1W resistor')], ''),
    'Leak probes': ('amazon', [('Amazon UK', 'stripboard')], 'Or two bare wires per probe, on the JST leads from Order 1.'),
    'Connectors & wire': ('aliexpress', [('AliExpress', 'JST PH 2.0 pre-crimped cable 2pin 4pin 5pin 7pin'),
                                         ('AliExpress', 'JST XH 2.54 2pin cable'),
                                         ('Amazon UK', '14 AWG silicone wire'), ('Amazon UK', '26 AWG hook up wire')],
                         'PH = 2.0 mm pitch (2, 4, 5 and 7 pin). XH = 2.5 mm pitch (2 pin).'),
    'Camera power socket': ('aliexpress', [('AliExpress', 'USB A female breakout board'), ('Amazon UK', 'USB A female breakout')], ''),
    # ---- camera
    '4K camera': ('ebay', [('eBay UK', 'GoPro HERO5 Black'), ('CeX', 'GoPro HERO5 Black'),
                           ('eBay UK', 'GoPro HERO6 Black'), ('eBay UK', 'GoPro HERO7 Black')],
                  'BLACK edition (Session and White models do not record 4K or fit the cradle). A dead battery is fine.'),
    'microSD card': ('amazon', [('Amazon UK', '64GB microSD U3 V30')], 'U3 / V30. Branded (SanDisk, Samsung, Kingston).'),
    'USB cable': ('amazon', [('Amazon UK', 'short USB A to USB C cable 20cm')], ''),
    # ---- LoRa (phase 2)
    'LoRa radios': ('aliexpress', [('AliExpress', 'Ebyte E220-900T22D'), ('eBay UK', 'E220-900T22D')],
                    'E220-900T22D exactly (868/915 MHz, DIP pins). Not the 400 MHz E220-400.'),
    'Sub antenna': ('aliexpress', [('AliExpress', '868MHz FPC antenna IPEX'), ('AliExpress', 'IPEX u.FL to SMA male pigtail RG178')], ''),
    'Shore antenna': ('aliexpress', [('AliExpress', '868MHz SMA antenna')], '868 MHz, SMA male.'),
    'USB-serial adapter': ('aliexpress', [('AliExpress', 'CH340 USB TTL 3.3V'), ('Amazon UK', 'CP2102 USB TTL')],
                           'Must have a 3.3 V option.'),
}

BASKETS = [
    ('aliexpress', 'Order 1: AliExpress (slowest, 1-3 weeks, so order first)',
     'Motors, ESC, ESP32, sensors and radios. Put it all in one basket to combine shipping.'),
    ('jlc', 'Order 2: JLCPCB (the main board) - about £14', ''),
    ('lcsc', 'Order 3: LCSC (parts for the main board) - about £15',
     'LCSC belongs to JLCPCB: if you order both on the same day you can often combine them into one parcel.'),
    ('ebay', 'Order 4: eBay UK', 'Pipe, O-rings, window, aluminium, lead, batteries and the camera.'),
    ('amazon', 'Order 5: Amazon UK', 'Screws, glue, grease and small supplies. Skip anything you already have.'),
    ('local', 'Order 6: Screwfix / B&Q (or any DIY shop)', 'Can be picked up the same day.'),
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
            f"**Cheaper shortcut for the resistors and capacitors:** an 0805 resistor + capacitor sample book "
            f"({link('AliExpress', '0805 resistor capacitor sample book')}) covers every R and C on the board, "
            'and leaves you spares for the next project.']
    return out


def main():
    tot = lambda pred: sum(r[3] * r[4] for r in B if pred(r))  # noqa: E731
    p1, p2, opt = tot(lambda r: r[5] == 1), tot(lambda r: r[5] == 2), tot(lambda r: r[5] == 'opt')
    own = tot(lambda r: r[5] in (1, 2) and r[6])
    missing = [r[1] for r in B if r[1] not in WHERE]
    assert not missing, f'no shop for {missing}'

    L = ['# Minnow shopping list', '',
         'Everything needed to build the regular Minnow design, grouped by the shop you would order it from. '
         'Generated by `bom/make_shopping_list.py` from the same data as [`bom.csv`](bom.csv), so quantities and '
         'prices match the parts list.', '',
         '**About the links.** They are *search* links for the exact part, not links to one listing: listings on '
         'AliExpress, eBay and Amazon change weekly, and a search keeps working. Pick a listing that matches the '
         '"Check" column. Prices are rough UK prices (late 2026), delivered; check them before you buy.', '',
         '| | Cost |', '|---|---:|',
         f'| Phase 1: pool-ready sub with the 4K camera | £{p1:.0f} |',
         f'| Phase 2: LoRa telemetry for lake missions | £{p2:.0f} |',
         f'| **Everything, from scratch** | **£{p1 + p2:.0f}** |',
         f'| Items marked 🏠 that most makers already own | -£{own:.0f} |',
         f'| **Everything, if you have the usual supplies** | **£{p1 + p2 - own:.0f}** |',
         f'| Optional extras (second battery, charger, spare motor, paint, spray) | +£{opt:.0f} |',
         '| Vacuum pump for leak testing (tool, strongly recommended) | +£18 |', '',
         'Key: 🏠 = you probably already have it. **P2** = phase 2 (only needed for lake missions; can wait). '
         '**Opt** = optional.', '']

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
          f"{link('Screwfix', 'plastic pipe cutter')} · {link('Amazon UK', 'deburring tool')} |",
          f"| ☐ | Heat-set insert tip for the soldering iron (M3/M4) | about £5 if needed | "
          f"{link('Amazon UK', 'heat set insert tip soldering iron')} |"]
    L += [f'| | {t} | {c} | |' for t, c in TOOLS if c == 'assumed']
    L += ['',
          '## Not on this list', '',
          '* The relay buoy and underwater sound link discussed earlier: they are not designed yet, so there are no '
          'parts to buy for them. Pool and lake missions with LoRa work without them.',
          '* Printed parts: they come out of the 1 kg of PETG above. See the print list in '
          '[`docs/01-mechanical.md`](../docs/01-mechanical.md#111-print-list).', '',
          '## Before you click buy', '',
          '1. Order AliExpress and the PCB first: they take 1-3 weeks. Print the O-ring fit test while you wait.',
          '2. Measure the pipe as soon as it arrives (outside diameter in several places). If it is not 90.0 mm, '
          'change `pipe_od` in `cad/build_sub.py` before printing the end caps.',
          '3. Check the camera and the battery pack sizes against the CAD (`cam_*`, `batt_*` in `build_sub.py`) '
          'before printing the sled and cradle.']
    open(os.path.join(HERE, 'shopping_list.md'), 'w').write('\n'.join(L) + '\n')
    print(f'shopping_list.md: p1 £{p1:.0f} p2 £{p2:.0f} own £{own:.0f} opt £{opt:.0f}')


if __name__ == '__main__':
    main()
