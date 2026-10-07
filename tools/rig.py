import math
from dataclasses import dataclass, field

import numpy as np

MAX_INFLUENCES = 4


@dataclass
class Bone:
    name: str
    start: tuple
    end: tuple
    parent: "Bone | None" = None
    children: list = field(default_factory=list)

    @property
    def angle(self):
        return math.atan2(self.end[1] - self.start[1], self.end[0] - self.start[0])

    @property
    def length(self):
        return math.dist(self.start, self.end)

    def attaches_at_parent_tip(self):
        return self.parent is not None and math.dist(self.parent.end, self.start) < 1e-6


def right_side(rig, key):
    explicit = rig.get(key.replace("_left", "_right"))
    if explicit is not None:
        return explicit
    value = rig[key]
    if isinstance(value, list):
        return [(rig["mirror_x"] - x, y) for x, y in value]
    return (rig["mirror_x"] - value[0], value[1])


def skeleton(rig):
    root = Bone("Root", rig["hip"], rig["neck"])
    head = Bone("Head", rig["neck"], rig["crown"], root)
    upper_l = Bone("UpperArmL", rig["shoulder_left"], rig["elbow_left"], root)
    fore_l = Bone("ForearmL", rig["elbow_left"], rig["wrist_left"], upper_l)
    upper_r = Bone("UpperArmR", right_side(rig, "shoulder_left"), right_side(rig, "elbow_left"), root)
    fore_r = Bone("ForearmR", right_side(rig, "elbow_left"), right_side(rig, "wrist_left"), upper_r)
    root.children = [head, upper_l, upper_r]
    upper_l.children = [fore_l]
    upper_r.children = [fore_r]
    return [root, head, upper_l, fore_l, upper_r, fore_r]


def smoothstep(x, edge0, edge1):
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def boundary_x(y, polyline):
    ys = [p[1] for p in polyline]
    xs = [p[0] for p in polyline]
    return np.interp(y, ys, xs)


def arm_weight(points, side_polyline, outward_sign, rig):
    x, y = points[:, 0], points[:, 1]
    edge = boundary_x(y, side_polyline)
    softness = rig["side_softness"]
    side = smoothstep(outward_sign * (edge - x), -softness, softness)
    return side * smoothstep(y, *rig["shoulder_ramp"])


def forearm_fraction(points, upper, rig):
    axis = np.array(upper.end) - np.array(upper.start)
    t = (points - np.array(upper.start)) @ axis / (axis @ axis)
    return smoothstep(t, *rig["elbow_blend"])


def head_weight(points, rig):
    x, y = points[:, 0], points[:, 1]
    center, side_ramp = rig["head_ramp_center"], rig["head_ramp_side"]
    side = smoothstep(np.abs(x - rig["neck"][0]), *rig["head_side_x"])
    y0 = center[0] + side * (side_ramp[0] - center[0])
    y1 = center[1] + side * (side_ramp[1] - center[1])
    return 1 - smoothstep(y, y0, y1)


def bone_weights(points, bones, rig):
    by_name = {b.name: b for b in bones}
    head = head_weight(points, rig)
    arm_l = arm_weight(points, rig["side_boundary_left"], 1.0, rig)
    arm_r = arm_weight(points, right_side(rig, "side_boundary_left"), -1.0, rig)
    fore_l = forearm_fraction(points, by_name["UpperArmL"], rig)
    fore_r = forearm_fraction(points, by_name["UpperArmR"], rig)
    columns = {
        "Head": head,
        "UpperArmL": arm_l * (1 - fore_l),
        "ForearmL": arm_l * fore_l,
        "UpperArmR": arm_r * (1 - fore_r),
        "ForearmR": arm_r * fore_r,
    }
    weights = np.zeros((len(points), len(bones)))
    for index, bone in enumerate(bones):
        if bone.name in columns:
            weights[:, index] = columns[bone.name]
    total = weights.sum(axis=1)
    overflow = total > 1
    weights[overflow] /= total[overflow, None]
    weights[:, 0] = 1 - weights[:, 1:].sum(axis=1)
    return weights


def pack_weights(row):
    order = np.argsort(row)[::-1][:MAX_INFLUENCES]
    order = [i for i in order if row[i] > 1e-3]
    values = np.array([row[i] for i in order])
    values = values / values.sum()
    bytes_ = np.floor(values * 255).astype(int)
    bytes_[0] += 255 - bytes_.sum()
    indices = 0
    packed = 0
    for slot, (tendon, value) in enumerate(zip(order, bytes_)):
        indices |= (tendon + 1) << (8 * slot)
        packed |= int(value) << (8 * slot)
    return packed, indices
