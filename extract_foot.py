"""
Extract foot pad outline from green (#02fe02) marker line, then relax
(shrink-wrap) a smooth closed curve onto the data points.
Active-contour style: external force = attraction to nearest data point,
internal force = smoothing toward neighbor midpoint.
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
import json
from pathlib import Path
from scipy.optimize import minimize
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks


# ---------- helpers ----------

def resample_arclength(pts, num_samples):
    closed = np.vstack([pts, pts[0]])
    diffs = np.diff(closed, axis=0)
    seg_lens = np.linalg.norm(diffs, axis=1)
    cum = np.concatenate([[0], np.cumsum(seg_lens)])
    target_s = np.linspace(0, cum[-1], num_samples, endpoint=False)
    rx = np.interp(target_s, cum, closed[:, 0])
    ry = np.interp(target_s, cum, closed[:, 1])
    return np.column_stack([rx, ry])


def detect_4_corners(pts):
    n = len(pts)
    sx = gaussian_filter1d(pts[:, 0], 6.0, mode="wrap")
    sy = gaussian_filter1d(pts[:, 1], 6.0, mode="wrap")
    win = 8
    curv = np.zeros(n)
    for i in range(n):
        a = np.array([sx[(i - win) % n] - sx[i], sy[(i - win) % n] - sy[i]])
        b = np.array([sx[(i + win) % n] - sx[i], sy[(i + win) % n] - sy[i]])
        cross = a[0] * b[1] - a[1] * b[0]
        dot = a[0] * b[0] + a[1] * b[1]
        curv[i] = np.pi - np.arctan2(abs(cross), dot)
    curv = gaussian_filter1d(curv, 4, mode="wrap")
    doubled = np.concatenate([curv, curv])
    peaks, _ = find_peaks(doubled, distance=n // 8)
    sorted_peaks = peaks[np.argsort(doubled[peaks])[::-1]]
    unique = []
    for p in sorted_peaks:
        idx = p % n
        if all(min(abs(idx - u), n - abs(idx - u)) > n // 12 for u in unique):
            unique.append(idx)
        if len(unique) >= 4:
            break
    return sorted(unique)


def fit_line_tls(points):
    """Total least-squares line fit. Returns (point_on_line, direction_unit)."""
    centroid = points.mean(axis=0)
    centered = points - centroid
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    direction = vt[0]
    direction = direction / np.linalg.norm(direction)
    return centroid, direction


def line_intersection(p1, d1, p2, d2):
    A = np.column_stack([d1, -d2])
    if abs(np.linalg.det(A)) < 1e-10:
        return None
    ts = np.linalg.solve(A, p2 - p1)
    return p1 + ts[0] * d1


def fit_quarter_superellipse(points_uv):
    """Fit (u/a)^n + (v/b)^n = 1 to points in local (u,v) coords (positive quadrant)."""
    u = np.abs(points_uv[:, 0])
    v = np.abs(points_uv[:, 1])
    a0 = u.max()
    b0 = v.max()
    n0 = 4.0

    def loss(params):
        a, b, n = params
        if a <= 1 or b <= 1 or n < 2.0 or n > 30.0:
            return 1e12
        ang = np.arctan2(v, u)
        ct = np.abs(np.cos(ang))
        st = np.abs(np.sin(ang))
        r_pred = (((ct / a) ** n + (st / b) ** n)) ** (-1.0 / n)
        r_obs = np.sqrt(u * u + v * v)
        return np.sum((r_pred - r_obs) ** 2)

    res = minimize(loss, [a0, b0, n0], method="Nelder-Mead",
                   options={"xatol": 1e-4, "fatol": 1e-4, "maxiter": 10000})
    return res.x


def quarter_superellipse_curve(a, b, n, num=60):
    """Quarter superellipse fillet from (a, 0) to (0, b) bulging TOWARD origin."""
    t = np.linspace(0, np.pi / 2, num)
    ct = np.cos(t)
    st = np.sin(t)
    u = a - a * np.abs(st) ** (2.0 / n)
    v = b - b * np.abs(ct) ** (2.0 / n)
    return np.column_stack([u, v])


def snake_relax(data_pts, num_curve_points=80, iterations=400,
                external_weight=0.5, internal_weight=0.4,
                init_scale=1.25):
    """Active contour / snake relaxation.

    Start with a circle that encloses the data, evolve points inward.
    For each iteration:
      - External force: attract each curve point to its nearest data point
      - Internal force: pull toward midpoint of neighbors (smoothing)
    """
    centroid = data_pts.mean(axis=0)
    rel = data_pts - centroid
    max_r = np.linalg.norm(rel, axis=1).max()

    # Initialize as a circle with radius max_r * init_scale
    t = np.linspace(0, 2 * np.pi, num_curve_points, endpoint=False)
    init_r = max_r * init_scale
    curve = np.column_stack([init_r * np.cos(t), init_r * np.sin(t)]) + centroid

    for it in range(iterations):
        # External force: each curve point moves toward its nearest data point
        diffs = curve[:, None, :] - data_pts[None, :, :]      # (M, N, 2)
        sqd = np.sum(diffs * diffs, axis=2)                   # (M, N)
        nearest_idx = np.argmin(sqd, axis=1)
        nearest = data_pts[nearest_idx]                       # (M, 2)
        ext_force = nearest - curve

        # Internal force: pull toward midpoint of neighbors
        prev_pts = np.roll(curve, 1, axis=0)
        next_pts = np.roll(curve, -1, axis=0)
        midpts = 0.5 * (prev_pts + next_pts)
        int_force = midpts - curve

        curve = curve + external_weight * ext_force + internal_weight * int_force

    return curve


# ---------- main extraction ----------

def extract_foot(image_path, output_dir="output"):
    Path(output_dir).mkdir(exist_ok=True)
    stem = Path(image_path).stem

    img = cv2.imread(image_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    mask_green = cv2.inRange(hsv, np.array([40, 150, 100]), np.array([85, 255, 255]))
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask_green, cv2.MORPH_CLOSE, kernel, iterations=5)
    mask = cv2.dilate(mask, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        print(f"No green contour in {image_path}")
        return
    contour = max(contours, key=cv2.contourArea)
    filled = np.zeros(mask.shape, dtype=np.uint8)
    cv2.drawContours(filled, [contour], -1, 255, -1)
    filled = cv2.erode(filled, kernel, iterations=2)
    contours2, _ = cv2.findContours(filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    raw = max(contours2, key=cv2.contourArea).reshape(-1, 2).astype(float)

    # Resample raw contour to a manageable size for the relaxation
    data_pts = resample_arclength(raw, 600)

    # Snake relaxation: shrink an initial circle onto the data
    smoothed = snake_relax(
        data_pts,
        num_curve_points=120,
        iterations=400,
        external_weight=0.5,
        internal_weight=0.4,
        init_scale=1.25,
    )

    # Visualization
    fig, axes = plt.subplots(1, 3, figsize=(21, 7))
    axes[0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    axes[0].plot(raw[:, 0], raw[:, 1], 'g-', linewidth=1)
    axes[0].set_title(f"Raw contour ({len(raw)} pts)")
    axes[0].axis('off')

    axes[1].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    axes[1].plot(data_pts[:, 0], data_pts[:, 1], 'co', markersize=2, alpha=0.5)
    closed = np.vstack([smoothed, smoothed[0]])
    axes[1].plot(closed[:, 0], closed[:, 1], 'y-', linewidth=2)
    axes[1].fill(closed[:, 0], closed[:, 1], color='yellow', alpha=0.25)
    axes[1].set_title("Snake-relaxed curve")
    axes[1].axis('off')

    axes[2].plot(data_pts[:, 0], -data_pts[:, 1], 'c.', markersize=2, label='data')
    axes[2].plot(closed[:, 0], -closed[:, 1], 'r-', linewidth=2, label='snake')
    axes[2].set_aspect('equal')
    axes[2].grid(alpha=0.3)
    axes[2].set_title("Snake fit (no image)")
    axes[2].legend()

    plt.tight_layout()
    out_path = f"{output_dir}/{stem}_contour.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved {out_path}")

    with open(f"{output_dir}/{stem}_8points.json", 'w') as f:
        json.dump({
            "image": image_path,
            "image_size": [img.shape[1], img.shape[0]],
            "smoothed_contour_px": smoothed.tolist(),
            "raw_contour_px": raw.tolist(),
        }, f, indent=2)
    print(f"Saved {output_dir}/{stem}_8points.json")


if __name__ == "__main__":
    for img_path in [
        "images/old/footing/PXL_20260326_221531091.jpg",
        "images/old/footing/PXL_20260326_221543814.jpg",
    ]:
        print(f"\n{img_path}:")
        extract_foot(img_path)
