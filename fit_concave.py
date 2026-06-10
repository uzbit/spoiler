"""
Fit a smooth concave shape to the extracted foot contour points.
Remove bottom 4 points (highest y), order by angle, smooth with spline.
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
import json
from scipy.interpolate import splprep, splev


def main():
    img_path = "images/footing/PXL_20260326_221543814.jpg"
    contour_path = "output/PXL_20260326_221543814_contour.json"

    img = cv2.imread(img_path)
    with open(contour_path) as f:
        data = json.load(f)

    points = np.array(data["contour_points_px"], dtype=float)

    # Remove the 4 points with the highest y values
    y_sorted_indices = np.argsort(points[:, 1])
    keep_indices = y_sorted_indices[:-4]
    points = points[keep_indices]

    # Remove the point furthest to the right (highest x)
    rightmost = np.argmax(points[:, 0])
    points = np.delete(points, rightmost, axis=0)

    # Order points by angle from centroid
    centroid = points.mean(axis=0)
    angles = np.arctan2(points[:, 1] - centroid[1], points[:, 0] - centroid[0])
    order = np.argsort(angles)
    ordered = points[order]

    # Close the loop
    closed = np.vstack([ordered, ordered[0]])

    # Fit periodic spline with varying smoothness
    fig, axes = plt.subplots(1, 3, figsize=(24, 8))

    smoothing_values = [0, len(ordered) * 100, len(ordered) * 1000]
    labels = ["No smoothing (interpolate)", "Light smoothing", "Heavy smoothing"]

    for idx, (s_val, label) in enumerate(zip(smoothing_values, labels)):
        ax = axes[idx]
        ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

        tck, u = splprep([closed[:, 0], closed[:, 1]], s=s_val, per=True, k=3)
        u_new = np.linspace(0, 1, 300)
        x_new, y_new = splev(u_new, tck)

        ax.plot(x_new, y_new, 'g-', linewidth=2)
        ax.fill(x_new, y_new, alpha=0.2, color='green')
        ax.plot(points[:, 0], points[:, 1], 'ro', markersize=8)
        ax.set_title(f"{label} (s={s_val})")
        ax.axis('off')

    plt.tight_layout()
    plt.savefig("output/concave_fit.png", dpi=150)
    plt.close()
    print("Saved output/concave_fit.png")

    # Save the medium-smoothed version
    tck, u = splprep([closed[:, 0], closed[:, 1]], s=len(ordered) * 100, per=True, k=3)
    u_new = np.linspace(0, 1, 200)
    x_new, y_new = splev(u_new, tck)
    smoothed = np.column_stack([x_new, y_new])

    with open("output/foot_outline_smoothed.json", 'w') as f:
        json.dump({
            "smoothed_contour_px": smoothed.tolist(),
            "raw_points_ordered_px": ordered.tolist(),
            "image_size": data["image_size"],
        }, f, indent=2)
    print("Saved output/foot_outline_smoothed.json")


if __name__ == "__main__":
    main()
