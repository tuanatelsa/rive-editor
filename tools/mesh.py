from dataclasses import dataclass

import numpy as np
from scipy.ndimage import binary_dilation
from scipy.spatial import Delaunay

ALPHA_THRESHOLD = 8
MASK_DILATION_PX = 3


@dataclass
class Mesh:
    points: np.ndarray
    triangles: np.ndarray
    contour_count: int
    width: int
    height: int


def grid_points(x0, y0, x1, y1, step):
    xs = np.unique(np.append(np.arange(x0, x1, step), x1))
    ys = np.unique(np.append(np.arange(y0, y1, step), y1))
    gx, gy = np.meshgrid(xs, ys)
    return np.column_stack([gx.ravel(), gy.ravel()]).astype(float)


def sample_points(width, height, settings):
    base = grid_points(0, 0, width, height, settings.base_step)
    inside_fine = np.zeros(len(base), dtype=bool)
    fine = []
    for fx0, fy0, fx1, fy1 in settings.fine_regions:
        inside_fine |= (base[:, 0] > fx0) & (base[:, 0] < fx1) & (base[:, 1] > fy0) & (base[:, 1] < fy1)
        fine.append(grid_points(fx0, fy0, fx1, fy1, settings.fine_step))
    return np.vstack([base[~inside_fine], *fine])


def triangle_covers_mask(tri, mask):
    x0, y0 = np.floor(tri.min(axis=0)).astype(int)
    x1, y1 = np.ceil(tri.max(axis=0)).astype(int)
    h, w = mask.shape
    x0, y0 = max(x0, 0), max(y0, 0)
    x1, y1 = min(x1, w - 1), min(y1, h - 1)
    window = mask[y0 : y1 + 1, x0 : x1 + 1]
    if not window.any():
        return False
    px, py = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    (ax, ay), (bx, by), (cx, cy) = tri
    d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(d) < 1e-9:
        return False
    l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / d
    l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / d
    l3 = 1 - l1 - l2
    eps = -0.05
    inside = (l1 >= eps) & (l2 >= eps) & (l3 >= eps)
    return bool((inside & window).any())


def contour_first(points, triangles):
    edges = {}
    for t in triangles:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            key = (min(a, b), max(a, b))
            edges[key] = edges.get(key, 0) + 1
    boundary = sorted({v for e, n in edges.items() if n == 1 for v in e})
    interior = [i for i in range(len(points)) if i not in set(boundary)]
    order = boundary + interior
    remap = np.empty(len(points), dtype=int)
    remap[order] = np.arange(len(order))
    return points[order], remap[triangles], len(boundary)


def build_mesh(alpha, settings):
    height, width = alpha.shape
    mask = binary_dilation(alpha > ALPHA_THRESHOLD, iterations=MASK_DILATION_PX)
    points = sample_points(width, height, settings)
    triangles = Delaunay(points).simplices
    kept = np.array([triangle_covers_mask(points[t], mask) for t in triangles])
    triangles = triangles[kept]
    used = np.unique(triangles)
    remap = np.full(len(points), -1)
    remap[used] = np.arange(len(used))
    points, triangles = points[used], remap[triangles]
    points, triangles, contour_count = contour_first(points, triangles)
    return Mesh(points, triangles, contour_count, width, height)
