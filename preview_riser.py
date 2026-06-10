"""Render an isometric and side preview of the riser STL."""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from stl import mesh


def main():
    m = mesh.Mesh.from_file("output/riser.stl")
    tris = m.vectors  # (N, 3, 3)

    fig = plt.figure(figsize=(30, 8))

    # 3/4 isometric view
    ax1 = fig.add_subplot(1, 5, 1, projection="3d")
    coll = Poly3DCollection(tris, edgecolor=(0, 0, 0, 0.05),
                             facecolor=(0.6, 0.6, 0.85, 0.9))
    ax1.add_collection3d(coll)
    pts = tris.reshape(-1, 3)
    for setlim, axis in [(ax1.set_xlim, 0), (ax1.set_ylim, 1), (ax1.set_zlim, 2)]:
        setlim(pts[:, axis].min(), pts[:, axis].max())
    ax1.set_box_aspect([
        np.ptp(pts[:, 0]), np.ptp(pts[:, 1]), np.ptp(pts[:, 2])
    ])
    ax1.view_init(elev=20, azim=35)
    ax1.set_title("Isometric")
    ax1.set_xlabel("X mm")
    ax1.set_ylabel("Y mm")
    ax1.set_zlabel("Z mm")

    # Side (X-Z) silhouette
    ax2 = fig.add_subplot(1, 5, 2)
    ax2.scatter(pts[:, 0], pts[:, 2], s=0.5, alpha=0.3)
    ax2.set_aspect("equal")
    ax2.set_xlabel("X mm")
    ax2.set_ylabel("Z mm (height)")
    ax2.set_title("Side view (X-Z) — see the waist")
    ax2.grid(alpha=0.3)

    # Front (Y-Z) silhouette
    ax3 = fig.add_subplot(1, 5, 3)
    ax3.scatter(pts[:, 1], pts[:, 2], s=0.5, alpha=0.3)
    ax3.set_aspect("equal")
    ax3.set_xlabel("Y mm")
    ax3.set_ylabel("Z mm (height)")
    ax3.set_title("Front view (Y-Z)")
    ax3.grid(alpha=0.3)

    # Top (X-Y) view at z = top of riser, showing washer counterbores
    ax4 = fig.add_subplot(1, 5, 4)
    z_top = pts[:, 2].max()
    top_mask = pts[:, 2] > (z_top - 0.5)
    top_pts = pts[top_mask]
    ax4.scatter(top_pts[:, 0], top_pts[:, 1], s=2, alpha=0.7, color='black')
    ax4.set_aspect("equal")
    ax4.set_xlabel("X mm")
    ax4.set_ylabel("Y mm")
    ax4.set_title("Top view — washer counterbores + stud holes")
    ax4.grid(alpha=0.3)

    # Bottom (X-Y) view: project triangles that face downward (handles a tilted
    # bottom face — a flat Z-slice would miss most of it).
    ax5 = fig.add_subplot(1, 5, 5)
    v1 = tris[:, 1] - tris[:, 0]
    v2 = tris[:, 2] - tris[:, 0]
    normals = np.cross(v1, v2)
    n_lens = np.linalg.norm(normals, axis=1, keepdims=True)
    n_lens[n_lens == 0] = 1.0
    normals = normals / n_lens
    down_mask = normals[:, 2] < -0.5
    bot_pts = tris[down_mask].reshape(-1, 3)
    ax5.scatter(bot_pts[:, 0], bot_pts[:, 1], s=2, alpha=0.7, color='black')
    ax5.set_aspect("equal")
    ax5.set_xlabel("X mm")
    ax5.set_ylabel("Y mm")
    ax5.set_title("Bottom view — stud clearance holes only")
    ax5.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("output/riser_preview.png", dpi=150)
    plt.close()
    print("Saved output/riser_preview.png")


if __name__ == "__main__":
    main()
