#!/usr/bin/env python3
"""
make_bom.py - the complete bill of materials for the Minnow AUV.

Writes bom.csv (every part) and bom_summary.md (totals by subsystem and phase).
Prices are rough UK prices for one-off hobby quantities in late 2026, delivered
(AliExpress / eBay UK / Amazon UK / UK hobby shops). Check before you buy.

phase: 1 = needed for the first pool-ready autonomous sub with the 4K camera,
       2 = lake operations (long-range LoRa telemetry), opt = optional upgrade.
own:   True if most makers already have it (filament, screws, glue, wire...).
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))

#  (subsystem, item, specification / what to search for, qty, unit GBP, phase, own, where, notes)
B = [
    # ------------------------------------------------------------------ hull
    ('Hull & seals', 'Pressure hull pipe', 'PVC-U pressure pipe 90 mm OD, PN10 (4.3 mm wall), 1 m length', 1, 10.00, 1, False,
     'pond / irrigation pipe supplier, eBay UK', 'Cut to 380 mm, square ends, 15 deg x 1.5 mm chamfer on the outside edges. Spare for a 2nd try.'),
    ('Hull & seals', 'O-rings', 'AS568-238 (88.49 x 3.53 mm) or metric 89 x 3.5 mm, NBR 70 Shore A', 6, 0.85, 1, False,
     'O-ring supplier (eBay UK)', '2 per end cap + 2 spares. Grooves are sized for a 90.0 mm pipe OD.'),
    ('Hull & seals', 'O-ring grease', 'Silicone O-ring / plumber\'s grease (e.g. Molykote 111), 10-30 g', 1, 4.00, 1, True,
     'Screwfix / Amazon UK', 'Never use petroleum grease on NBR O-rings.'),
    ('Hull & seals', 'Camera window', 'Cast acrylic disc 80 mm dia x 8 mm, laser cut, clear (CAST, not extruded)', 1, 6.00, 1, False,
     'UK laser-cutting service (eBay)', 'Send window_80x8.svg / .dxf from cad/drawings.'),
    ('Hull & seals', 'Window sealant', 'Clear neutral-cure silicone or Sikaflex-291i', 1, 4.00, 1, True,
     'Screwfix / B&Q', 'Bed the window into its recess; the nose ring lip also retains it.'),
    ('Hull & seals', 'Epoxy', '2-part epoxy: thin laminating epoxy (coat printed caps) + 5-min epoxy (potting)', 1, 7.00, 1, True,
     'Amazon UK', 'Coat the OUTSIDE of the printed caps and fill the mast. Keep it out of the O-ring grooves.'),
    ('Hull & seals', 'Cable glands', 'Nylon IP68 cable gland M12 x 1.5, cable 3-6.5 mm (pack of 10)', 1, 4.00, 1, False,
     'Amazon UK / AliExpress', '7 used in the rear cap (4 thrusters, mast cable, LoRa coax, vent tube).'),
    ('Hull & seals', 'Tap', 'M12 x 1.5 hand tap (plug)', 1, 5.00, 1, False, 'Amazon UK',
     'Tap the 7 printed 10.5 mm holes in the rear cap; screw glands in with a smear of silicone.'),
    ('Hull & seals', 'Vent / vacuum-test port', '6 mm silicone tube 30 cm + stainless M3x10 plug screw + zip tie', 1, 2.00, 1, False,
     'Amazon UK', 'Tube through one gland; pump a vacuum, then plug it. Optional brass mini ball valve (+GBP 5).'),
    ('Hull & seals', 'High-vis paint', 'Plastic primer + orange spray paint', 1, 6.00, 'opt', False, 'B&Q',
     'Makes the hull easy to find. Mask the last 35 mm of each pipe end (O-ring seal area).'),
    # ------------------------------------------------------------------ structure
    ('Structure', 'PETG filament', 'PETG 1.75 mm, 1 kg (black or orange)', 1, 15.00, 1, True,
     'any', 'All printed parts need about 1.0 kg (see cad/print_list.json). Buy 2 kg if you expect reprints.'),
    ('Structure', 'Keel bar', 'Aluminium flat bar 25 x 3 mm, 1 m (cut to 370 mm, drill 4.5 mm holes every 20 mm)', 1, 5.00, 1, False,
     'B&Q / eBay', 'Non-magnetic, keeps the compass happy.'),
    ('Structure', 'Sled rods', 'Aluminium round tube 6 mm OD, 1 m (cut two at 312 mm)', 1, 3.00, 1, False, 'B&Q / eBay', ''),
    ('Structure', 'M4 bolts', 'A2 stainless M4 x 30 socket cap + nyloc nut + 2 washers', 12, 0.25, 1, True, 'Amazon UK assortment',
     '8 through the thruster tabs + clamp ears, 4 pinch bolts on the front clamp.'),
    ('Structure', 'M4 countersunk screws', 'A2 stainless M4 x 12 countersunk', 10, 0.15, 1, True, 'Amazon UK',
     'Keel bar to clamps (6) and ballast pods to keel (4). They cut their own thread in the printed parts.'),
    ('Structure', 'M3 studs', 'A2 stainless M3 threaded rod, 300 mm (cut into 8 studs of 26 mm with a hacksaw) '
     '+ 8 M3 nuts + 8 washers', 1, 3.00, 1, False, 'Amazon UK',
     'Glued into the nose ring and tail cone flanges with 5-minute epoxy; the nuts go on the clamp side.'),
    ('Structure', 'M3 short screws', 'A2 stainless M3 x 6 / x 8 / x 10 (motors, mast, PCB, ESC, sled)', 30, 0.06, 1, True,
     'Amazon UK', '16 motor screws, 2 mast (M3 x 10), 5 PCB, 4 ESC, 3 sled. The mast screws cut their own thread '
     'in the printed pad.'),
    ('Structure', 'Standoffs', 'Brass M3 x 20 hex standoffs, male-female (rear cap bosses to sled plate)', 3, 0.30, 1,
     True, 'Amazon UK', 'The male end cuts its own thread in the printed boss: no inserts, no heat.'),
    ('Structure', 'Ballast', 'Lead shot (fishing / reloading), 1 kg', 1, 8.00, 1, False, 'tackle shop / eBay UK',
     'About 580 g is needed (cad/trim_report.md). Lead is non-magnetic - steel ballast would upset the compass.'),
    ('Structure', 'Straps, ties, foam', 'Velcro battery straps, small zip ties, 3 mm black EVA foam sheet', 1, 4.00, 1, True, 'Amazon UK',
     'Foam behind the camera and as the anti-glare ring around the lens.'),
    # ------------------------------------------------------------------ propulsion
    ('Propulsion', 'Thruster motors', 'A2212 1000KV brushless outrunner with prop adapter (runs wet in fresh water)', 4, 4.50, 1, False,
     'AliExpress / eBay', 'Rinse in fresh water and spray with corrosion inhibitor after every session.'),
    ('Propulsion', 'Spare motor', 'A2212 1000KV', 1, 4.50, 'opt', False, 'AliExpress', ''),
    ('Propulsion', '4-in-1 ESC', '4-in-1 ESC 35-45 A, 2-6S, BLHeli_S / Bluejay / AM32, DShot, 30.5 mm mount', 1, 20.00, 1, False,
     'AliExpress / UK drone shops', 'Firmware puts it in 3D (reversible) mode with DShot commands 10 + 12.'),
    ('Propulsion', 'Thruster cable', '3-core 0.5 mm2 round flexible cable (about 5.5 mm OD), 3 m', 1, 4.00, 1, False,
     'Screwfix / eBay', '4 runs: ~0.6 m each (rear cap to motor) plus spare.'),
    ('Propulsion', 'Heat-shrink', 'Adhesive-lined (marine) heat-shrink assortment', 1, 3.00, 1, True, 'Amazon UK',
     'Seal every wet splice.'),
    ('Propulsion', 'Corrosion inhibitor', 'ACF-50 / Corrosion-X / silicone spray', 1, 6.00, 'opt', True, 'Amazon UK', ''),
    # ------------------------------------------------------------------ power
    ('Power', 'Battery', '3S1P 18650 Li-ion pack 11.1 V ~3.0-3.5 Ah with BMS and XT60 (female) lead', 1, 20.00, 1, False,
     'UK battery shop (e.g. custom pack) / eBay', 'Use reputable cells (Samsung 35E / Molicel). Charge OUTSIDE the hull.'),
    ('Power', 'Second battery pack', 'Same 3S1P pack, used in parallel (or a 3S2P pack)', 1, 20.00, 'opt', False, '',
     'Doubles runtime (the CAD and trim report show two packs fitted).'),
    ('Power', 'Charger', '12.6 V 2 A Li-ion charger + XT60 lead (or any hobby balance charger)', 1, 9.00, 'opt', True, 'Amazon UK', ''),
    # ------------------------------------------------------------------ electronics
    ('Electronics', 'Microcontroller', 'Espressif ESP32-S3-DevKitC-1 (N8R8 or N16R8)', 1, 9.00, 1, False,
     'AliExpress / The Pi Hut', 'Plugs into the main board. Program it through the port marked UART.'),
    ('Electronics', 'Main board PCB', 'Fabricate pcb/output/auv-mainboard-gerbers.zip: 2 layers, 1.6 mm, 150 x 60 mm, 5 pcs', 1, 14.00, 1, False,
     'JLCPCB / PCBWay (incl. UK VAT + shipping)', 'Any colour. HASL lead-free is fine.'),
    ('Electronics', 'Main board components', 'Everything in pcb/output/auv-mainboard-bom.csv (81 parts, mostly 0805 / SOT-23)', 1, 15.00, 1, False,
     'LCSC / AliExpress / Farnell', 'Includes XT60/XT30, fuse clips + 15 A fuse, LM2596S-5, FETs, JST connectors, headers.'),
    ('Electronics', 'GPS', 'Beitian BN-220 (u-blox M8 class, UART, built-in antenna)', 1, 9.00, 1, False, 'AliExpress / eBay',
     'Lives in the mast; 4-wire cable through the rear cap.'),
    ('Electronics', 'IMU / compass', 'BNO085 9-DoF breakout (Adafruit 4754 or GY-BNO08X)', 1, 12.00, 1, False, 'AliExpress / The Pi Hut',
     'Mount flat and square on the IMU bracket.'),
    ('Electronics', 'Depth + water temp', 'MS5837-30BA pressure sensor module (or a potted "Bar30"-style M10 sensor, +GBP 10)', 1, 11.00, 1, False,
     'AliExpress', 'Through the centre of the rear cap; pot the module in an M10 hollow bolt if you buy the bare board.'),
    ('Electronics', 'Hull monitor', 'BME280 breakout (pressure, humidity, temperature inside the hull)', 1, 3.00, 1, False, 'AliExpress',
     'Early leak warning + automatic vacuum-hold check before every dive.'),
    ('Electronics', 'Magnet switch', 'Glass reed switch (normally open) + N52 neodymium magnet with lanyard', 1, 3.00, 1, False, 'Amazon UK',
     'Reed switch glued inside the hull top under the white target ring.'),
    ('Electronics', 'Strobe', 'White LED (0.5-1 W) + 47 ohm 1 W resistor, potted in the mast top', 1, 1.00, 1, True, 'any', ''),
    ('Electronics', 'Leak probes', 'Two small pieces of stripboard or bare copper wire pairs + 2-pin JST lead each', 2, 0.50, 1, True, 'DIY',
     'At the lowest point, one at each end of the hull.'),
    ('Electronics', 'Connectors & wire', 'JST PH 2/4/5/7-pin + XH 2-pin pre-crimped leads, 14 AWG silicone (power), 26 AWG hook-up', 1, 8.00, 1, True,
     'AliExpress / Amazon UK', ''),
    ('Electronics', 'Camera power socket', 'USB-A female breakout board (bridge D+ to D- so the camera may draw >0.5 A)', 1, 1.00, 1, False,
     'AliExpress', 'Wired to the CAMERA 5V connector J14.'),
    # ------------------------------------------------------------------ camera
    ('4K camera', '4K camera', 'GoPro HERO5 Black (used) - native 4K30, waterproof on its own, Wi-Fi control. HERO6/7 Black fit the same cradle.', 1, 50.00, 1, False,
     'eBay UK / CeX', 'Budget alternative: any action camera that records NATIVE 3840x2160 (adjust the cradle numbers).'),
    ('4K camera', 'microSD card', '64 GB U3 / V30 microSD', 1, 7.00, 1, True, 'any', '4K30 at 60 Mb/s = about 27 GB per hour.'),
    ('4K camera', 'USB cable', 'Short USB-A to USB-C cable (20 cm)', 1, 2.00, 1, True, 'any', 'Powers the camera from the sub so it can record for hours.'),
    # ------------------------------------------------------------------ telemetry (phase 2)
    ('LoRa telemetry', 'LoRa radios', 'Ebyte E220-900T22D (868 MHz, UART) - one in the sub, one on the shore', 2, 7.00, 2, False, 'AliExpress',
     'GPS position + status every few seconds when surfaced, km range over water.'),
    ('LoRa telemetry', 'Sub antenna', '868 MHz FPC (stick-on) antenna with u.FL + u.FL-to-SMA-male RG178 pigtail 30 cm', 1, 4.00, 2, False, 'AliExpress',
     'Potted in the mast; coax goes through its own gland.'),
    ('LoRa telemetry', 'Shore antenna', '868 MHz SMA rubber-duck antenna', 1, 3.00, 2, False, 'AliExpress', ''),
    ('LoRa telemetry', 'USB-serial adapter', 'CH340 or CP2102 USB-TTL adapter (3.3 V logic) for the shore radio', 1, 3.00, 2, True, 'AliExpress',
     'Plug into a laptop or phone (OTG); see docs/04-software.md (shore station).'),
]

TOOLS = [
    ('3D printer that prints PETG (bed 220 x 220 mm is enough)', 'assumed'),
    ('Soldering iron, solder, flux, multimeter', 'assumed'),
    ('Hacksaw + mitre box or pipe cutter, file / deburring tool', 'about GBP 10 if needed'),
    ('Drill + 4.2 mm and 3.2 mm bits', 'assumed'),
    ('Hand vacuum pump with gauge (brake-bleeder type) - strongly recommended for leak testing', 'about GBP 18'),
    ('Kitchen scale (ballast and trim)', 'assumed'),
    ('Small bucket / bath for the first wet tests', 'assumed'),
]


def main():
    rows = []
    for sub, item, spec, qty, unit, phase, own, where, notes in B:
        rows.append(dict(subsystem=sub, item=item, specification=spec, qty=qty, unit_gbp=f'{unit:.2f}',
                         total_gbp=f'{unit * qty:.2f}', phase=phase, likely_owned='yes' if own else '',
                         where_to_buy=where, notes=notes))
    with open(os.path.join(HERE, 'bom.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    subs = []
    for r in B:
        if r[0] not in subs:
            subs.append(r[0])
    tot = lambda pred: sum(r[3] * r[4] for r in B if pred(r))  # noqa: E731
    lines = ['# Budget summary', '',
             'Generated by `bom/make_bom.py` from the full parts list in `bom.csv`. Rough UK prices (late 2026), '
             'delivered, one-off quantities. Check current prices before ordering.', '',
             '| Subsystem | Phase 1 (pool-ready, 4K camera) | Phase 2 (LoRa, lake ops) | Optional extras |',
             '|---|---:|---:|---:|']
    for s in subs:
        lines.append(f"| {s} | £{tot(lambda r: r[0] == s and r[5] == 1):.0f} | £{tot(lambda r: r[0] == s and r[5] == 2):.0f} | "
                     f"£{tot(lambda r: r[0] == s and r[5] == 'opt'):.0f} |")
    p1 = tot(lambda r: r[5] == 1)
    p2 = tot(lambda r: r[5] == 2)
    opt = tot(lambda r: r[5] == 'opt')
    owned1 = tot(lambda r: r[5] == 1 and r[6])
    owned2 = tot(lambda r: r[5] == 2 and r[6])
    lines += [f'| **Total** | **£{p1:.0f}** | **£{p2:.0f}** | £{opt:.0f} |', '',
              f'* Phase 1 + Phase 2 (everything needed to run lake missions): **£{p1 + p2:.0f}**.',
              f'* Of that, about **£{owned1 + owned2:.0f}** is stuff most makers already have (filament, screws, glue, '
              f'grease, wire, SD card...). If you have it, the build costs about **£{p1 + p2 - owned1 - owned2:.0f}**.',
              f'* Phase 1 alone if you already own the basics: **£{p1 - owned1:.0f}**.', '',
              '## Tools (not included above)', '', '| Tool | Cost |', '|---|---|']
    lines += [f'| {t} | {c} |' for t, c in TOOLS]
    lines += ['', '## Ways to save money if prices come in high', '',
              '* Buy a used GoPro HERO5 Black with a dead battery: the sub powers the camera over USB anyway.',
              '* Use the bare MS5837 module and pot it yourself instead of a ready-made Bar30 clone.',
              '* Skip LoRa at first (phase 2): pool testing works without it.',
              '* Order the PCB components from LCSC together with the boards (one shipping charge).',
              '* Print the pods and sled at lower infill; only the end caps, clamps and ducts must be solid.']
    open(os.path.join(HERE, 'bom_summary.md'), 'w').write('\n'.join(lines) + '\n')
    print(f'phase1 £{p1:.2f}  phase2 £{p2:.2f}  optional £{opt:.2f}  owned(p1+p2) £{owned1 + owned2:.2f}  '
          f'net £{p1 + p2 - owned1 - owned2:.2f}  rows {len(rows)}')


if __name__ == '__main__':
    main()
