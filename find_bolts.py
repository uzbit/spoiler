"""
Find bolt positions from cyan (#02fef9) hand-drawn circles in each image.
The two foot pads are mirror images of each other (flipped vertically), so
we average their bolt positions accordingly to get the canonical bolt layout.
"""

import json
import numpy as np
import cv2
import matplotlib.pyplot as plt
from pathlib import Path

REAL_LENGTH_CM = 13.0


def detect_cyan_circles(image_path):
    """Detect cyan (#02fef9) dots placed on bolt tips. Returns 2 centroids
    sorted left-to-right."""
    img = cv2.imread(image_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Exact match for #02fef9 (BGR = 249, 254, 2; HSV ≈ (89, 253, 254)).
    # Use a tight tolerance so we don't pick up other paint blobs.
    mask_cyan = cv2.inRange(hsv, np.array([86, 230, 230]), np.array([92, 255, 255]))

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask_cyan, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bolts = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < 30:
            continue
        M = cv2.moments(c)
        if M["m00"] == 0:
            continue
        cx = M["m10"] / M["m00"]
        cy = M["m01"] / M["m00"]
        bolts.append((area, cx, cy))

    bolts.sort(key=lambda b: -b[0])
    bolts = bolts[:2]
    if len(bolts) != 2:
        print(f"Warning: found {len(bolts)} cyan dots in {image_path}")
        return None
    bolts.sort(key=lambda b: b[1])  # left-to-right by x
    return [(b[1], b[2]) for b in bolts]


def get_foot_centroid_and_scale(image_path):
    """Same logic as model_foot.normalize_to_cm to get centroid_px and px_per_cm."""
    img = cv2.imread(image_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    mask_green = cv2.inRange(hsv, np.array([40, 150, 100]), np.array([85, 255, 255]))
    kernel = np.ones((5, 5), np.uint8)
    closed = cv2.morphologyEx(mask_green, cv2.MORPH_CLOSE, kernel, iterations=5)
    closed = cv2.dilate(closed, kernel, iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    foot_contour = max(contours, key=cv2.contourArea)
    filled = np.zeros(closed.shape, dtype=np.uint8)
    cv2.drawContours(filled, [foot_contour], -1, 255, -1)
    filled = cv2.erode(filled, kernel, iterations=2)
    contours2, _ = cv2.findContours(filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    raw = max(contours2, key=cv2.contourArea).reshape(-1, 2).astype(float)

    centroid = raw.mean(axis=0)
    centered = raw - centroid
    centered_y_flipped = centered.copy()
    centered_y_flipped[:, 1] = -centered_y_flipped[:, 1]
    bbox_w = centered_y_flipped[:, 0].max() - centered_y_flipped[:, 0].min()
    bbox_h = centered_y_flipped[:, 1].max() - centered_y_flipped[:, 1].min()
    longest = max(bbox_w, bbox_h)
    px_per_cm = longest / REAL_LENGTH_CM
    return centroid, px_per_cm


def bolts_to_cm(bolts_px, centroid_px, px_per_cm):
    """Convert pixel coords to foot-local cm (centered, y flipped to math coords)."""
    out = []
    for (bx, by) in bolts_px:
        cx = (bx - centroid_px[0]) / px_per_cm
        cy = -(by - centroid_px[1]) / px_per_cm
        out.append((cx, cy))
    return out


def main():
    img1 = "images/old/footing/PXL_20260326_221531091.jpg"
    img2 = "images/old/footing/PXL_20260326_221543814.jpg"

    b1_px = detect_cyan_circles(img1)
    b2_px = detect_cyan_circles(img2)
    c1, s1 = get_foot_centroid_and_scale(img1)
    c2, s2 = get_foot_centroid_and_scale(img2)

    b1_cm = bolts_to_cm(b1_px, c1, s1)
    b2_cm = bolts_to_cm(b2_px, c2, s2)

    print("Foot 1 (raw cm):")
    for i, b in enumerate(b1_cm):
        print(f"  bolt {i}: x={b[0]:+.2f}  y={b[1]:+.2f}")
    print(f"  bolt-to-bolt: {np.linalg.norm(np.array(b1_cm[0]) - np.array(b1_cm[1])):.2f} cm")

    print("\nFoot 2 (raw cm):")
    for i, b in enumerate(b2_cm):
        print(f"  bolt {i}: x={b[0]:+.2f}  y={b[1]:+.2f}")
    print(f"  bolt-to-bolt: {np.linalg.norm(np.array(b2_cm[0]) - np.array(b2_cm[1])):.2f} cm")

    # The two feet are mirror images flipped vertically (across x-axis).
    # So flip foot2's y-coords to align with foot1's frame.
    b2_in_foot1_frame = [(x, -y) for (x, y) in b2_cm]
    # After this flip, foot2's bolts should overlap with foot1's bolts.

    # Average them
    avg = []
    for i in range(2):
        ax = (b1_cm[i][0] + b2_in_foot1_frame[i][0]) / 2.0
        ay = (b1_cm[i][1] + b2_in_foot1_frame[i][1]) / 2.0
        avg.append((ax, ay))

    print("\nAveraged bolt positions (foot1 frame, cm):")
    for i, b in enumerate(avg):
        print(f"  bolt {i}: x={b[0]:+.2f}  y={b[1]:+.2f}")
    avg_dist = float(np.linalg.norm(np.array(avg[0]) - np.array(avg[1])))
    print(f"  bolt-to-bolt: {avg_dist:.2f} cm  (target: {5.7} cm)")

    # Apply additional constraint: scale to exactly 5.7 cm bolt-to-bolt
    # (measured 62 mm OD-to-OD on the real spoiler, minus 5 mm stud diameter)
    # while keeping the midpoint fixed
    target = 5.7
    midpt = ((avg[0][0] + avg[1][0]) / 2.0, (avg[0][1] + avg[1][1]) / 2.0)
    if avg_dist > 0:
        scale_factor = target / avg_dist
        constrained = []
        for b in avg:
            dx = b[0] - midpt[0]
            dy = b[1] - midpt[1]
            constrained.append((midpt[0] + dx * scale_factor, midpt[1] + dy * scale_factor))
    else:
        constrained = avg

    print(f"\nConstrained to exactly {target} cm bolt-to-bolt (midpoint preserved):")
    for i, b in enumerate(constrained):
        print(f"  bolt {i}: x={b[0]:+.2f}  y={b[1]:+.2f}")

    # The two bolts are physically at the same y; average their y values
    y_avg = (constrained[0][1] + constrained[1][1]) / 2.0
    final = [(constrained[0][0], y_avg), (constrained[1][0], y_avg)]
    print("\nFinal (forced equal y):")
    for i, b in enumerate(final):
        print(f"  bolt {i}: x={b[0]:+.2f}  y={b[1]:+.2f}")

    out = {
        "foot1_bolts_cm": b1_cm,
        "foot2_bolts_cm": b2_cm,
        "averaged_bolts_cm": avg,
        "constrained_bolts_cm": constrained,
        "final_bolts_cm": final,
        "bolt_spacing_cm": float(np.linalg.norm(np.array(final[0]) - np.array(final[1]))),
    }
    with open("output/bolt_positions.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nSaved output/bolt_positions.json")

    # Visualization: draw the final bolt positions on top of both images
    def project_back(bolts_cm, centroid_px, px_per_cm, flip_y=False):
        out = []
        for (cx, cy) in bolts_cm:
            if flip_y:
                cy = -cy
            x = cx * px_per_cm + centroid_px[0]
            y = -cy * px_per_cm + centroid_px[1]
            out.append((x, y))
        return out

    final_px_foot1 = project_back(final, c1, s1, flip_y=False)
    # foot2's frame is the flipped one; flip back
    final_px_foot2 = project_back(final, c2, s2, flip_y=True)

    # Show RAW detected dots (yellow) vs averaged-projected (red) on both images
    fig, axes = plt.subplots(1, 2, figsize=(20, 8))
    for ax, img_path, raw_px, fps, title in [
        (axes[0], img1, b1_px, final_px_foot1, "Foot 1: yellow=raw detected, red=averaged"),
        (axes[1], img2, b2_px, final_px_foot2, "Foot 2: yellow=raw detected, red=averaged"),
    ]:
        img = cv2.imread(img_path)
        ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        for (bx, by) in raw_px:
            ax.plot(bx, by, 'y+', markersize=25, markeredgewidth=4)
            ax.add_patch(plt.Circle((bx, by), 60, fill=False, color='yellow', linewidth=3))
        for (bx, by) in fps:
            ax.plot(bx, by, 'r+', markersize=20, markeredgewidth=3)
            ax.add_patch(plt.Circle((bx, by), 40, fill=False, color='red', linewidth=2))
        ax.set_title(title)
        ax.axis('off')
    plt.tight_layout()
    plt.savefig("output/bolts_final.png", dpi=150)
    plt.close()
    print("Saved output/bolts_final.png")


if __name__ == "__main__":
    main()
