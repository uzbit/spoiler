# Spoiler Riser

3D-printed riser that sits between an aftermarket spoiler and the trunk lid of
a 2016 Subaru Crosstrek, lifting the spoiler ~4.1 cm while keeping it level on
the trunk's angled surface.

Two pieces are produced per build — one per spoiler foot — that are mirror
images of each other, accounting for the car's trunk crown.

## Pipeline

Each script writes intermediate artifacts to `output/`. Run in order:

1. **`extract_foot.py`** — segments the foot pad outline from photos
2. **`fit_concave.py`** — concave-hull fit to clean the outline
3. **`overlay_avg.py`** — averages the two feet's contours into one canonical
   foot frame (`foot_models_cm.json`)
4. **`find_bolts.py`** — detects bolt positions from cyan paint dots; enforces
   the 5.7 cm bolt spacing constraint (`bolt_positions.json`)
5. **`build_riser.py`** — lofts the riser with a hyperbolic waist, tilts the
   bottom to match the trunk slope (front-back + side-to-side), and cuts the
   washer counterbore + hex pocket + stud clearance hole. Exports both
   canonical and mirrored STL/STEP.
6. **`preview_riser.py`** — multi-view PNG preview of the resulting STL

## Build

```
uv run python build_riser.py
uv run python preview_riser.py
```

### Output files

- `output/riser.stl` + `.step` — canonical piece
- `output/riser_mirrored.stl` + `.step` — opposite-side piece (mirror across XZ)
- `output/riser_preview.png` — 5-panel preview (iso, side, front, top, bottom)

## Key parameters (`build_riser.py`)

| Parameter | Default | Meaning |
|---|---|---|
| `RISER_HEIGHT` | 41.2 mm | Riser height at the foot center |
| `TILT_ANGLE_DEG` | 8.3° | Front-back trunk slope (foot pad ~level fore-aft, so full slope) |
| `SIDE_TILT_DEG` | 2.4° | Side-to-side riser wedge = trunk slope 5.9° − spoiler foot-pad cant 3.5° |
| `FLIP_FOOT_Y` | `True` | Flip foot pad in Y so canonical = LEFT-side piece |
| `STUD_CLEARANCE_DIA` | 7.0 mm | M5 stud through-hole |
| `WASHER_OD` | 25.0 mm | Fender washer OD |
| `WASHER_THICKNESS` | 1.0 mm | Per-washer thickness |
| `NUM_WASHERS_PER_BOLT` | 3 | Washers per bolt |
| `HEX_NUT_AF` | 10.0 mm | Hex nut across flats |
| `HEX_NUT_LENGTH` | 17.7 mm | Hex nut total length |
| `HEX_AF_CLEARANCE` | 0.5 mm | Pocket AF clearance over `HEX_NUT_AF` (must stay under bolt's 11.1 mm across-corners to prevent rotation) |
| `LOCKNUT_THICKNESS` | 2.0 mm | Locknut sits below the hex nut in the hex pocket |
| `HEX_POCKET_HEADROOM` | 5.0 mm | Slack below the locknut |

## Measurements

| Item | Value |
|---|---|
| Bolt-to-bolt distance | 57.00 mm (5.7 cm) — measured 62 mm OD-to-OD on the real spoiler minus 5 mm stud diameter |
| Foot pad bounding | ~13 cm × 6 cm |
| Trunk tilt — front-back | 8.3° (left foot) / 7.8° (right) |
| Trunk tilt — side-to-side | 5.9° (left) / 5.4° (right) |
| Spoiler foot-pad cant — side | 3.5° (the pad isn't flat to the trunk) |
| Riser side wedge (used) | 2.4° = trunk 5.9° − foot-pad 3.5° |

The riser only needs the *difference* between the trunk slope and the spoiler's
own foot-pad angle. Side-to-side the pad is canted ~3.5°, so the riser wedge is
5.9° − 3.5° = 2.4° (building the full 5.9° floats the inboard edge ~4–5 mm).
Fore-aft the pad is ~level, so the riser takes the full 8.3°.

Counterbore stack at each bolt position (top → bottom):

1. **Ø27.5 mm washer counterbore, 5.0 mm deep** (3 × 1 mm washers + 2.0 mm seat clearance)
2. **10.5 mm AF hex pocket, 24.7 mm deep** (17.7 hex nut + 2 locknut + 5 headroom)
3. **Ø7 mm stud clearance hole** continuing through to the bottom face

Total cavity: 29.7 mm from the top face. At the front bolt (riser ~37 mm tall
there) this leaves ~7 mm of bottom-wall material below the hex pocket.

## Printing

Orient with the **flat top face on the build plate** (model upside-down from
its installed orientation):

- Top face is horizontal and flat → maximum bed contact
- Tilted bottom becomes the upper surface → ~10° slope is fine without supports
- Washer counterbore + hex pocket + stud hole all open downward → printable
  without internal supports

Print `riser.stl` and `riser_mirrored.stl` separately. They are *not*
identical pieces — each is handed for its respective side of the car.
