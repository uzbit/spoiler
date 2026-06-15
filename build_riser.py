"""
Build the 3D riser by lofting the foot contour through multiple Z layers,
with a hyperbolic waist that narrows in the middle and widens to top/bottom.
The TOP is a horizontal plane (so the spoiler sits level) and the BOTTOM is
tilted to match the car's trunk slope.

Profile (scale vs. height):
    z_norm = (z - H/2) / (H/2)        # -1 at bottom, +1 at top
    s(z)   = waist_min + (1 - waist_min) * (cosh(k * z_norm) - 1) / (cosh(k) - 1)
At the middle (z_norm = 0): s = waist_min  (narrowest)
At the edges (|z_norm| = 1): s = 1.0       (full contour)
"""

import json
import numpy as np
import cadquery as cq

# ---------- parameters (mm) ----------
RISER_HEIGHT = 39.2            # mm, AVERAGE height (was 90; minus 2" = 50.8 mm)
INNER_SCALE = 0.98             # apply 0.98 fit margin to the contour

# Trunk lid tilt. +X end of the foot pad faces the front of the car (toward the
# roof, where the trunk surface is HIGH); -X faces the rear (where trunk is LOW).
# The riser BOTTOM is tilted to match the trunk; the TOP stays horizontal so the
# spoiler sits level. Net effect: riser is short at +X, tall at -X.
# *** Guess from PXL_20260609_173925625.jpg — refine with a real measurement. ***
TILT_ANGLE_DEG = 8.3

# Side-to-side tilt (across the foot pad's short axis). The trunk lid crowns at
# the car's centerline, so each foot pad sits on a slight side slope: inboard
# is HIGH, outboard is LOW. Canonical riser is built with +Y = inboard, so it's
# SHORT at +Y and TALL at -Y. Mirroring across XZ flips Y for the other piece,
# producing the opposite-handed slope automatically.
SIDE_TILT_DEG = 5.8

# The photos give the contour and bolts in the orientation of the RIGHT foot of
# the spoiler in CAD's +Y direction. The SIDE_TILT_DEG above was set up assuming
# +Y = inboard for the LEFT foot, so the canonical's top didn't match its bottom
# (printed test: riser.stl bottom matched the LEFT side of the car, but the top
# matched the RIGHT foot of the spoiler). Flipping Y of the foot pad aligns the
# top to the LEFT foot, making the canonical fully consistent as the LEFT-side
# riser. Mirror across XZ then yields the RIGHT-side piece.
FLIP_FOOT_Y = True

# Hyperbolic waist
WAIST_MIN_SCALE = 0.82         # narrowest cross-section (fraction of full)
WAIST_K = 2.2                  # higher = flatter middle, sharper transition
NUM_LAYERS = 17                # cross-sections used for lofting

# Stud clearance through-hole. The M5 stud (or threaded rod) passes the full
# height of the riser from the spoiler foot pad above into the trunk lid below.
STUD_CLEARANCE_DIA = 7.0       # mm, M5 thread + 2mm clearance

# Washer stack: 3 washers per bolt, sitting on TOP of the riser between the
# riser's upper face and the spoiler foot pad above. Counterbore is cut from
# the TOP of the riser downward.
# *** All values are guesses — refine with calipers later. ***
WASHER_OD = 25.0               # mm, measured
WASHER_THICKNESS = 1.0         # mm, per washer (measured)
NUM_WASHERS_PER_BOLT = 3
WASHER_DIA_CLEARANCE = 0.5     # mm, added to OD for slip fit
WASHER_DEPTH_CLEARANCE = 0.3   # mm, added to depth so foot pad seats on the top face of the riser

COUNTERBORE_DIA = WASHER_OD + WASHER_DIA_CLEARANCE
COUNTERBORE_DEPTH = NUM_WASHERS_PER_BOLT * WASHER_THICKNESS + WASHER_DEPTH_CLEARANCE
# The locknut sits below the hex nut (inside the hex pocket's leeway space),
# not in this wide washer counterbore — so it's not included here.

# Hex nut pocket nested inside the washer counterbore (sits directly below it).
# Sized so the hex nut slips in snugly — small AF clearance for print tolerance.
HEX_NUT_AF = 10.0              # mm, across flats (measured)
HEX_NUT_LENGTH = 17.7          # mm, total length (measured)
HEX_AF_CLEARANCE = 0.5         # mm, pocket AF must stay under the bolt's 11.1 mm across-corners to prevent free rotation
HEX_POCKET_AF = HEX_NUT_AF + HEX_AF_CLEARANCE

# Hex pocket holds the hex nut stacked on top of the locknut directly beneath
# it, plus a bit of headroom.
LOCKNUT_THICKNESS = 2.0        # mm, measured
HEX_POCKET_HEADROOM = 5.0      # mm, slack below the locknut
HEX_POCKET_DEPTH = HEX_NUT_LENGTH + LOCKNUT_THICKNESS + HEX_POCKET_HEADROOM


def load_avg_contour_mm():
    with open("output/foot_models_cm.json") as f:
        data = json.load(f)
    pts_cm = np.array(data["foot_avg_cm"], dtype=float)
    if FLIP_FOOT_Y:
        pts_cm[:, 1] = -pts_cm[:, 1]
        pts_cm = pts_cm[::-1].copy()  # preserve loft winding direction
    return pts_cm * 10.0 * INNER_SCALE  # to mm + inset


def load_bolt_positions_mm():
    with open("output/bolt_positions.json") as f:
        data = json.load(f)
    bolts_cm = data["final_bolts_cm"]
    if FLIP_FOOT_Y:
        bolts_cm = [(x, -y) for (x, y) in bolts_cm]
    return [(float(x) * 10.0, float(y) * 10.0) for (x, y) in bolts_cm]


def waist_scales(num_layers, height, waist_min, k):
    z_values = np.linspace(0, height, num_layers)
    z_norm = (z_values - height / 2.0) / (height / 2.0)
    cosh_k = np.cosh(k)
    scales = waist_min + (1.0 - waist_min) * (np.cosh(k * z_norm) - 1.0) / (cosh_k - 1.0)
    return z_values, scales


def build_riser():
    contour = load_avg_contour_mm()
    x_min, x_max = float(contour[:, 0].min()), float(contour[:, 0].max())
    y_min, y_max = float(contour[:, 1].min()), float(contour[:, 1].max())

    # Build the loft tall enough to absorb both tilts. Worst-case z-bump above
    # the bottom-ref plane is at the corner where both tilts add up most.
    tilt_x_rad = np.radians(TILT_ANGLE_DEG)
    tilt_y_rad = np.radians(SIDE_TILT_DEG)
    var_x = max(abs(x_min), abs(x_max)) * np.tan(tilt_x_rad)
    var_y = max(abs(y_min), abs(y_max)) * np.tan(tilt_y_rad)
    max_var = var_x + var_y
    build_height = RISER_HEIGHT + max_var + 5.0  # +5mm safety margin
    bottom_ref_z = build_height - RISER_HEIGHT   # tilted plane passes through this at x=y=0

    print(f"contour X range: {x_min:.1f} → {x_max:.1f} mm  Y range: {y_min:.1f} → {y_max:.1f} mm")
    print(f"X-tilt {TILT_ANGLE_DEG}° → ±{var_x:.1f} mm  |  Y-tilt {SIDE_TILT_DEG}° → ±{var_y:.1f} mm")
    print(f"Height corners (approx):")
    print(f"  +X +Y (front, inboard, SHORTEST): {RISER_HEIGHT - var_x - var_y:.1f} mm")
    print(f"  -X -Y (rear,  outboard, TALLEST): {RISER_HEIGHT + var_x + var_y:.1f} mm")
    print(f"build_height={build_height:.1f}, bottom_ref_z={bottom_ref_z:.1f}")

    z_values, scales = waist_scales(NUM_LAYERS, build_height, WAIST_MIN_SCALE, WAIST_K)

    # Build a workplane chain with one polyline per layer, then loft
    wp = cq.Workplane("XY")
    for i, (z, s) in enumerate(zip(z_values, scales)):
        scaled = contour * s
        pts = [(float(p[0]), float(p[1])) for p in scaled]
        if i == 0:
            wp = wp.polyline(pts).close()
        else:
            wp = wp.workplane(offset=(z - z_values[i - 1])).polyline(pts).close()

    riser = wp.loft(combine=True, ruled=False)

    # Tilt cut at the bottom. Two rotations of a large half-space whose top face
    # starts at z=bottom_ref_z:
    #   - about Y axis by +TILT_ANGLE_DEG → +X side rises (riser short at +X = front)
    #   - about X axis by +SIDE_TILT_DEG  → +Y side rises (riser short at +Y = inboard)
    big = 1000.0
    cutter = (
        cq.Workplane("XY")
        .workplane(offset=bottom_ref_z - big)
        .box(big, big, big, centered=(True, True, False))
    )
    cutter = cutter.rotate((0, 0, bottom_ref_z), (0, 1, bottom_ref_z), TILT_ANGLE_DEG)
    cutter = cutter.rotate((0, 0, bottom_ref_z), (1, 0, bottom_ref_z), SIDE_TILT_DEG)
    riser = riser.cut(cutter)

    # Bolt positions from find_bolts.py (mm, foot-local)
    bolt_pts = load_bolt_positions_mm()
    print(f"bolt positions (mm): {bolt_pts}")

    overshoot = 1.0

    for (bx, by) in bolt_pts:
        # Full-height clearance hole for the M5 stud (covers entire z range)
        stud_cut = (
            cq.Workplane("XY")
            .workplane(offset=-overshoot)
            .center(bx, by)
            .circle(STUD_CLEARANCE_DIA / 2.0)
            .extrude(build_height + 2 * overshoot)
        )
        riser = riser.cut(stud_cut)

        # Counterbore from the (horizontal) top face for the 3-washer stack
        washer_cut = (
            cq.Workplane("XY")
            .workplane(offset=build_height - COUNTERBORE_DEPTH)
            .center(bx, by)
            .circle(COUNTERBORE_DIA / 2.0)
            .extrude(COUNTERBORE_DEPTH + overshoot)
        )
        riser = riser.cut(washer_cut)

        # Hex pocket nested directly beneath the washer counterbore
        hex_corners = HEX_POCKET_AF * 2.0 / np.sqrt(3.0)
        hex_top_z = build_height - COUNTERBORE_DEPTH
        hex_cut = (
            cq.Workplane("XY")
            .workplane(offset=hex_top_z - HEX_POCKET_DEPTH)
            .center(bx, by)
            .polygon(6, hex_corners)
            .extrude(HEX_POCKET_DEPTH + 0.1)  # small overshoot into the washer counterbore region
        )
        riser = riser.cut(hex_cut)

    return riser


def main():
    print(f"X-tilt: {TILT_ANGLE_DEG}° (+X=front, trunk slopes down toward rear)")
    print(f"Y-tilt: {SIDE_TILT_DEG}° (+Y=inboard for canonical; mirror flips it for the other piece)")
    print(f"Stud clearance: {STUD_CLEARANCE_DIA:.2f}mm dia through-hole")
    print(f"Washer counterbore (top): dia={COUNTERBORE_DIA:.2f}mm  depth={COUNTERBORE_DEPTH:.2f}mm "
          f"(for {NUM_WASHERS_PER_BOLT} × {WASHER_THICKNESS}mm washers)")
    print(f"Hex pocket (below washers): {HEX_POCKET_AF:.2f}mm AF  depth={HEX_POCKET_DEPTH:.2f}mm "
          f"(hex nut {HEX_NUT_LENGTH}mm + locknut {LOCKNUT_THICKNESS}mm + headroom {HEX_POCKET_HEADROOM}mm)")
    print(f"Total cavity depth: {COUNTERBORE_DEPTH + HEX_POCKET_DEPTH:.1f}mm")

    riser = build_riser()
    cq.exporters.export(riser, "output/riser.stl")
    cq.exporters.export(riser, "output/riser.step")
    print("Exported output/riser.stl and output/riser.step")
    bb = riser.val().BoundingBox()
    print(f"Bounding box: X={bb.xlen:.1f}mm  Y={bb.ylen:.1f}mm  Z={bb.zlen:.1f}mm")

    # Mirror across the XZ plane (y -> -y) to produce the opposite-side piece.
    # See find_bolts.py:113-114: the two feet are mirror images across the x-axis.
    riser_mirrored = riser.mirror(mirrorPlane="XZ")
    cq.exporters.export(riser_mirrored, "output/riser_mirrored.stl")
    cq.exporters.export(riser_mirrored, "output/riser_mirrored.step")
    print("Exported output/riser_mirrored.stl and output/riser_mirrored.step")


if __name__ == "__main__":
    main()
