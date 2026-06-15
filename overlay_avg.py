"""
Plot the averaged foot model back onto each original image
in the correct orientation (un-doing the per-image transforms).
"""

import cv2
import json
import numpy as np
import matplotlib.pyplot as plt
from model_foot import (
    load_smoothed,
    normalize_to_cm,
    mirror_vertical,
    weighted_average_outlines,
    REAL_LENGTH_CM,
)


def get_image_transform(pts_px):
    """Returns (centroid_px, px_per_cm) for the px->cm normalization."""
    centroid = pts_px.mean(axis=0)
    centered = pts_px - centroid
    centered[:, 1] = -centered[:, 1]
    bbox_w = centered[:, 0].max() - centered[:, 0].min()
    bbox_h = centered[:, 1].max() - centered[:, 1].min()
    longest = max(bbox_w, bbox_h)
    px_per_cm = longest / REAL_LENGTH_CM
    return centroid, px_per_cm


def cm_to_image(pts_cm, centroid_px, px_per_cm):
    """Inverse of normalize_to_cm: cm math coords -> image pixel coords."""
    out = pts_cm * px_per_cm
    out[:, 1] = -out[:, 1]  # flip y back
    out = out + centroid_px
    return out


def main():
    img1_path = "images/old/footing/PXL_20260326_221531091.jpg"
    img2_path = "images/old/footing/PXL_20260326_221543814.jpg"

    foot1_px = load_smoothed("output/PXL_20260326_221531091_8points.json")
    foot2_px = load_smoothed("output/PXL_20260326_221543814_8points.json")

    foot1_cm = normalize_to_cm(foot1_px)
    foot2_cm = normalize_to_cm(foot2_px)
    foot2_mirrored = mirror_vertical(foot2_cm)
    foot_avg = weighted_average_outlines(foot1_cm, foot2_mirrored, large_weight=0.75)

    # Final shrink so the riser sits inside the marker line
    foot_avg *= 0.98

    # For foot 1: just project avg back onto image
    c1, s1 = get_image_transform(foot1_px)
    avg_on_img1 = cm_to_image(foot_avg.copy(), c1, s1)

    # For foot 2: avg is in foot1's orientation. Apply mirror_vertical to get into
    # foot2's normalized orientation, then project back to image.
    avg_for_foot2 = mirror_vertical(foot_avg)
    c2, s2 = get_image_transform(foot2_px)
    avg_on_img2 = cm_to_image(avg_for_foot2.copy(), c2, s2)

    img1 = cv2.imread(img1_path)
    img2 = cv2.imread(img2_path)

    fig, axes = plt.subplots(1, 2, figsize=(20, 8))

    for ax, img, avg_pts, title in [
        (axes[0], img1, avg_on_img1, "Foot 1 with averaged model"),
        (axes[1], img2, avg_on_img2, "Foot 2 with averaged model"),
    ]:
        ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        closed = np.vstack([avg_pts, avg_pts[0]])
        ax.plot(closed[:, 0], closed[:, 1], 'y-', linewidth=3, label='avg model')
        ax.fill(closed[:, 0], closed[:, 1], color='yellow', alpha=0.25)
        ax.set_title(title)
        ax.axis('off')
        ax.legend()

    plt.tight_layout()
    out_path = "output/avg_on_images.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
