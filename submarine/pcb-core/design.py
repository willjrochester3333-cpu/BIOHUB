"""
design.py - single source of truth for the Minnow CORE board (rev 2.0).

The core board is the "everything on one board" version of the Minnow AUV
electronics. JLCPCB assembles it completely, so the ESP32, USB programming
port, power switch, 5 V and 3.3 V supplies, compass/IMU, hull pressure and
humidity sensor, LoRa radio, magnet on/off sensor, camera power port and all
connectors arrive soldered. Order two: one goes in the sub, the other is the
shore radio (plug it into a laptop with a USB-C cable).

Same outline (150 x 60 mm) and mounting holes as the rev 1 carrier board, so
it fits the same sled in the hull.

Every part has an 'lcsc' field: the JLCPCB / LCSC part number used in the
assembly BOM. All of them were checked against JLCPCB's parts library (stock
and basic / extended status) on 2026-11-11.

Board coordinates (bx, by) are in mm: bx runs from the REAR edge (0) to the
FRONT edge (150) of the board, by from the PORT edge (0) to the STARBOARD
edge (60). KiCad X = 100 + bx, KiCad Y = 100 + by.
"""

BOARD_W = 150.0
BOARD_H = 60.0
TITLE = 'Minnow AUV core board'
REV = '2.0'
PROJECT = 'minnow-core'

# ---------------------------------------------------------------------------
# ESP32-WROOM-32E pad -> net. The module sits at the front edge with its PCB
# antenna pointing forward (towards the camera, which it talks to over Wi-Fi).
# Pins were chosen by where the wires go: port-side pads drive the thrusters,
# outputs and power latch (all at the rear/port side of the board), starboard
# pads go to the LoRa radio, GPS, sensors and USB.
#   ADC1 pins (work while Wi-Fi is on): 36 VBAT, 39 ESC current, 34/35 leak.
#   Strapping pins: IO0 boot button, IO2 status LED (pulled low by the LED),
#   IO12 AUX output (100k pull-down keeps it low at reset, as the flash needs),
#   IO15 magnet sense, IO5 LoRa chip-select (pulled up).
# ---------------------------------------------------------------------------
ESP_PINS = {
    '1': 'GND', '2': '+3V3', '3': 'ESP_EN', '4': 'VBAT_SENSE', '5': 'ESC_CURR_F', '6': 'LEAK_F', '7': 'LEAK_R',
    '8': 'PWR_HOLD', '9': 'ESC_M1', '10': 'ESC_M2', '11': 'ESC_M3', '12': 'ESC_M4', '13': 'STROBE_EN',
    '14': 'AUX_EN', '15': 'GND', '16': 'CAM_EN', '17': None, '18': None, '19': None, '20': None, '21': None,
    '22': None, '23': 'MAG_SENSE', '24': 'LED_STAT', '25': 'ESP_IO0', '26': 'LORA_DIO0', '27': 'GPS_TX',
    '28': 'GPS_RX', '29': 'LORA_NSS', '30': 'LORA_SCK', '31': 'LORA_MISO', '32': None, '33': 'SDA',
    '34': 'ESP_RXD', '35': 'ESP_TXD', '36': 'SCL', '37': 'LORA_MOSI', '38': 'GND', '39': 'GND',
}
GPIO_MAP = [  # (GPIO, net, note) - for the docs and the firmware
    (0, 'ESP_IO0', 'BOOT button / auto-program'), (1, 'ESP_TXD', 'USB serial (CH340C)'),
    (2, 'LED_STAT', 'red status LED'), (3, 'ESP_RXD', 'USB serial (CH340C)'),
    (4, 'LORA_DIO0', 'LoRa interrupt'), (5, 'LORA_NSS', 'LoRa chip select'),
    (12, 'AUX_EN', 'AUX output (lights / pump)'), (13, 'CAM_EN', 'camera 5 V on'),
    (14, 'STROBE_EN', 'strobe output'), (15, 'MAG_SENSE', 'magnet sensor (low = magnet)'),
    (16, 'GPS_TX', 'UART2 RX <- GPS TX'), (17, 'GPS_RX', 'UART2 TX -> GPS RX'),
    (18, 'LORA_SCK', 'SPI'), (19, 'LORA_MISO', 'SPI'), (21, 'SDA', 'I2C'), (22, 'SCL', 'I2C'),
    (23, 'LORA_MOSI', 'SPI'), (25, 'ESC_M2', 'DShot motor 2'), (26, 'ESC_M3', 'DShot motor 3'),
    (27, 'ESC_M4', 'DShot motor 4'), (32, 'PWR_HOLD', 'keeps the power switch on'),
    (33, 'ESC_M1', 'DShot motor 1'), (34, 'LEAK_F', 'leak probe front (ADC1)'),
    (35, 'LEAK_R', 'leak probe rear (ADC1)'), (36, 'VBAT_SENSE', 'battery voltage x 22/122 (ADC1)'),
    (39, 'ESC_CURR_F', 'ESC current sensor (ADC1)'),
]

# ---------------------------------------------------------------------------
# Footprints and helpers
# ---------------------------------------------------------------------------
R0805 = 'Resistor_SMD:R_0805_2012Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
C1206 = 'Capacitor_SMD:C_1206_3216Metric'
SOT23 = 'Package_TO_SOT_SMD:SOT-23'
PH = 'Connector_JST:JST_PH_S{n}B-PH-SM4-TB_1x{n:02d}-1MP_P2.00mm_Horizontal'

# JLCPCB basic parts (no feeder fee) for the passives
R_LCSC = {'100R': 'C17408', '1k': 'C17513', '2.2k': 'C17520', '4.7k': 'C17673', '5.1k': 'C27834', '10k': 'C17414',
          '22k': 'C17560', '47k': 'C17713', '75k': 'C17819', '100k': 'C149504', '220k': 'C17556'}
C_LCSC = {('22pF', C0805): 'C1804', ('100nF', C0805): 'C49678', ('1uF', C0805): 'C28323',
          ('10uF', C0805): 'C15850', ('10uF', C1206): 'C13585', ('22uF', C1206): 'C12891'}
C_MPN = {'22pF': '22 pF 50 V C0G', '100nF': '100 nF 50 V X7R', '1uF': '1 uF 50 V X7R', '10uF': '10 uF X5R',
         '22uF': '22 uF 25 V X5R'}


def R(ref, val, a, b, pcb, blk, note=''):
    return dict(ref=ref, sym='Device:R', val=val, fp=R0805, pins={'1': a, '2': b}, pcb=pcb, blk=blk,
                lcsc=R_LCSC[val], mpn=f'{val} 0805 1%' + (f' ({note})' if note else ''))


def C(ref, val, a, b, pcb, blk, fp=C0805, note=''):
    return dict(ref=ref, sym='Device:C', val=val, fp=fp, pins={'1': a, '2': b}, pcb=pcb, blk=blk,
                lcsc=C_LCSC[(val, fp)], mpn=f"{C_MPN[val]} {fp.split(':')[1][2:6]}" + (f' ({note})' if note else ''))


def NFET(ref, g, s, d, pcb, blk):
    return dict(ref=ref, sym='Device:Q_NMOS_GSD', val='AO3400A', fp=SOT23, pins={'1': g, '2': s, '3': d},
                pcb=pcb, blk=blk, lcsc='C20917', mpn='AO3400A N-MOSFET 30 V 5.7 A SOT-23')


def PFET(ref, g, s, d, pcb, blk):
    return dict(ref=ref, sym='Device:Q_PMOS_GSD', val='AO3401A', fp=SOT23, pins={'1': g, '2': s, '3': d},
                pcb=pcb, blk=blk, lcsc='C15127', mpn='AO3401A P-MOSFET -30 V -4 A SOT-23')


def SCHOTTKY_SMALL(ref, k, a, pcb, blk):
    return dict(ref=ref, sym='Device:D_Schottky', val='BAT54WS', fp='Diode_SMD:D_SOD-323', pins={'1': k, '2': a},
                pcb=pcb, blk=blk, lcsc='C7502694', mpn='BAT54WS Schottky SOD-323')


def conn(ref, n, nets, pcb, blk, val, lcsc):
    return dict(ref=ref, sym=f'Connector_Generic:Conn_01x{n:02d}', val=val, fp=PH.format(n=n),
                pins={str(i + 1): net for i, net in enumerate(nets)}, pcb=pcb, blk=blk, lcsc=lcsc,
                mpn=f'JST PH {n}-pin side-entry SMD S{n}B-PH-SM4-TB')


PH2, PH4 = 'C295747', 'C265102'

PARTS = [
    # ================= battery in, 15 A fuse, magnet soft-latch high-side switch =================
    dict(ref='J1', sym='Connector_Generic:Conn_01x02', val='BATTERY XT60', fp='Connector_AMASS:AMASS_XT60PW-M_1x02_P7.20mm_Horizontal',
         pins={'1': 'GND', '2': 'VBAT_IN'}, pcb=(17.5, 37.0, 90), blk='power', lcsc='C98732',
         mpn='AMASS XT60PW-M (male, PCB, right angle) - through-hole'),
    dict(ref='F1', sym='Device:Fuse', val='15A', fp='Fuse:Fuse_1206_3216Metric', pins={'1': 'VBAT_IN', '2': 'VBAT_F'},
         pcb=(22.6, 29.8, 0), blk='power', lcsc='C136356', mpn='JFC1206-2150FS 15 A 32 V fast fuse, 1206'),
    dict(ref='Q1', sym='Device:Q_PMOS_GDS', val='AOD4185', fp='Package_TO_SOT_SMD:TO-252-2',
         pins={'1': 'PFET_G', '2': 'VSYS', '3': 'VBAT_F'}, pcb=(38.0, 18.0, 0), blk='power', lcsc='C400894',
         mpn='AOD4185 P-MOSFET -40 V -40 A DPAK'),
    dict(ref='Q2', sym='Device:Q_PMOS_GDS', val='AOD4185', fp='Package_TO_SOT_SMD:TO-252-2',
         pins={'1': 'PFET_G', '2': 'VSYS', '3': 'VBAT_F'}, pcb=(38.0, 27.5, 0), blk='power', lcsc='C400894',
         mpn='AOD4185 P-MOSFET -40 V -40 A DPAK (in parallel with Q1: half the heat)'),
    R('R1', '100k', 'PFET_G', 'VBAT_F', (35.6, 12.35, 90), 'power', 'gate pull-up: FETs off'),
    C('C1', '100nF', 'PFET_G', 'VBAT_F', (33.4, 12.35, 90), 'power', note='soft start'),
    R('R2', '47k', 'PFET_G', 'LATCH_D', (37.8, 12.35, 90), 'power', 'gate divider: Vgs = 68 % of battery'),
    NFET('Q3', 'LATCH_G', 'GND', 'LATCH_D', (13.5, 11.5, 0), 'power'),
    R('R3', '100k', 'LATCH_G', 'GND', (13.5, 15.0, 0), 'power'),
    R('R4', '1k', 'PWR_HOLD', 'PWR_HOLD_R', (17.8, 15.0, 90), 'power'),
    SCHOTTKY_SMALL('D1', 'LATCH_G', 'PWR_HOLD_R', (17.8, 11.0, 90), 'power'),
    # always-on 3.3 V (2.5 uA) for the magnet sensor
    R('R5', '100R', 'VBAT_F', 'VAON_IN', (18.0, 6.5, 90), 'power', 'spike filter'),
    C('C2', '1uF', 'VAON_IN', 'GND', (18.0, 2.9, 90), 'power'),
    dict(ref='U1', sym='Regulator_Linear:HT75xx-1-SOT89', val='HT7533-1', fp='Package_TO_SOT_SMD:SOT-89-3',
         pins={'1': 'GND', '2': 'VAON_IN', '3': 'VAON'}, pcb=(13.5, 4.0, 0), blk='power', lcsc='C14289',
         mpn='HT7533-1 3.3 V LDO, 30 V in, 2.5 uA, SOT-89'),
    C('C3', '1uF', 'VAON', 'GND', (13.5, 8.0, 0), 'power'),
    dict(ref='U2', sym='Sensor_Magnetic:SM351LT', val='SM351LT', fp=SOT23, pins={'1': 'VAON', '2': 'HALL_OUT', '3': 'GND'},
         pcb=(8.5, 2.3, 0), blk='power', lcsc='C80830',
         mpn='Honeywell SM351LT magnetoresistive switch, output low near a magnet, 0.36 uA'),
    C('C4', '100nF', 'VAON', 'GND', (8.5, 5.6, 0), 'power'),
    PFET('Q4', 'HALL_OUT', 'VAON', 'HALL_ON', (4.4, 5.0, 0), 'power'),
    R('R6', '100k', 'HALL_ON', 'GND', (4.4, 8.6, 0), 'power'),
    SCHOTTKY_SMALL('D2', 'LATCH_G', 'HALL_ON', (8.7, 8.6, 0), 'power'),
    R('R7', '220k', 'HALL_OUT', 'MAG_SENSE', (8.7, 11.2, 0), 'power', 'magnet state to the ESP32'),
    # protection and bulk capacitance on the switched battery rail
    dict(ref='D3', sym='Device:D_TVS', val='SMBJ18A', fp='Diode_SMD:D_SMB', pins={'1': 'VSYS', '2': 'GND'},
         pcb=(46.5, 22.5, 90), blk='power', lcsc='C19077573', mpn='SMBJ18A unidirectional TVS (ESC spikes)'),
    dict(ref='C5', sym='Device:C_Polarized', val='100uF 35V', fp='Capacitor_SMD:CP_Elec_6.3x7.7',
         pins={'1': 'VSYS', '2': 'GND'}, pcb=(46.5, 31.0, 270), blk='power', lcsc='C72478',
         mpn='100 uF 35 V aluminium electrolytic, SMD 6.3 x 7.7 mm'),
    dict(ref='C6', sym='Device:C_Polarized', val='100uF 35V', fp='Capacitor_SMD:CP_Elec_6.3x7.7',
         pins={'1': 'VSYS', '2': 'GND'}, pcb=(46.5, 40.6, 270), blk='power', lcsc='C72478',
         mpn='100 uF 35 V aluminium electrolytic, SMD 6.3 x 7.7 mm'),
    dict(ref='J2', sym='Connector_Generic:Conn_01x02', val='ESC POWER XT30', fp='Connector_AMASS:AMASS_XT30UPB-F_1x02_P5.0mm_Vertical',
         pins={'1': 'GND', '2': 'VSYS'}, pcb=(8.0, 55.0, 90), blk='power', lcsc='C108769',
         mpn='AMASS XT30UPB-F (female, PCB, vertical) - through-hole'),
    R('R8', '100k', 'VSYS', 'VBAT_SENSE', (36.0, 35.0, 0), 'power', 'battery divider top'),
    R('R9', '22k', 'VBAT_SENSE', 'GND', (36.0, 37.4, 0), 'power', 'battery divider bottom'),
    C('C7', '100nF', 'VBAT_SENSE', 'GND', (36.0, 39.8, 0), 'power'),

    # ================= 5 V / 3 A buck (TPS54302) =================
    dict(ref='U3', sym='Regulator_Switching:TPS54302', val='TPS54302', fp='Package_TO_SOT_SMD:SOT-23-6',
         pins={'1': 'GND', '2': 'BUCK_SW', '3': 'VSYS', '4': 'BUCK_FB', '5': 'BUCK_EN', '6': 'BUCK_BOOT'},
         pcb=(59.0, 31.0, 90), blk='buck', lcsc='C311983', mpn='TI TPS54302DDCR 3 A 28 V synchronous buck, SOT-23-6'),
    C('C8', '10uF', 'VSYS', 'GND', (63.3, 30.0, 0), 'buck', fp=C1206, note='50 V'),
    C('C9', '10uF', 'VSYS', 'GND', (63.3, 27.4, 0), 'buck', fp=C1206, note='50 V'),
    C('C10', '100nF', 'VSYS', 'GND', (63.3, 32.8, 0), 'buck'),
    C('C11', '100nF', 'BUCK_BOOT', 'BUCK_SW', (55.6, 31.0, 90), 'buck', note='bootstrap'),
    dict(ref='L1', sym='Device:L', val='12uH', fp='Inductor_SMD:L_Bourns_SRR1260', pins={'1': 'BUCK_SW', '2': '+5V'},
         pcb=(59.0, 41.5, 270), blk='buck', lcsc='C1329355', mpn='Bourns SRR1260-120M 12 uH 5 A shielded'),
    C('C12', '22uF', '+5V', 'GND', (67.6, 44.0, 90), 'buck', fp=C1206),
    C('C13', '22uF', '+5V', 'GND', (70.2, 44.0, 90), 'buck', fp=C1206),
    R('R10', '75k', '+5V', 'BUCK_FB', (64.5, 25.0, 0), 'buck', 'Vout = 0.596 x (1 + 75/10) = 5.07 V'),
    R('R11', '10k', 'BUCK_FB', 'GND', (64.5, 22.8, 0), 'buck'),
    R('R12', '100k', 'VSYS', 'BUCK_EN', (55.0, 26.0, 0), 'buck', 'starts at 6.6 V'),
    R('R13', '22k', 'BUCK_EN', 'GND', (55.0, 23.8, 0), 'buck'),
    R('R14', '2.2k', '+5V', 'LED_5V', (64.5, 51.8, 0), 'buck'),
    dict(ref='D4', sym='Device:LED', val='green', fp='LED_SMD:LED_0805_2012Metric', pins={'1': 'GND', '2': 'LED_5V'},
         pcb=(68.0, 49.5, 180), blk='buck', lcsc='C2297', mpn='green LED 0805 (5 V on)'),

    # ================= USB-C, USB serial, auto-program, 3.3 V =================
    dict(ref='J3', sym='Connector:USB_C_Receptacle_USB2.0_16P', val='USB-C', fp='Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12',
         pins={'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND', 'S1': 'GND', 'A4': 'USB_VBUS', 'A9': 'USB_VBUS',
               'B4': 'USB_VBUS', 'B9': 'USB_VBUS', 'A5': 'USB_CC1', 'B5': 'USB_CC2', 'A6': 'USB_DP', 'B6': 'USB_DP',
               'A7': 'USB_DN', 'B7': 'USB_DN', 'A8': None, 'B8': None},
         pcb=(112.0, 57.0, 0), blk='usb', lcsc='C165948', mpn='Korean Hroparts TYPE-C-31-M-12 USB-C receptacle'),
    R('R15', '5.1k', 'USB_CC1', 'GND', (110.0, 49.6, 90), 'usb', 'USB-C sink'),
    R('R16', '5.1k', 'USB_CC2', 'GND', (114.0, 49.6, 90), 'usb', 'USB-C sink'),
    dict(ref='U4', sym='Power_Protection:SRV05-4', val='SRV05-4', fp='Package_TO_SOT_SMD:SOT-23-6',
         pins={'1': 'USB_DP', '2': 'GND', '3': 'USB_DN', '4': None, '5': 'USB_VBUS', '6': None},
         pcb=(112.0, 45.5, 0), blk='usb', lcsc='C85364', mpn='SRV05-4 USB ESD protection, SOT-23-6'),
    C('C14', '10uF', 'USB_VBUS', 'GND', (119.5, 53.0, 90), 'usb'),
    dict(ref='D5', sym='Device:D_Schottky', val='SS34', fp='Diode_SMD:D_SMA', pins={'1': 'LDO_IN', '2': 'USB_VBUS'},
         pcb=(118.5, 45.5, 90), blk='usb', lcsc='C8678',
         mpn='SS34 3 A Schottky, SMA (USB powers only the 3.3 V side: never the battery side)'),
    dict(ref='D8', sym='Device:D_Schottky', val='SS34', fp='Diode_SMD:D_SMA', pins={'1': 'LDO_IN', '2': '+5V'},
         pcb=(112.0, 19.5, 90), blk='usb', lcsc='C8678', mpn='SS34 3 A Schottky, SMA (5 V -> 3.3 V regulator)'),
    dict(ref='U5', sym='Interface_USB:CH340C', val='CH340C', fp='Package_SO:SOIC-16_3.9x9.9mm_P1.27mm',
         pins={'1': 'GND', '2': 'ESP_RXD', '3': 'ESP_TXD', '4': '+3V3', '5': 'USB_DP', '6': 'USB_DN', '7': None,
               '8': None, '9': None, '10': None, '11': None, '12': None, '13': 'CH_DTR', '14': 'CH_RTS',
               '15': None, '16': '+3V3'},
         pcb=(104.0, 46.0, 0), blk='usb', lcsc='C84681', mpn='WCH CH340C USB-serial (no crystal), SOIC-16'),
    C('C15', '100nF', '+3V3', 'GND', (98.8, 46.0, 90), 'usb'),
    dict(ref='Q5', sym='Transistor_BJT:MMBT3904', val='MMBT3904', fp=SOT23, pins={'1': 'AP_B1', '2': 'CH_RTS', '3': 'ESP_EN'},
         pcb=(110.0, 38.5, 0), blk='usb', lcsc='C20526', mpn='MMBT3904 NPN SOT-23 (auto-reset)'),
    dict(ref='Q6', sym='Transistor_BJT:MMBT3904', val='MMBT3904', fp=SOT23, pins={'1': 'AP_B2', '2': 'CH_DTR', '3': 'ESP_IO0'},
         pcb=(114.5, 38.5, 0), blk='usb', lcsc='C20526', mpn='MMBT3904 NPN SOT-23 (auto-boot)'),
    R('R17', '10k', 'CH_DTR', 'AP_B1', (110.0, 42.0, 0), 'usb'),
    R('R18', '10k', 'CH_RTS', 'AP_B2', (114.5, 42.0, 0), 'usb'),
    R('R19', '10k', '+3V3', 'ESP_EN', (139.0, 2.6, 0), 'usb'),
    C('C16', '1uF', 'ESP_EN', 'GND', (135.0, 2.6, 0), 'usb', note='reset delay'),
    R('R20', '10k', '+3V3', 'ESP_IO0', (122.0, 31.5, 0), 'usb'),
    dict(ref='SW1', sym='Switch:SW_Push', val='RESET', fp='Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A',
         pins={'1': 'ESP_EN', '2': 'GND'}, pcb=(114.0, 4.0, 0), blk='usb', lcsc='C318884', mpn='XKB TS-1187A-B-A-B tact switch'),
    dict(ref='SW2', sym='Switch:SW_Push', val='BOOT', fp='Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A',
         pins={'1': 'ESP_IO0', '2': 'GND'}, pcb=(105.0, 4.0, 0), blk='usb', lcsc='C318884', mpn='XKB TS-1187A-B-A-B tact switch'),
    dict(ref='U6', sym='Regulator_Linear:AMS1117-3.3', val='AMS1117-3.3', fp='Package_TO_SOT_SMD:SOT-223-3_TabPin2',
         pins={'1': 'GND', '2': '+3V3', '3': 'LDO_IN'}, pcb=(119.0, 13.0, 0), blk='usb', lcsc='C6186',
         mpn='AMS1117-3.3 1 A LDO, SOT-223'),
    C('C17', '22uF', 'LDO_IN', 'GND', (112.0, 13.0, 90), 'usb', fp=C1206),
    C('C18', '22uF', '+3V3', 'GND', (119.0, 19.0, 0), 'usb', fp=C1206),

    # ================= ESP32 =================
    dict(ref='U7', sym='RF_Module:ESP32-WROOM-32E', val='ESP32-WROOM-32E-N8', fp='core:ESP32-WROOM-32E',
         pins=ESP_PINS, pcb=(134.5, 16.0, 270), blk='mcu', lcsc='C701342',
         mpn='Espressif ESP32-WROOM-32E-N8 (8 MB flash, PCB antenna)'),
    C('C19', '10uF', '+3V3', 'GND', (131.0, 2.6, 0), 'mcu'),
    C('C20', '100nF', '+3V3', 'GND', (127.0, 2.6, 0), 'mcu'),
    R('R21', '1k', 'LED_STAT', 'LED_STAT_A', (121.0, 24.0, 0), 'mcu'),
    dict(ref='D6', sym='Device:LED', val='red', fp='LED_SMD:LED_0805_2012Metric', pins={'1': 'GND', '2': 'LED_STAT_A'},
         pcb=(121.0, 26.5, 180), blk='mcu', lcsc='C84256', mpn='red LED 0805 (status)'),

    # ================= LoRa radio =================
    dict(ref='U8', sym='RF_Module:Ai-Thinker-Ra-01', val='Ra-01H', fp='RF_Module:Ai-Thinker-Ra-01-LoRa',
         pins={'1': 'LORA_ANT', '2': 'GND', '3': '+3V3', '4': 'ESP_EN', '5': 'LORA_DIO0', '6': None, '7': None,
               '8': None, '9': 'GND', '10': None, '11': None, '12': 'LORA_SCK', '13': 'LORA_MISO', '14': 'LORA_MOSI',
               '15': 'LORA_NSS', '16': 'GND'},
         pcb=(87.5, 46.0, 0), blk='lora', lcsc='C503593',
         mpn='Ai-Thinker Ra-01H (SX1276, 803-930 MHz, same pins as Ra-01); reset follows the ESP32 EN line'),
    dict(ref='J4', sym='Connector:Conn_Coaxial', val='ANT 868', fp='Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical',
         pins={'1': 'LORA_ANT', '2': 'GND'}, pcb=(75.5, 39.0, 180), blk='lora', lcsc='C88374',
         mpn='Hirose U.FL-R-SMT-1(80) antenna socket'),
    C('C21', '10uF', '+3V3', 'GND', (77.0, 46.0, 90), 'lora'),
    C('C22', '100nF', '+3V3', 'GND', (77.0, 50.5, 90), 'lora'),
    R('R22', '10k', '+3V3', 'LORA_NSS', (99.0, 34.5, 0), 'lora'),

    # ================= sensors on the board =================
    dict(ref='U9', sym='Sensor_Motion:BNO055', val='BNO055', fp='Package_LGA:LGA-28_5.2x3.8mm_P0.5mm',
         pins={'2': 'GND', '3': '+3V3', '4': 'IMU_BL', '5': 'GND', '6': 'GND', '9': 'IMU_CAP', '10': None,
               '11': 'IMU_RST', '14': 'IMU_INT', '15': 'GND', '16': 'GND', '17': 'GND', '18': 'GND', '19': 'SCL',
               '20': 'SDA', '25': 'GND', '26': 'IMU_XO', '27': 'IMU_XI', '28': '+3V3'},
         pcb=(104.0, 20.0, 0), blk='sensors', lcsc='C93216',
         mpn='Bosch BNO055 9-axis orientation sensor, I2C address 0x28 (PS0=PS1=COM3=0)'),
    dict(ref='Y1', sym='Device:Crystal', val='32.768kHz', fp='Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm',
         pins={'1': 'IMU_XI', '2': 'IMU_XO'}, pcb=(104.0, 26.0, 0), blk='sensors', lcsc='C32346',
         mpn='32.768 kHz 12.5 pF crystal 3215 (better compass timing)'),
    C('C23', '22pF', 'IMU_XI', 'GND', (100.5, 26.0, 90), 'sensors'),
    C('C24', '22pF', 'IMU_XO', 'GND', (107.5, 26.0, 90), 'sensors'),
    C('C25', '100nF', '+3V3', 'GND', (100.0, 20.0, 90), 'sensors', note='VDD'),
    C('C26', '100nF', '+3V3', 'GND', (108.0, 20.0, 90), 'sensors', note='VDDIO'),
    C('C27', '100nF', 'IMU_CAP', 'GND', (104.0, 15.5, 0), 'sensors', note='BNO055 CAP pin'),
    R('R23', '10k', 'IMU_BL', '+3V3', (100.0, 13.5, 0), 'sensors', 'boot-loader pin high = normal'),
    R('R24', '10k', 'IMU_RST', '+3V3', (108.0, 13.5, 0), 'sensors'),
    dict(ref='U10', sym='Sensor:BME280', val='BME280', fp='Package_LGA:Bosch_LGA-8_2.5x2.5mm_P0.65mm_ClockwisePinNumbering',
         pins={'1': 'GND', '2': '+3V3', '3': 'SDA', '4': 'SCL', '5': '+3V3', '6': '+3V3', '7': 'GND', '8': '+3V3'},
         pcb=(93.0, 20.0, 0), blk='sensors', lcsc='C92489',
         mpn='Bosch BME280 hull pressure / humidity / temperature, I2C address 0x77 (SDO high)'),
    C('C28', '100nF', '+3V3', 'GND', (93.0, 16.5, 0), 'sensors'),
    C('C29', '100nF', '+3V3', 'GND', (93.0, 23.5, 0), 'sensors'),
    R('R25', '4.7k', 'SDA', '+3V3', (88.5, 18.0, 90), 'sensors', 'I2C pull-up'),
    R('R26', '4.7k', 'SCL', '+3V3', (86.0, 18.0, 90), 'sensors', 'I2C pull-up'),
    conn('J5', 4, ['+5V', 'GND', 'GPS_TX', 'GPS_RX'], (36.0, 54.9, 0), 'sensors', 'GPS (5V,G,TX,RX)', PH4),
    conn('J6', 4, ['+3V3', 'GND', 'SDA', 'SCL'], (84.0, 5.1, 180), 'sensors', 'DEPTH (3V3,G,SDA,SCL)', PH4),
    conn('J8', 2, ['LEAK_F', 'GND'], (33.0, 5.1, 180), 'sensors', 'LEAK FRONT', PH2),
    R('R27', '100k', 'LEAK_F', '+3V3', (79.0, 12.6, 90), 'sensors'),
    C('C30', '100nF', 'LEAK_F', 'GND', (81.2, 12.6, 90), 'sensors'),
    conn('J9', 2, ['LEAK_R', 'GND'], (42.5, 5.1, 180), 'sensors', 'LEAK REAR', PH2),
    R('R28', '100k', 'LEAK_R', '+3V3', (83.4, 12.6, 90), 'sensors'),
    C('C31', '100nF', 'LEAK_R', 'GND', (85.6, 12.6, 90), 'sensors'),

    # ================= 4-in-1 ESC (DShot) =================
    dict(ref='J10', sym='Connector_Generic:Conn_01x08', val='ESC SIGNAL', fp='Connector_JST:JST_SH_SM08B-SRSS-TB_1x08-1MP_P1.00mm_Horizontal',
         pins={'1': 'GND', '2': None, '3': 'ESC_CURR', '4': 'ESC_TLM', '5': 'ESC_M1_O', '6': 'ESC_M2_O',
               '7': 'ESC_M3_O', '8': 'ESC_M4_O'},
         pcb=(3.3, 19.0, 270), blk='esc', lcsc='C160407',
         mpn='JST SH 8-pin SMD SM08B-SRSS-TB: G, (VBAT not used), CUR, TLM, M1-M4'),
    R('R29', '1k', 'ESC_M1', 'ESC_M1_O', (9.5, 16.0, 0), 'esc', 'limits current if a wire is crossed'),
    R('R30', '1k', 'ESC_M2', 'ESC_M2_O', (9.5, 18.2, 0), 'esc'),
    R('R31', '1k', 'ESC_M3', 'ESC_M3_O', (9.5, 20.4, 0), 'esc'),
    R('R32', '1k', 'ESC_M4', 'ESC_M4_O', (9.5, 22.6, 0), 'esc'),
    R('R33', '1k', 'ESC_CURR', 'ESC_CURR_F', (14.0, 19.0, 0), 'esc'),
    R('R34', '10k', 'ESC_CURR', 'GND', (14.0, 21.2, 0), 'esc', 'holds the input low with no ESC'),
    C('C32', '100nF', 'ESC_CURR_F', 'GND', (14.0, 23.4, 0), 'esc'),

    # ================= switched outputs: strobe and spare (lights / pump) =================
    NFET('Q7', 'STROBE_EN', 'GND', 'STROBE_D', (52.5, 12.5, 0), 'outputs'),
    R('R35', '100k', 'STROBE_EN', 'GND', (52.5, 15.8, 0), 'outputs'),
    conn('J11', 2, ['VSYS', 'STROBE_D'], (52.5, 5.1, 180), 'outputs', 'STROBE (+BATT, -)', PH2),
    NFET('Q8', 'AUX_EN', 'GND', 'AUX_D', (62.5, 12.5, 0), 'outputs'),
    R('R36', '100k', 'AUX_EN', 'GND', (62.5, 15.8, 0), 'outputs', 'also keeps IO12 low at reset'),
    dict(ref='D7', sym='Device:D_Schottky', val='SS34', fp='Diode_SMD:D_SMA', pins={'1': 'VSYS', '2': 'AUX_D'},
         pcb=(62.5, 19.5, 0), blk='outputs', lcsc='C8678', mpn='SS34 flyback diode (pumps, motors)'),
    conn('J12', 2, ['VSYS', 'AUX_D'], (62.5, 5.1, 180), 'outputs', 'AUX (+BATT, -)', PH2),

    # ================= camera 5 V port =================
    PFET('Q9', 'CAM_PG', '+5V', 'CAM_5V_SW', (126.0, 42.0, 0), 'camera'),
    R('R37', '100k', 'CAM_PG', '+5V', (126.0, 45.5, 0), 'camera'),
    NFET('Q10', 'CAM_EN', 'GND', 'CAM_PG', (126.0, 49.0, 0), 'camera'),
    R('R38', '100k', 'CAM_EN', 'GND', (126.0, 52.5, 0), 'camera'),
    dict(ref='F2', sym='Device:Polyfuse', val='1.5A', fp='Fuse:Fuse_1812_4532Metric', pins={'1': 'CAM_5V_SW', '2': 'CAM_VBUS'},
         pcb=(131.0, 38.5, 0), blk='camera', lcsc='C142805', mpn='1812L150 resettable fuse 1.5 A hold'),
    C('C33', '22uF', 'CAM_VBUS', 'GND', (131.0, 34.5, 0), 'camera', fp=C1206),
    dict(ref='J13', sym='Connector:USB_A', val='CAMERA 5V', fp='Connector_USB:USB_A_Molex_67643_Horizontal',
         pins={'1': 'CAM_VBUS', '2': 'CAM_D', '3': 'CAM_D', '4': 'GND', '5': 'GND'}, pcb=(137.0, 54.0, 90),
         blk='camera', lcsc='C564920',
         mpn='Molex 67643 USB-A socket (D+ joined to D- = "charger", so the camera may draw 1.5 A) - through-hole'),

    # ================= test points and mounting holes =================
    dict(ref='TP1', sym='Connector:TestPoint', val='ESC_TLM', fp='TestPoint:TestPoint_Pad_D1.5mm', pins={'1': 'ESC_TLM'},
         pcb=(21.0, 20.5, 0), blk='misc', lcsc='', mpn='test pad'),
    dict(ref='TP2', sym='Connector:TestPoint', val='GND', fp='TestPoint:TestPoint_Pad_D1.5mm', pins={'1': 'GND'},
         pcb=(28.0, 43.0, 0), blk='misc', lcsc='', mpn='test pad'),
    dict(ref='TP3', sym='Connector:TestPoint', val='VSYS', fp='TestPoint:TestPoint_Pad_D1.5mm', pins={'1': 'VSYS'},
         pcb=(40.0, 47.5, 0), blk='misc', lcsc='', mpn='test pad'),
    dict(ref='TP4', sym='Connector:TestPoint', val='+5V', fp='TestPoint:TestPoint_Pad_D1.5mm', pins={'1': '+5V'},
         pcb=(73.5, 47.5, 0), blk='misc', lcsc='', mpn='test pad'),
    dict(ref='TP6', sym='Connector:TestPoint', val='IMU_INT', fp='TestPoint:TestPoint_Pad_D1.5mm', pins={'1': 'IMU_INT'},
         pcb=(116.0, 23.5, 0), blk='misc', lcsc='', mpn='test pad'),
]

for i, (bx, by) in enumerate(((24.0, 4.0), (24.0, 56.0), (71.5, 4.0), (71.5, 56.5), (96.0, 4.0)), start=1):
    PARTS.append(dict(ref=f'H{i}', sym='Mechanical:MountingHole', val='M3', fp='MountingHole:MountingHole_3.2mm_M3',
                      pins={}, pcb=(bx, by, 0), blk='misc', lcsc='', mpn='M3 mounting hole'))

# Magnet sensor position (for the hull marking): the SM351LT sits at the very
# port edge so a magnet held on the side of the hull, level with the board, is
# only about 15 mm away from it.
MAGNET_SENSOR_BXBY = (8.5, 0.0)

# ---------------------------------------------------------------------------
# Net classes (track width / clearance in mm)
# ---------------------------------------------------------------------------
NETCLASSES = {
    # battery -> fuse -> FETs is also pre-routed as wide copper in generate_board.py
    'Power': dict(width=2.0, clearance=0.3, via_d=1.2, via_drill=0.6, nets=['VBAT_IN', 'VBAT_F']),
    # 0.6 mm carries 2 A; the wide parts of VSYS are pre-routed
    'Supply': dict(width=0.6, clearance=0.25, via_d=0.9, via_drill=0.45,
                   nets=['VSYS', '+5V', 'BUCK_SW', 'CAM_5V_SW', 'CAM_VBUS', 'AUX_D', 'STROBE_D']),
    # 0.25 mm (about 1 A) so the tracks fit the 0.5 mm-pitch pins of the compass and the USB-C socket
    'Rail': dict(width=0.25, clearance=0.2, via_d=0.7, via_drill=0.35,
                 nets=['+3V3', 'VAON', 'VAON_IN', 'USB_VBUS', 'LDO_IN']),
    'Gnd': dict(width=0.5, clearance=0.2, via_d=0.8, via_drill=0.4, nets=['GND']),
    'RF': dict(width=0.8, clearance=0.3, via_d=0.8, via_drill=0.4, nets=['LORA_ANT']),
    'Fine': dict(width=0.2, clearance=0.15, via_d=0.6, via_drill=0.3,
                 nets=['USB_DP', 'USB_DN', 'USB_CC1', 'USB_CC2', 'SDA', 'SCL', 'IMU_XI', 'IMU_XO', 'IMU_BL',
                       'IMU_RST', 'IMU_CAP', 'IMU_INT']),
    'Default': dict(width=0.25, clearance=0.2, via_d=0.7, via_drill=0.35, nets=[]),
}

BLOCK_TITLES = {
    'power': 'Battery input, 15 A fuse, magnet soft-latch power switch (SM351LT, always-on 3.3 V)',
    'buck': '5 V / 3 A buck regulator (TPS54302)',
    'usb': 'USB-C programming port, CH340C USB serial, auto-program, 3.3 V LDO',
    'mcu': 'ESP32-WROOM-32E (Wi-Fi to the camera, BLE)',
    'lora': 'LoRa radio (Ai-Thinker Ra-01H, SX1276, 868 MHz) and antenna socket',
    'sensors': 'Sensors: BNO055 compass/IMU, BME280 hull monitor, GPS, depth, leak',
    'esc': '4-in-1 ESC signals (DShot) and current sense',
    'outputs': 'Switched outputs: strobe and spare (lights / pump)',
    'camera': '4K camera: switched 5 V USB-A port',
    'misc': 'Test points and mounting holes',
}
