"""
Build a 2D model of each foot from the 8-point Chaikin contours.
Scale to real-world cm (13cm long), center on origin, mirror one,
and overlay both to compare.
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import savgol_filter


REAL_LENGTH_CM = 13.0  # measured longest dimension of the foot pad


def load_smoothed(json_path):
    with open(json_path) as f:
        data = json.load(f)
    return np.array(data["smoothed_contour_px"], dtype=float)


def normalize_to_cm(pts, target_length_cm=REAL_LENGTH_CM):
    """Center on centroid, flip y (image coords -> math coords),
    and uniformly scale so longest bounding-box dimension == target_length_cm."""
    centroid = pts.mean(axis=0)
    centered = pts - centroid
    # Image y goes down, world y goes up
    centered[:, 1] = -centered[:, 1]

    bbox_w = centered[:, 0].max() - centered[:, 0].min()
    bbox_h = centered[:, 1].max() - centered[:, 1].min()
    longest = max(bbox_w, bbox_h)
    scale = target_length_cm / longest
    return centered * scale


def mirror_horizontal(pts):
    """Mirror across vertical axis (negate x)."""
    out = pts.copy()
    out[:, 0] = -out[:, 0]
    # Reverse order so winding stays consistent
    return out[::-1]


def mirror_vertical(pts):
    """Mirror across horizontal axis (negate y)."""
    out = pts.copy()
    out[:, 1] = -out[:, 1]
    return out[::-1]


def resample_arclength(pts, num_samples=400):
    """Resample a closed contour uniformly along arc length."""
    closed = np.vstack([pts, pts[0]])
    diffs = np.diff(closed, axis=0)
    seg_lens = np.linalg.norm(diffs, axis=1)
    cum = np.concatenate([[0], np.cumsum(seg_lens)])
    total = cum[-1]
    target_s = np.linspace(0, total, num_samples, endpoint=False)
    rx = np.interp(target_s, cum, closed[:, 0])
    ry = np.interp(target_s, cum, closed[:, 1])
    return np.column_stack([rx, ry])


def align_start(pts):
    """Rotate a closed contour so its starting point is the rightmost point."""
    idx = np.lexsort((pts[:, 1], -pts[:, 0]))[0]
    return np.roll(pts, -idx, axis=0)


def weighted_average_outlines(pts_a, pts_b, large_weight=0.75,
                               sg_window=21, sg_order=3):
    """Average two contours by arc-length sampling with weighted blend
    favoring whichever point is further from the joint centroid.
    Final smoothing uses periodic Savitzky-Golay filter (preserves corners)."""
    a = resample_arclength(pts_a)
    b = resample_arclength(pts_b)
    a = align_start(a)
    b = align_start(b)

    centroid = (a.mean(axis=0) + b.mean(axis=0)) / 2.0
    da = np.linalg.norm(a - centroid, axis=1)
    db = np.linalg.norm(b - centroid, axis=1)

    a_is_larger = (da >= db).astype(float).reshape(-1, 1)
    b_is_larger = 1.0 - a_is_larger
    larger = a * a_is_larger + b * b_is_larger
    smaller = a * b_is_larger + b * a_is_larger

    avg = large_weight * larger + (1.0 - large_weight) * smaller

    # Periodic Savitzky-Golay smoothing
    if sg_window > sg_order:
        pad = sg_window
        out = np.zeros_like(avg)
        for dim in range(2):
            padded = np.concatenate([avg[-pad:, dim], avg[:, dim], avg[:pad, dim]])
            sm = savgol_filter(padded, window_length=sg_window, polyorder=sg_order)
            out[:, dim] = sm[pad:-pad]
        avg = out

    return avg


def main():
    foot1 = load_smoothed("output/PXL_20260326_221531091_8points.json")
    foot2 = load_smoothed("output/PXL_20260326_221543814_8points.json")

    foot1_cm = normalize_to_cm(foot1)
    foot2_cm = normalize_to_cm(foot2)

    # Mirror foot 2 vertically (flip across x axis)
    foot2_mirrored = mirror_vertical(foot2_cm)

    # Weighted average favoring larger radius
    foot_avg = weighted_average_outlines(foot1_cm, foot2_mirrored, large_weight=0.75)
    wa, ha = (foot_avg[:, 0].max() - foot_avg[:, 0].min(),
              foot_avg[:, 1].max() - foot_avg[:, 1].min())
    print(f"Averaged (75% large) bounding box: {wa:.2f} x {ha:.2f} cm")

    # Compute bounding boxes for reporting
    def bbox(pts):
        w = pts[:, 0].max() - pts[:, 0].min()
        h = pts[:, 1].max() - pts[:, 1].min()
        return w, h

    w1, h1 = bbox(foot1_cm)
    w2, h2 = bbox(foot2_cm)
    print(f"Foot 1 bounding box: {w1:.2f} x {h1:.2f} cm")
    print(f"Foot 2 bounding box: {w2:.2f} x {h2:.2f} cm")

    # Plot
    fig, axes = plt.subplots(1, 3, figsize=(21, 7))

    def plot_contour(ax, pts, color, label):
        closed = np.vstack([pts, pts[0]])
        ax.plot(closed[:, 0], closed[:, 1], color=color, linewidth=2, label=label)
        ax.fill(closed[:, 0], closed[:, 1], color=color, alpha=0.2)

    plot_contour(axes[0], foot1_cm, 'blue', 'Foot 1')
    axes[0].set_title("Foot 1 (scaled to cm)")
    axes[0].set_aspect('equal')
    axes[0].grid(True, alpha=0.3)
    axes[0].axhline(0, color='k', linewidth=0.5)
    axes[0].axvline(0, color='k', linewidth=0.5)
    axes[0].set_xlabel("cm")
    axes[0].set_ylabel("cm")
    axes[0].legend()

    plot_contour(axes[1], foot2_cm, 'red', 'Foot 2')
    axes[1].set_title("Foot 2 (scaled to cm)")
    axes[1].set_aspect('equal')
    axes[1].grid(True, alpha=0.3)
    axes[1].axhline(0, color='k', linewidth=0.5)
    axes[1].axvline(0, color='k', linewidth=0.5)
    axes[1].set_xlabel("cm")
    axes[1].set_ylabel("cm")
    axes[1].legend()

    plot_contour(axes[2], foot1_cm, 'blue', 'Foot 1')
    plot_contour(axes[2], foot2_mirrored, 'red', 'Foot 2 (mirrored)')
    plot_contour(axes[2], foot_avg, 'green', 'Avg (75% large)')
    axes[2].set_title("Overlay + weighted avg")
    axes[2].set_aspect('equal')
    axes[2].grid(True, alpha=0.3)
    axes[2].axhline(0, color='k', linewidth=0.5)
    axes[2].axvline(0, color='k', linewidth=0.5)
    axes[2].set_xlabel("cm")
    axes[2].set_ylabel("cm")
    axes[2].legend()

    plt.tight_layout()
    out_path = "output/foot_models_overlay.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved {out_path}")

    # Save the scaled models
    with open("output/foot_models_cm.json", 'w') as f:
        json.dump({
            "foot1_cm": foot1_cm.tolist(),
            "foot2_cm": foot2_cm.tolist(),
            "foot2_mirrored_cm": foot2_mirrored.tolist(),
            "foot_avg_cm": foot_avg.tolist(),
            "real_length_cm": REAL_LENGTH_CM,
        }, f, indent=2)
    print("Saved output/foot_models_cm.json")


if __name__ == "__main__":
    main()
