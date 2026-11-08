"""
design.py - single source of truth for the Minnow AUV main board.

Every component is listed once here with its schematic symbol, footprint,
pin -> net connections, PCB placement and BOM information. generate_board.py
turns this into the KiCad schematic, the KiCad PCB, the BOM and the files the
Blender model reads, so the schematic and the board can never disagree.

Board coordinates (bx, by) are in mm: bx runs from the REAR edge (0) to the
FRONT edge (150) of the board, by from the PORT edge (0) to the STARBOARD
edge (60). KiCad X = 100 + bx, KiCad Y = 100 + by.
"""

BOARD_W = 150.0   # along the hull
BOARD_H = 60.0    # across the hull
TITLE = 'Minnow AUV main board'
REV = '1.0'

# ---------------------------------------------------------------------------
# ESP32-S3-DevKitC-1 pin map (verified against Espressif's user guide v1.1:
# J1 = 3V3,3V3,RST,4,5,6,7,15,16,17,18,8,3,46,9,10,11,12,13,14,5V,G
# J3 = G,TX,RX,1,2,42,41,40,39,38,37,36,35,0,45,48,47,21,20,19,G,G)
# Footprint pad n = J1 pin n, pad 22+n = J3 pin n.
# ---------------------------------------------------------------------------
DEVKIT_J1 = ['3V3', '3V3', 'RST', 'GPIO4', 'GPIO5', 'GPIO6', 'GPIO7', 'GPIO15', 'GPIO16', 'GPIO17',
             'GPIO18', 'GPIO8', 'GPIO3', 'GPIO46', 'GPIO9', 'GPIO10', 'GPIO11', 'GPIO12', 'GPIO13',
             'GPIO14', '5V', 'GND']
DEVKIT_J3 = ['GND', 'TX/GPIO43', 'RX/GPIO44', 'GPIO1', 'GPIO2', 'GPIO42', 'GPIO41', 'GPIO40', 'GPIO39',
             'GPIO38', 'GPIO37', 'GPIO36', 'GPIO35', 'GPIO0', 'GPIO45', 'GPIO48', 'GPIO47', 'GPIO21',
             'GPIO20', 'GPIO19', 'GND', 'GND']

GPIO_NET = {
    # ADC1 (usable with Wi-Fi on)
    'GPIO1': 'VBAT_SENSE', 'GPIO2': 'ESC_CURR_F', 'GPIO4': 'LEAK_F', 'GPIO5': 'LEAK_R', 'GPIO6': 'MAG_SENSE',
    # sensors and radios
    'GPIO7': 'IMU_INT', 'GPIO8': 'SDA', 'GPIO9': 'SCL',
    'GPIO15': 'LORA_RXD', 'GPIO16': 'LORA_TXD', 'GPIO17': 'GPS_RXD', 'GPIO18': 'GPS_TXD',
    'GPIO39': 'LORA_M0', 'GPIO40': 'LORA_M1', 'GPIO41': 'LORA_AUX',
    # thrusters (DShot via the RMT peripheral)
    'GPIO11': 'ESC_M1', 'GPIO12': 'ESC_M2', 'GPIO13': 'ESC_M3', 'GPIO10': 'ESC_M4',
    # camera, outputs, power latch
    'GPIO14': 'CAM_EN', 'GPIO42': 'CAM_BTN_A', 'GPIO47': 'CAM_BTN_B',
    'GPIO3': 'AUX1_EN', 'GPIO45': 'AUX2_EN', 'GPIO21': 'PWR_HOLD',   # GPIO46 left free (spare)
}


def devkit_pins():
    pins = {}
    for i, name in enumerate(DEVKIT_J1, start=1):
        pins[str(i)] = name
    for i, name in enumerate(DEVKIT_J3, start=1):
        pins[str(22 + i)] = name
    nets = {}
    for pad, name in pins.items():
        if name == '3V3':
            nets[pad] = '+3V3'
        elif name == '5V':
            nets[pad] = 'DEVKIT_5V'
        elif name == 'GND':
            nets[pad] = 'GND'
        elif name in GPIO_NET:
            nets[pad] = GPIO_NET[name]
        else:
            nets[pad] = None          # not connected
    return pins, nets


DEVKIT_PIN_NAMES, DEVKIT_NETS = devkit_pins()

# ---------------------------------------------------------------------------
# Component table
# sym: KiCad symbol lib_id    fp: footprint lib_id
# pins: {pin number: net}     pcb: (bx, by, rotation_deg)
# blk: schematic block        mpn: suggested part / notes for the BOM
# ---------------------------------------------------------------------------
R0805 = 'Resistor_SMD:R_0805_2012Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
C1206 = 'Capacitor_SMD:C_1206_3216Metric'
SOT23 = 'Package_TO_SOT_SMD:SOT-23'
PH = 'Connector_JST:JST_PH_B{n}B-PH-K_1x{n:02d}_P2.00mm_Vertical'
XH2 = 'Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical'


def R(ref, val, a, b, pcb, blk, mpn='0805 1% thick film'):
    return dict(ref=ref, sym='Device:R', val=val, fp=R0805, pins={'1': a, '2': b}, pcb=pcb, blk=blk, mpn=mpn)


def C(ref, val, a, b, pcb, blk, fp=C0805, mpn='0805 X7R 50V'):
    return dict(ref=ref, sym='Device:C', val=val, fp=fp, pins={'1': a, '2': b}, pcb=pcb, blk=blk, mpn=mpn)


def NFET(ref, g, s, d, pcb, blk):
    return dict(ref=ref, sym='Device:Q_NMOS_GSD', val='AO3400A', fp=SOT23, pins={'1': g, '2': s, '3': d},
                pcb=pcb, blk=blk, mpn='AO3400A N-MOSFET 30V 5.7A SOT-23 (logic level)')


def conn(ref, n, nets, pcb, blk, val, xh=False, mpn=None):
    fp = XH2 if xh else PH.format(n=n)
    return dict(ref=ref, sym=f'Connector_Generic:Conn_01x{n:02d}', val=val, fp=fp,
                pins={str(i + 1): net for i, net in enumerate(nets)}, pcb=pcb, blk=blk,
                mpn=mpn or (f'JST XH {n}-pin vertical B{n}B-XH-A' if xh else f'JST PH {n}-pin vertical B{n}B-PH-K'))


PARTS = [
    # ---------------- power entry, fuse, soft-latch high-side switch --------------
    dict(ref='J1', sym='Connector_Generic:Conn_01x02', val='BATTERY XT60', fp='Connector_AMASS:AMASS_XT60PW-M_1x02_P7.20mm_Horizontal',
         pins={'1': 'GND', '2': 'VBAT_IN'}, pcb=(17.5, 37.0, 90), blk='power', mpn='AMASS XT60PW-M (male, PCB, right angle)'),
    dict(ref='F1', sym='Device:Fuse', val='15A ATO', fp='Fuse:Fuseholder_Blade_ATO_Littelfuse_Pudenz_2_Pin',
         pins={'1': 'VBAT_IN', '2': 'VBAT_F'}, pcb=(25.0, 29.8, 90), blk='power', mpn='ATO/ATC PCB fuse clip pair + 15 A blade fuse'),
    dict(ref='Q1', sym='Device:Q_PMOS_GDS', val='AOD4185', fp='Package_TO_SOT_SMD:TO-252-2',
         pins={'1': 'PFET_G', '2': 'VSYS', '3': 'VBAT_F'}, pcb=(38.0, 18.0, 0), blk='power',
         mpn='AOD4185 P-MOSFET -40V -40A DPAK (or SQD40031EL / IPD50P04P4L-11)'),
    dict(ref='Q2', sym='Device:Q_PMOS_GDS', val='AOD4185', fp='Package_TO_SOT_SMD:TO-252-2',
         pins={'1': 'PFET_G', '2': 'VSYS', '3': 'VBAT_F'}, pcb=(38.0, 27.5, 0), blk='power',
         mpn='second FET in parallel halves the heat (optional for <8 A)'),
    R('R1', '100k', 'PFET_G', 'VBAT_F', (33.0, 11.5, 0), 'power'),
    C('C1', '100nF', 'PFET_G', 'VBAT_F', (33.0, 8.5, 0), 'power', mpn='0805 X7R 50V (soft start)'),
    dict(ref='D1', sym='Device:D_Zener', val='BZT52C15', fp='Diode_SMD:D_SOD-123', pins={'1': 'VBAT_F', '2': 'PFET_G'},
         pcb=(38.5, 11.5, 0), blk='power', mpn='BZT52C15 15 V Zener SOD-123 (gate clamp)'),
    R('R2', '10k', 'PFET_G', 'LATCH_D', (38.5, 8.5, 0), 'power'),
    NFET('Q3', 'LATCH_G', 'GND', 'LATCH_D', (88.5, 37.0, 0), 'power'),
    R('R3', '100k', 'LATCH_G', 'GND', (88.5, 41.0, 0), 'power'),
    R('R4', '1k', 'PWR_HOLD', 'PWR_HOLD_R', (97.5, 37.0, 0), 'power'),
    dict(ref='D2', sym='Device:D_Schottky', val='BAT54WS', fp='Diode_SMD:D_SOD-323', pins={'1': 'LATCH_G', '2': 'PWR_HOLD_R'},
         pcb=(93.0, 37.0, 0), blk='power', mpn='BAT54WS Schottky SOD-323'),
    R('R9', '1k', 'VBAT_F', 'REED_SUPPLY', (30.5, 37.5, 90), 'power', mpn='0805 (limits current if the reed lead shorts)'),
    conn('J3', 2, ['REED_SUPPLY', 'REED_OUT'], (44.0, 57.5, 180), 'power', 'REED SWITCH',
         mpn='JST PH 2-pin + glass reed switch (normally open) on the hull wall'),
    R('R5', '100k', 'REED_OUT', 'REED_DIV', (97.5, 41.0, 0), 'power'),
    R('R6', '100k', 'REED_DIV', 'GND', (102.0, 37.0, 0), 'power'),
    dict(ref='D3', sym='Device:D_Schottky', val='BAT54WS', fp='Diode_SMD:D_SOD-323', pins={'1': 'LATCH_G', '2': 'REED_DIV'},
         pcb=(93.0, 41.0, 0), blk='power', mpn='BAT54WS Schottky SOD-323'),
    R('R7', '100k', 'REED_OUT', 'MAG_SENSE', (102.0, 41.0, 0), 'power'),
    R('R8', '22k', 'MAG_SENSE', 'GND', (106.5, 37.0, 0), 'power'),
    C('C7', '100nF', 'MAG_SENSE', 'GND', (106.5, 41.0, 0), 'power'),
    dict(ref='D4', sym='Device:D_TVS', val='SMBJ18A', fp='Diode_SMD:D_SMB', pins={'1': 'VSYS', '2': 'GND'},
         pcb=(45.5, 24.0, 90), blk='power', mpn='SMBJ18A unidirectional TVS (ESC spikes)'),
    dict(ref='C2', sym='Device:C_Polarized', val='470uF 25V', fp='Capacitor_THT:CP_Radial_D10.0mm_P5.00mm',
         pins={'1': 'VSYS', '2': 'GND'}, pcb=(36.0, 38.5, 0), blk='power', mpn='470 uF 25 V low-ESR electrolytic, 10 mm'),
    dict(ref='J2', sym='Connector_Generic:Conn_01x02', val='ESC POWER XT30', fp='Connector_AMASS:AMASS_XT30PW-F_1x02_P2.50mm_Horizontal',
         pins={'1': 'GND', '2': 'VSYS'}, pcb=(15.0, 53.0, 90), blk='power', mpn='AMASS XT30PW-F (female, PCB, right angle)'),
    # ---------------- 5 V buck regulator ---------------------------------------------
    dict(ref='U1', sym='Regulator_Switching:LM2596S-5', val='LM2596S-5.0', fp='Package_TO_SOT_SMD:TO-263-5_TabPin3',
         pins={'1': 'VSYS', '2': 'BUCK_SW', '3': 'GND', '4': '+5V', '5': 'GND'}, pcb=(66.0, 17.0, 180), blk='buck',
         mpn='LM2596S-5.0 3 A buck, TO-263-5'),
    dict(ref='C3', sym='Device:C_Polarized', val='220uF 35V', fp='Capacitor_THT:CP_Radial_D10.0mm_P5.00mm',
         pins={'1': 'VSYS', '2': 'GND'}, pcb=(48.0, 15.0, 0), blk='buck', mpn='220 uF 35 V low-ESR electrolytic, 10 mm'),
    C('C4', '4.7uF 50V', 'VSYS', 'GND', (71.0, 25.5, 0), 'buck', fp=C1206, mpn='1206 X7R 50V'),
    dict(ref='D5', sym='Device:D_Schottky', val='SS54', fp='Diode_SMD:D_SMC', pins={'1': 'BUCK_SW', '2': 'GND'},
         pcb=(79.8, 27.6, 270), blk='buck', mpn='SS54 5 A 40 V Schottky, SMC'),
    dict(ref='L1', sym='Device:L', val='33uH 3A', fp='Inductor_SMD:L_Bourns_SRR1260',
         pins={'1': 'BUCK_SW', '2': '+5V'}, pcb=(86.0, 15.0, 0), blk='buck', mpn='Bourns SRR1260-330M (33 uH, >3 A)'),
    dict(ref='C5', sym='Device:C_Polarized', val='470uF 10V', fp='Capacitor_THT:CP_Radial_D8.0mm_P3.50mm',
         pins={'1': '+5V', '2': 'GND'}, pcb=(95.0, 15.0, 0), blk='buck', mpn='470 uF 10 V low-ESR electrolytic, 8 mm'),
    C('C6', '22uF', '+5V', 'GND', (95.0, 23.0, 90), 'buck', fp=C1206, mpn='1206 X5R 16V'),
    dict(ref='D6', sym='Device:D_Schottky', val='SS34', fp='Diode_SMD:D_SMA', pins={'1': 'DEVKIT_5V', '2': '+5V'},
         pcb=(98.0, 28.4, 0), blk='buck', mpn='SS34 3 A Schottky, SMA (stops USB back-feed)'),
    C('C8', '10uF', 'DEVKIT_5V', 'GND', (91.0, 29.0, 0), 'buck', fp=C1206, mpn='1206 X5R 16V'),
    R('R10', '2.2k', '+5V', 'LED_PWR', (71.0, 29.0, 0), 'buck'),
    dict(ref='D10', sym='Device:LED', val='green', fp='LED_SMD:LED_0805_2012Metric', pins={'1': 'GND', '2': 'LED_PWR'},
         pcb=(66.5, 29.0, 180), blk='buck', mpn='0805 green LED (5 V present)'),
    # ---------------- MCU ---------------------------------------------------------------
    dict(ref='U2', sym='auv:ESP32-S3-DevKitC-1', val='ESP32-S3-DevKitC-1', fp='auv:ESP32-S3-DevKitC-1_Socket',
         pins=DEVKIT_NETS, pcb=(147.0, 32.0, 0), blk='mcu',
         mpn='Espressif ESP32-S3-DevKitC-1 (N8R8 or N16R8) on 2 x 22-pin 2.54 mm female headers'),
    # ---------------- LoRa radio ---------------------------------------------------------
    dict(ref='J4', sym='auv:E220-900T22D', val='E220-900T22D', fp='auv:E220-900T22D_Socket',
         pins={'1': 'LORA_M0', '2': 'LORA_M1', '3': 'LORA_RXD', '4': 'LORA_TXD', '5': 'LORA_AUX', '6': '+5V', '7': 'GND'},
         pcb=(108.0, 8.0, 0), blk='lora', mpn='Ebyte E220-900T22D (868 MHz LoRa, UART) on a 7-pin female header'),
    R('R11', '4.7k', 'LORA_TXD', '+3V3', (113.0, 12.0, 90), 'lora'),
    R('R12', '4.7k', 'LORA_AUX', '+3V3', (116.0, 12.0, 90), 'lora'),
    # ---------------- sensors ------------------------------------------------------------
    conn('J5', 4, ['+5V', 'GND', 'GPS_TXD', 'GPS_RXD'], (31.5, 2.4, 0), 'sensors', 'GPS (5V,G,TX,RX)',
         mpn='JST PH 4-pin to the BN-220 GPS in the mast'),
    conn('J6', 5, ['+3V3', 'GND', 'SDA', 'SCL', 'IMU_INT'], (44.0, 2.4, 0), 'sensors', 'IMU (3V3,G,SDA,SCL,INT)'),
    conn('J7', 4, ['+3V3', 'GND', 'SDA', 'SCL'], (57.5, 2.4, 0), 'sensors', 'DEPTH (3V3,G,SDA,SCL)'),
    conn('J8', 4, ['+3V3', 'GND', 'SDA', 'SCL'], (79.0, 2.4, 0), 'sensors', 'I2C AUX / BME280'),
    R('R13', '4.7k', 'SDA', '+3V3', (120.0, 12.0, 90), 'sensors'),
    R('R14', '4.7k', 'SCL', '+3V3', (123.0, 12.0, 90), 'sensors'),
    conn('J9', 2, ['LEAK_F', 'GND'], (46.5, 40.5, 0), 'sensors', 'LEAK FRONT'),
    R('R15', '100k', 'LEAK_F', '+3V3', (131.0, 37.0, 90), 'sensors'),
    C('C9', '100nF', 'LEAK_F', 'GND', (133.5, 37.0, 90), 'sensors'),
    conn('J10', 2, ['LEAK_R', 'GND'], (53.5, 40.5, 0), 'sensors', 'LEAK REAR'),
    R('R16', '100k', 'LEAK_R', '+3V3', (126.0, 37.0, 90), 'sensors'),
    C('C10', '100nF', 'LEAK_R', 'GND', (128.5, 37.0, 90), 'sensors'),
    R('R17', '100k', 'VSYS', 'VBAT_SENSE', (133.5, 49.0, 90), 'sensors', mpn='0805 1% (battery divider top)'),
    R('R18', '22k', 'VBAT_SENSE', 'GND', (136.0, 49.0, 90), 'sensors', mpn='0805 1% (battery divider bottom)'),
    C('C11', '100nF', 'VBAT_SENSE', 'GND', (138.5, 49.0, 90), 'sensors'),
    # ---------------- ESC (4-in-1, DShot) -------------------------------------------------
    conn('J11', 7, ['GND', 'ESC_CURR', 'ESC_TLM', 'ESC_M1_O', 'ESC_M2_O', 'ESC_M3_O', 'ESC_M4_O'], (3.0, 17.0, 90),
         'esc', 'ESC SIGNAL', mpn='JST PH 7-pin; re-pin the ESC harness to match the silkscreen'),
    R('R19', '100R', 'ESC_M1', 'ESC_M1_O', (9.5, 11.6, 0), 'esc'),
    R('R20', '100R', 'ESC_M2', 'ESC_M2_O', (9.5, 9.4, 0), 'esc'),
    R('R21', '100R', 'ESC_M3', 'ESC_M3_O', (9.5, 7.2, 0), 'esc'),
    R('R22', '100R', 'ESC_M4', 'ESC_M4_O', (9.5, 5.0, 0), 'esc'),
    R('R23', '1k', 'ESC_CURR', 'ESC_CURR_F', (128.0, 49.0, 90), 'esc'),
    C('C12', '100nF', 'ESC_CURR_F', 'GND', (130.5, 49.0, 90), 'esc'),
    R('R24', '10k', 'ESC_CURR', 'GND', (125.5, 49.0, 90), 'esc', mpn='0805 (holds the input low if no ESC)'),
    # ---------------- outputs: strobe, aux, buzzer ----------------------------------------
    NFET('Q6', 'AUX1_EN', 'GND', 'AUX1_D', (56.0, 47.0, 0), 'outputs'),
    R('R25', '100k', 'AUX1_EN', 'GND', (56.0, 51.0, 0), 'outputs'),
    conn('J12', 2, ['VSYS', 'AUX1_D'], (52.0, 57.0, 180), 'outputs', 'AUX1 STROBE (+,-)', xh=True,
         mpn='JST XH 2-pin to the strobe LED in the mast'),
    NFET('Q7', 'AUX2_EN', 'GND', 'AUX2_D', (60.0, 47.0, 0), 'outputs'),
    R('R26', '100k', 'AUX2_EN', 'GND', (60.0, 51.0, 0), 'outputs'),
    conn('J13', 2, ['VSYS', 'AUX2_D'], (60.5, 57.0, 180), 'outputs', 'AUX2 LIGHT (+,-)', xh=True,
         mpn='JST XH 2-pin spare switched output (lights, pump)'),
    # ---------------- camera power switch and button opto-isolators ----------------------
    dict(ref='Q4', sym='Device:Q_PMOS_GSD', val='AO3401A', fp=SOT23, pins={'1': 'CAM_PG', '2': '+5V', '3': 'CAM_5V_SW'},
         pcb=(64.0, 47.5, 0), blk='camera', mpn='AO3401A P-MOSFET -30V -4A SOT-23'),
    R('R28', '100k', 'CAM_PG', '+5V', (64.0, 51.5, 0), 'camera'),
    NFET('Q5', 'CAM_EN', 'GND', 'CAM_PG', (69.0, 47.5, 0), 'camera'),
    R('R30', '100k', 'CAM_EN', 'GND', (69.0, 51.5, 0), 'camera'),
    dict(ref='F2', sym='Device:Polyfuse', val='1.5A hold', fp='Fuse:Fuse_1812_4532Metric', pins={'1': 'CAM_5V_SW', '2': 'CAM_VBUS'},
         pcb=(75.0, 47.5, 0), blk='camera', mpn='1812 PTC resettable fuse, 1.5 A hold'),
    C('C13', '22uF', 'CAM_VBUS', 'GND', (75.0, 51.5, 0), 'camera', fp=C1206, mpn='1206 X5R 16V'),
    conn('J14', 2, ['CAM_VBUS', 'GND'], (47.5, 47.5, 0), 'camera', 'CAMERA 5V (+,-)', xh=True,
         mpn='JST XH 2-pin to a USB-A female breakout (bridge D+ to D-) for the camera cable'),
    dict(ref='U3', sym='Isolator:PC817', val='PC817', fp='Package_DIP:DIP-4_W7.62mm',
         pins={'1': 'OPTO_A_AN', '2': 'GND', '3': 'BTN_A_E', '4': 'BTN_A_C'}, pcb=(60.0, 33.5, 0), blk='camera',
         mpn='PC817 opto-isolator DIP-4 (presses camera button A)'),
    dict(ref='U4', sym='Isolator:PC817', val='PC817', fp='Package_DIP:DIP-4_W7.62mm',
         pins={'1': 'OPTO_B_AN', '2': 'GND', '3': 'BTN_B_E', '4': 'BTN_B_C'}, pcb=(60.0, 40.0, 0), blk='camera',
         mpn='PC817 opto-isolator DIP-4 (presses camera button B)'),
    R('R31', '330R', 'CAM_BTN_A', 'OPTO_A_AN', (72.0, 33.5, 0), 'camera'),
    R('R32', '330R', 'CAM_BTN_B', 'OPTO_B_AN', (72.0, 40.0, 0), 'camera'),
    R('R33', '100k', 'CAM_BTN_A', 'GND', (76.0, 33.5, 0), 'camera'),
    R('R34', '100k', 'CAM_BTN_B', 'GND', (76.0, 40.0, 0), 'camera'),
    conn('J15', 4, ['BTN_A_C', 'BTN_A_E', 'BTN_B_C', 'BTN_B_E'], (46.5, 34.2, 0), 'camera', 'CAM BUTTONS (A+,A-,B+,B-)',
         mpn='JST PH 4-pin, wires soldered across the camera buttons (optional)'),
    # ---------------- test points and mounting holes --------------------------------------
    dict(ref='TP1', sym='Connector:TestPoint', val='ESC_TLM', fp='TestPoint:TestPoint_Pad_D2.0mm', pins={'1': 'ESC_TLM'},
         pcb=(13.5, 13.5, 0), blk='misc', mpn='test pad'),
    dict(ref='TP2', sym='Connector:TestPoint', val='GND', fp='TestPoint:TestPoint_Pad_D2.0mm', pins={'1': 'GND'},
         pcb=(113.0, 45.0, 0), blk='misc', mpn='test pad'),
    dict(ref='TP3', sym='Connector:TestPoint', val='VSYS', fp='TestPoint:TestPoint_Pad_D2.0mm', pins={'1': 'VSYS'},
         pcb=(47.5, 30.0, 0), blk='misc', mpn='test pad'),
    dict(ref='TP4', sym='Connector:TestPoint', val='+5V', fp='TestPoint:TestPoint_Pad_D2.0mm', pins={'1': '+5V'},
         pcb=(103.5, 28.6, 0), blk='misc', mpn='test pad'),
    dict(ref='TP5', sym='Connector:TestPoint', val='+3V3', fp='TestPoint:TestPoint_Pad_D2.0mm', pins={'1': '+3V3'},
         pcb=(142.0, 43.0, 0), blk='misc', mpn='test pad'),
]

for i, (bx, by) in enumerate(((24.0, 4.0), (24.0, 56.0), (71.5, 4.0), (71.5, 56.5), (96.0, 4.0)), start=1):
    PARTS.append(dict(ref=f'H{i}', sym='Mechanical:MountingHole', val='M3', fp='MountingHole:MountingHole_3.2mm_M3',
                      pins={}, pcb=(bx, by, 0), blk='misc', mpn='M3 mounting hole'))

# ---------------------------------------------------------------------------
# Net classes (track width / clearance in mm)
# ---------------------------------------------------------------------------
NETCLASSES = {
    # the high-current paths (battery -> fuse -> FETs -> ESC, buck switch node) are
    # also pre-routed as wide tracks in generate_board.py before autorouting
    'Power': dict(width=2.0, clearance=0.3, via_d=1.2, via_drill=0.6, nets=['VBAT_IN', 'VBAT_F']),
    'Supply': dict(width=0.6, clearance=0.25, via_d=0.9, via_drill=0.45,
                   nets=['VSYS', '+5V', 'BUCK_SW', 'DEVKIT_5V', 'CAM_5V_SW', 'CAM_VBUS', 'AUX1_D', 'AUX2_D']),
    'Gnd': dict(width=0.5, clearance=0.2, via_d=0.8, via_drill=0.4, nets=['GND']),
    'Default': dict(width=0.3, clearance=0.2, via_d=0.7, via_drill=0.35, nets=[]),
}

BLOCK_TITLES = {
    'power': 'Battery input, 15 A fuse, magnet soft-latch power switch',
    'buck': '5 V buck regulator (LM2596S-5)',
    'mcu': 'ESP32-S3-DevKitC-1 (plugs into two 22-pin sockets)',
    'lora': 'LoRa telemetry radio (Ebyte E220-900T22D, 868 MHz)',
    'sensors': 'Sensors: GPS, IMU, depth, leak, battery voltage',
    'esc': '4-in-1 ESC signals (DShot) and current sense',
    'outputs': 'Switched outputs: strobe light and spare load',
    'camera': '4K camera: switched 5 V and button opto-isolators',
    'misc': 'Test points and mounting holes',
}
