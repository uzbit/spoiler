"""Zoom in on each corner to see how well the smoothed contour matches the raw."""

import json
import numpy as np
import matplotlib.pyplot as plt
import cv2


def main():
    img_path = "images/old/footing/PXL_20260326_221531091.jpg"
    json_path = "output/PXL_20260326_221531091_8points.json"

    img = cv2.imread(img_path)
    with open(json_path) as f:
        data = json.load(f)

    raw = np.array(data["raw_contour_px"])
    smoothed = np.array(data["smoothed_contour_px"])

    # Find the 4 bounding box corners as ROI centers
    minx, maxx = smoothed[:, 0].min(), smoothed[:, 0].max()
    miny, maxy = smoothed[:, 1].min(), smoothed[:, 1].max()

    pad = 400
    rois = {
        "top-left":     (minx, miny),
        "top-right":    (maxx, miny),
        "bottom-right": (maxx, maxy),
        "bottom-left":  (minx, maxy),
    }

    fig, axes = plt.subplots(1, 4, figsize=(28, 8))
    for ax, (name, (cx, cy)) in zip(axes, rois.items()):
        ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        ax.plot(raw[:, 0], raw[:, 1], 'co', markersize=4, label='raw contour')
        sclosed = np.vstack([smoothed, smoothed[0]])
        ax.plot(sclosed[:, 0], sclosed[:, 1], 'y-', linewidth=3, label='smoothed')
        ax.set_xlim(cx - pad, cx + pad)
        ax.set_ylim(cy + pad, cy - pad)  # invert for image coords
        ax.set_title(name)

    axes[0].legend(fontsize=10, loc='upper right')
    plt.tight_layout()
    plt.savefig("output/corner_zoom.png", dpi=150)
    plt.close()
    print("Saved output/corner_zoom.png")


if __name__ == "__main__":
    main()
