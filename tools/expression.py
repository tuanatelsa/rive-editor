import numpy as np


def displacement(points, expression):
    offset = np.zeros_like(points)
    for entry in expression:
        d2 = ((points - np.array(entry.center)) ** 2).sum(axis=1)
        falloff = np.exp(-d2 / (2 * entry.radius * entry.radius))
        offset += falloff[:, None] * np.array(entry.offset)
    return offset
