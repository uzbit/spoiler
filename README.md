# Spoiler Riser

3D-printed riser that sits between an aftermarket spoiler and the trunk lid of
a 2016 Subaru Crosstrek, lifting the spoiler ~3.9 cm while keeping it level on
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
| `RISER_HEIGHT` | 39.2 mm | Average riser height |
| `TILT_ANGLE_DEG` | 8.3° | Front-back trunk slope (riser short at front) |
| `SIDE_TILT_DEG` | 5.8° | Side-to-side trunk crown (riser short inboard) |
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
| Trunk tilt — front-back | 8.3° |
| Trunk tilt — side-to-side (crown) | 5.8° (magnitude; mirrored sign per side) |

Counterbore stack at each bolt position (top → bottom):

1. **Ø25.5 mm washer counterbore, 3.3 mm deep** (3 × 1 mm washers + 0.3 mm seat clearance)
2. **10.5 mm AF hex pocket, 24.7 mm deep** (17.7 hex nut + 2 locknut + 5 headroom)
3. **Ø7 mm stud clearance hole** continuing through to the bottom face

Total cavity: 28.0 mm from the top face. At the front bolt (riser ~36 mm tall
there) this leaves ~8 mm of bottom-wall material below the hex pocket.

## Printing

Orient with the **flat top face on the build plate** (model upside-down from
its installed orientation):

- Top face is horizontal and flat → maximum bed contact
- Tilted bottom becomes the upper surface → ~10° slope is fine without supports
- Washer counterbore + hex pocket + stud hole all open downward → printable
  without internal supports

Print `riser.stl` and `riser_mirrored.stl` separately. They are *not*
identical pieces — each is handed for its respective side of the car.
