# 5. Build and test plan

Build it in stages and prove each stage before the next. Every test below has a pass mark. Most hobby
subs that are lost are lost because a step was skipped.

## 5.1 Timeline

| Week | Work |
|---|---|
| 1 | Order everything: PCB + parts (2–3 weeks), motors / ESC / sensors (1–3 weeks), pipe, O-rings, window. Print the O-ring fit test, adjust, then print the end caps |
| 2 | Print the rest (about 30 hours of printing). Cut the pipe. Hull assembly and **dry-hull tests T1–T2** |
| 3 | Solder the board. **Bench tests T3–T5**. Write firmware steps 1–5 (see the software doc) |
| 4 | Thrusters, wiring, final assembly. **Bucket and bath tests T6–T7** |
| 5–6 | **Pool T8–T10**: trim, depth hold, heading hold, pool missions with 4K video |
| 7+ | **Lake T11–T12**: on a tether first, then free, with LoRa |

## 5.2 Tools

3D printer (PETG), soldering iron, multimeter, fine saw and mitre box (or pipe cutter), file, drill, M12 x 1.5 tap,
kitchen scale, a bucket, and a **hand vacuum pump with a gauge** (the brake-bleeder kind, about £18). A bench power
supply with a current limit is very useful for the first power-up but not essential.

## 5.3 Tests

### T0: O-ring fit test (before printing the caps)
Print `00_Oring_fit_test.stl`. Grease one O-ring, fit it, push the ring onto the pipe.
**Pass:** slides on with firm hand pressure, no wobble, O-ring stays seated.

### T1: Dry hull, vacuum
Close the empty hull (caps, window, glands, depth sensor, nothing inside). Connect the pump to the vent tube and pull
-0.3 bar (-300 mbar). **Pass:** loses less than 20 mbar in 15 minutes. If it leaks, brush soapy water over the joints
while pumping; bubbles show the leak. Usual culprits: a gland not tightened, the window bedding, a porous print.

### T2: Dry hull, dunk
Put dry tissue paper inside and hold the closed empty hull 0.5 m down in a bath or water butt for 1 hour.
**Pass:** the tissue is bone dry.

### T3: Board bring-up
On the bench, with the DevKit and modules **not** plugged in, follow the first power-up steps in the
[electronics doc](02-electronics.md#28-ordering-and-building-the-board).
**Pass:** the latch switches on and off, VSYS and 5 V are correct, and nothing gets warm.
With the **Minnow Core** board there is nothing to plug in first: follow its
[first power-up steps](../pcb-core/README.md#first-power-up-do-this-before-anything-is-plugged-in) instead
(current-limited 12 V, magnet on and off, then USB and the bring-up sketch).

### T4: Sensors and outputs
DevKit, LoRa and all sensors connected; bring-up firmware running. **Pass:** depth reads about 0 at the surface
and rises about 0.10 m when the sensor is held 10 cm under water. The compass heading turns smoothly through 360
degrees. GPS gets a fix outdoors in under 2 minutes. The leak inputs read "wet" when you touch a wet finger across
the probe. The BME280 reads room pressure. The strobe flashes. The camera starts and stops over Wi-Fi.

### T5: Thrusters
Thrusters in a bucket of water, sub on the bench. Enable 3D mode, then run each motor both ways at 10–30 %.
**Pass:** each motor runs smoothly both ways, the right motor answers to M1–M4, and the total current is under
3 A at 30 %.

### T6: Full system soak
Everything assembled and sealed, camera recording, on the bench (out of the sun) for 45 minutes.
**Pass:** no resets, the log is complete, hull temperature stays under 40 °C, and the camera file plays.

### T7: Bath or water butt
Sealed sub in water, mission software in a "stay at 0.3 m for 2 minutes" test mode.
**Pass:** holds depth, comes up by itself when the test ends (and when you pull the magnet off to switch it off), dry inside.

### T8: Pool trim
Follow the trim procedure in the [mechanical doc](01-mechanical.md#110-ballast-and-trim).
**Pass:** floats level, mast up, 45 g positive.

### T9: Pool control tuning
Tune depth, then heading, then both together (software doc, section 4.4).
**Pass:** holds 1.0 m ± 5 cm; holds heading ± 3 degrees while cruising; turns 90 degrees without losing more than 20 cm of depth.

### T10: Pool missions
A 3-waypoint square with real GPS outdoors, or simulated positions indoors. 4K recording on.
**Pass:** completes it 3 times in a row, surfaces at every waypoint, video plus log come back, no water inside.

### T11: Lake on a tether
Tie 30 m of strong braided fishing line to the rear clamp with a small float on it. Short missions, 1–2 m deep,
in calm, clear water near the bank.
**Pass:** 5 missions without a failsafe trigger, LoRa reports received on the shore, GPS track looks right.

### T12: Lake, free
Same missions without the line, building up slowly: one leg, then three, then longer. Always inside line of sight,
always with a way to reach the sub (a long pole or net, or a small inflatable for bigger lakes).

## 5.4 Pre-dive checklist

1. Battery charged (> 12.4 V) and strapped down; fuse fitted.
2. O-rings clean, lightly greased, no hairs or grit; window clean and undamaged.
3. Caps fully home; nose ring and tail cone screws tight; gland nuts tight.
4. **Vacuum test: pull -0.2 bar through the vent, plug it, and let the sub check that it holds for 5 minutes.**
5. Magnet on: sub boots, self-test passes (listen for the "OK" beep pattern).
6. Camera connected and recording when armed; microSD has space.
7. GPS fix and LoRa link to the shore station confirmed.
8. Mission loaded, boundary set, max depth set, start delay set.
9. Thrusters spin freely, props tight, no loose cables near the props.
10. Recovery kit ready: pole/net, spare magnet, towel, the shore station.

## 5.5 After every session

1. Rinse the outside in fresh tap water, especially the motors, and dry it.
2. Spray the motors with corrosion inhibitor.
3. Open the hull, check for any moisture (and look at the hull humidity in the log).
4. Download the log and the video, charge the battery outside the hull.
5. **Check, Clean, Dry** before going to a different lake, so you don't carry invasive species (like killer
   shrimp) between waters. This is official UK guidance for all water users.

## 5.6 Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| Vacuum leaks slowly | Gland thread, window bedding, porous cap | Soapy-water test; re-seal; epoxy-coat the cap again |
| Sub won't dive with full vertical thrust | Too much reserve buoyancy | Add lead shot (target 45 g positive) |
| Sub pitches nose-down when diving | Vertical thrusters not over the centre of gravity | Move lead between the pods |
| Heading drifts underwater | Compass disturbed | Re-calibrate in the assembled sub; check for steel parts near the IMU; the ALIGN step corrects at each surfacing |
| Depth oscillates | Kp too high or Kd too low | Halve Kp, raise Kd |
| GPS takes ages | Mast too low in the water, or no clear sky | Remove some lead; check the mast is upright |
| Camera stops recording | Overheating on land, or the Wi-Fi link dropped | Keep land time short; check the camera's Wi-Fi settings |
| Random resets when thrusters start | Supply dips | Check the ESC's capacitor, the XT30 lead and the thrust rate limit |

## 5.7 Safety and the law

* **Batteries:** charge outside the hull, on a non-flammable surface, never unattended. If the hull floods,
  disconnect the battery straight away and leave it outside to dry. Throw away any cell that has been soaked or swells.
* **Water safety:** never operate alone near deep water. Stay out of swimming areas and keep well away from boats,
  anglers' lines and wildlife (especially nesting birds in spring).
* **Permission:** every lake, canal and river belongs to someone. Get the landowner's or the navigation
  authority's permission first (for example the Canal & River Trust for canals). Most drinking-water reservoirs do not allow it.
  Swimming pools: ask the manager; a clean, dry sub and a short session make it easier to say yes.
* **Radio:** in the UK and EU, 868.0–868.6 MHz LoRa is licence-free at up to 25 mW with a 1 % duty cycle.
  The firmware settings in the electronics doc stay inside that.
* **Losing it:** the sub floats when anything fails, flashes its strobe and keeps sending its GPS position over
  LoRa. Put your phone number on the hull in case someone else finds it.
