import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image

from config import BONE_PROPERTIES, load_character
from confetti import build_pieces
from expression import displacement
from mesh import build_mesh
from rig import bone_weights, pack_weights, skeleton
from rml import Ids, document, element, triangle_index_bytes

KEYED_VERTEX_THRESHOLD = 0.05
VERTEX_X_KEY = 24
VERTEX_Y_KEY = 25
ENUM_PROPERTY_KEY = 637
CONFETTI_PROPERTIES = ("x", "y", "rotation", "scaleY", "opacity")
PIECE_TRACKS = ("x", "y", "rotation", "scale_y", "opacity")


class Scene:
    def __init__(self, character, mesh):
        self.character = character
        self.mesh = mesh
        self.pad_x = character.canvas.pad_x
        self.pad_top = character.canvas.pad_top
        self.bones = skeleton(character.rig)
        self.ids = Ids()

    def to_world(self, point):
        return (point[0] + self.pad_x, point[1] + self.pad_top)

    def bone_rest(self, bone):
        if bone.parent is None:
            x, y = self.to_world(bone.start)
            return {"x": x, "y": y, "rotation": bone.angle}
        rotation = bone.angle - bone.parent.angle
        if bone.attaches_at_parent_tip():
            return {"rotation": rotation}
        dx = bone.start[0] - bone.parent.start[0]
        dy = bone.start[1] - bone.parent.start[1]
        cos_p, sin_p = math.cos(bone.parent.angle), math.sin(bone.parent.angle)
        return {"x": cos_p * dx + sin_p * dy, "y": -sin_p * dx + cos_p * dy, "rotation": rotation}

    def bone_element(self, bone):
        rest = self.bone_rest(bone)
        tag = "Bone" if bone.attaches_at_parent_tip() else "RootBone"
        children = [self.bone_element(child) for child in bone.children]
        return element(tag, children, length=bone.length, name=bone.name, id=self.bone_ids[bone.name], **rest)

    def tendon_element(self, bone):
        tx, ty = self.to_world(bone.start)
        cos_a, sin_a = math.cos(bone.angle), math.sin(bone.angle)
        return element(
            "Tendon",
            boneId=self.bone_ids[bone.name],
            xx=cos_a,
            xy=sin_a,
            yx=-sin_a,
            yy=cos_a,
            tx=float(tx),
            ty=float(ty),
            name=bone.name,
        )

    def mesh_element(self, weights):
        mesh = self.mesh
        vertices = []
        for index, (x, y) in enumerate(mesh.points):
            tag = "ContourMeshVertex" if index < mesh.contour_count else "MeshVertex"
            values, indices = pack_weights(weights[index])
            vertices.append(
                element(
                    tag,
                    [element("Weight", values=values, indices=indices)],
                    x=float(x),
                    y=float(y),
                    u=float(x / mesh.width),
                    v=float(y / mesh.height),
                    id=self.vertex_ids.get(index),
                )
            )
        skin = element(
            "Skin",
            [self.tendon_element(bone) for bone in self.bones],
            tx=float(self.pad_x),
            ty=float(self.pad_top),
            name="Skin",
        )
        return element(
            "Mesh",
            vertices + [skin],
            triangleIndexBytes=triangle_index_bytes(mesh.triangles),
            name="Mesh",
            id=self.ids.new(),
        )

    def mood_element(self, mood):
        by_name = {b.name: b for b in self.bones}
        objects = []
        for bone_name in self.bone_ids:
            rest = self.bone_rest(by_name[bone_name])
            tracks = []
            for prop in BONE_PROPERTIES:
                offsets = mood.bone_offsets.get((bone_name, prop))
                if offsets:
                    if prop not in rest:
                        raise ValueError(f"mood {mood.name}: {bone_name}.{prop} cannot be keyed")
                    tracks.append(("property", prop, [(f, rest[prop] + v) for f, v in offsets]))
            if tracks:
                objects.append(keyed(self.bone_ids[bone_name], tracks))
        offset = displacement(self.mesh.points[self.keyed_vertices], mood.expression)
        for row, index in enumerate(self.keyed_vertices):
            x, y = self.mesh.points[index] + offset[row]
            objects.append(
                keyed(
                    self.vertex_ids[index],
                    [("propertyKey", VERTEX_X_KEY, [(0, x)]), ("propertyKey", VERTEX_Y_KEY, [(0, y)])],
                    held_keyframe,
                )
            )
        return element(
            "LinearAnimation",
            objects,
            loopValue="loop",
            duration=mood.duration,
            name=mood.name,
            id=self.mood_ids[mood.name],
        )

    def mood_condition(self, mood_name):
        bind = element("DataBindContext", sourcePathIds=self.mood_path, propertyKey=ENUM_PROPERTY_KEY)
        return element(
            "TransitionViewModelCondition",
            [
                element("TransitionPropertyViewModelComparator", [element("BindablePropertyEnum", [bind])]),
                element("TransitionValueEnumComparator", value=self.enum_value_ids[mood_name]),
            ],
            opValue="equal",
        )

    def state_machine(self):
        settings = self.character.state_machine
        moods = self.character.moods
        states = []
        for column, mood in enumerate(moods):
            transitions = [
                element(
                    "StateTransition",
                    [self.mood_condition(other.name)],
                    stateToId=self.state_ids[other.name],
                    duration=settings.transition_ms,
                )
                for other in moods
                if other.name != mood.name
            ]
            states.append(
                element(
                    "AnimationState",
                    transitions,
                    x=160 + 220 * column,
                    y=120,
                    animationId=self.mood_ids[mood.name],
                    id=self.state_ids[mood.name],
                )
            )
        entry = element("StateTransition", stateToId=self.state_ids[settings.default])
        layer = element(
            "StateMachineLayer",
            [
                element("AnyState", x=160, y=-120),
                element("ExitState", x=600, y=-120),
                element("EntryState", [entry], x=380, y=-120),
                *states,
            ],
            name="Mood",
            id=self.ids.new(),
        )
        layers = [layer, self.confetti_layer()] if self.character.confetti else [layer]
        return element("StateMachine", layers, name="Mood Machine", id=self.machine_id)

    def confetti_layer(self):
        settings = self.character.confetti
        other_moods = [m.name for m in self.character.moods if m.name not in settings.moods]
        hidden = element(
            "AnimationState",
            [
                element("StateTransition", [self.mood_condition(name)], stateToId=self.confetti_state_ids["burst"])
                for name in settings.moods
            ],
            x=160,
            y=120,
            animationId=self.confetti_anim_ids["hidden"],
            id=self.confetti_state_ids["hidden"],
        )
        burst = element(
            "AnimationState",
            [
                element(
                    "StateTransition",
                    [self.mood_condition(name)],
                    stateToId=self.confetti_state_ids["hidden"],
                    duration=self.character.state_machine.transition_ms,
                )
                for name in other_moods
            ],
            x=380,
            y=120,
            reset="true",
            animationId=self.confetti_anim_ids["burst"],
            id=self.confetti_state_ids["burst"],
        )
        entry = element("StateTransition", stateToId=self.confetti_state_ids["hidden"])
        return element(
            "StateMachineLayer",
            [
                element("AnyState", x=160, y=-120),
                element("ExitState", x=600, y=-120),
                element("EntryState", [entry], x=380, y=-120),
                hidden,
                burst,
            ],
            name="Confetti",
            id=self.ids.new(),
        )

    def confetti_group(self, name, node_id, pieces):
        shapes = []
        for piece, shape_id in pieces:
            fill = element("Fill", [element("SolidColor", colorValue=piece.color, name="Color")], name="Fill")
            geometry = element(piece.shape, width=piece.width, height=piece.height, name="Path")
            shapes.append(
                element(
                    "Shape",
                    [geometry, fill],
                    x=float(piece.x[0][1]),
                    y=float(piece.y[0][1]),
                    rotation=float(piece.rotation[0][1]),
                    scaleY=float(piece.scale_y[0][1]),
                    opacity=float(piece.opacity[0][1]),
                    name="Piece",
                    id=shape_id,
                )
            )
        return element("Node", shapes, opacity=0.0, name=name, id=node_id)

    def confetti_animations(self, pieces):
        groups = [self.confetti_node_ids["front"], self.confetti_node_ids["back"]]
        hidden = element(
            "LinearAnimation",
            [keyed(node, [("property", "opacity", [(0, 0.0)])], held_keyframe) for node in groups],
            duration=1,
            name="confetti_hidden",
            id=self.confetti_anim_ids["hidden"],
        )
        objects = [keyed(node, [("property", "opacity", [(0, 1.0)])], held_keyframe) for node in groups]
        for piece, shape_id in pieces:
            tracks = [("property", prop, getattr(piece, attr)) for prop, attr in zip(CONFETTI_PROPERTIES, PIECE_TRACKS)]
            objects.append(keyed(shape_id, tracks, held_keyframe))
        burst = element(
            "LinearAnimation",
            objects,
            loopValue="loop",
            duration=self.character.confetti.duration,
            name="confetti_burst",
            id=self.confetti_anim_ids["burst"],
        )
        return [hidden, burst]

    def find_keyed_vertices(self):
        points = self.mesh.points
        magnitude = np.zeros(len(points))
        for mood in self.character.moods:
            magnitude = np.maximum(magnitude, np.linalg.norm(displacement(points, mood.expression), axis=1))
        return [int(i) for i in np.nonzero(magnitude > KEYED_VERTEX_THRESHOLD)[0]]

    def build(self):
        character, mesh, ids = self.character, self.mesh, self.ids
        moods = character.moods
        bone_names = {b.name for b in self.bones}
        for mood in moods:
            for bone_name, _ in mood.bone_offsets:
                if bone_name not in bone_names:
                    raise ValueError(f"mood {mood.name}: unknown bone {bone_name!r}; use one of {sorted(bone_names)}")

        artboard_id, style_id, self.machine_id = ids.new(), ids.new(), ids.new()
        image_asset_id, image_id = ids.new(), ids.new()
        enum_id, view_model_id, property_id, instance_id = ids.new(), ids.new(), ids.new(), ids.new()
        self.enum_value_ids = {mood.name: ids.new() for mood in moods}
        self.mood_ids = {mood.name: ids.new() for mood in moods}
        self.state_ids = {mood.name: ids.new() for mood in moods}
        self.bone_ids = {bone.name: ids.new() for bone in self.bones}
        self.keyed_vertices = self.find_keyed_vertices()
        self.vertex_ids = {index: ids.new() for index in self.keyed_vertices}
        self.mood_path = f"{view_model_id}-{property_id}"
        weights = bone_weights(mesh.points, self.bones, character.rig)
        confetti_front, confetti_back, confetti_animations = [], [], []
        if character.confetti:
            self.confetti_node_ids = {"front": ids.new(), "back": ids.new()}
            self.confetti_anim_ids = {"hidden": ids.new(), "burst": ids.new()}
            self.confetti_state_ids = {"hidden": ids.new(), "burst": ids.new()}
            pieces = [(piece, ids.new()) for piece in build_pieces(character.confetti, self.to_world)]
            front = [(p, i) for p, i in pieces if not p.behind]
            back = [(p, i) for p, i in pieces if p.behind]
            confetti_front = [self.confetti_group("Confetti Front", self.confetti_node_ids["front"], front)]
            confetti_back = [self.confetti_group("Confetti Back", self.confetti_node_ids["back"], back)]
            confetti_animations = self.confetti_animations(pieces)

        image = element(
            "Image",
            [self.mesh_element(weights)],
            x=float(self.pad_x),
            y=float(self.pad_top),
            originX=0.0,
            originY=0.0,
            assetId=image_asset_id,
            name="Character",
            id=image_id,
        )
        background = element("SolidColor", colorValue=character.canvas.background, name="Color")
        artboard = element(
            "Artboard",
            [
                element("LayoutComponentStyle", name="Artboard Style", id=style_id),
                element("Fill", [background], name="Background"),
                *confetti_front,
                image,
                *confetti_back,
                self.bone_element(self.bones[0]),
                self.state_machine(),
                *[self.mood_element(mood) for mood in moods],
                *confetti_animations,
            ],
            defaultStateMachineId=self.machine_id,
            viewModelId=view_model_id,
            viewModelInstanceId=instance_id,
            styleId=style_id,
            width=mesh.width + 2 * self.pad_x,
            height=mesh.height + self.pad_top + character.canvas.pad_bottom,
            name=character.name.capitalize(),
            id=artboard_id,
        )
        mood_enum = element(
            "DataEnumCustom",
            [
                element("DataEnumValue", key=mood.name, value=mood.name.capitalize(), id=self.enum_value_ids[mood.name])
                for mood in moods
            ],
            name="Mood",
            id=enum_id,
        )
        default_value = element(
            "ViewModelInstanceEnum",
            propertyValue=self.enum_value_ids[character.state_machine.default],
            viewModelPropertyId=property_id,
        )
        view_model = element(
            "ViewModel",
            [
                element(
                    "ViewModelPropertyEnumCustom",
                    enumId=enum_id,
                    name=character.state_machine.property,
                    id=property_id,
                ),
                element("ViewModelInstance", [default_value], exports="true", name="Default", id=instance_id),
            ],
            defaultInstanceId=instance_id,
            name="Character",
            id=view_model_id,
        )
        asset = element("ImageAsset", file=character.image.name, name=character.image.stem, id=image_asset_id)
        return document([artboard, mood_enum, view_model, asset])


def eased_keyframe(frame, value):
    curve = element("CubicEaseInterpolator", x1=0.42, y1=0.0, x2=0.58, y2=1.0)
    return element("KeyFrameDouble", [curve], frame=frame, value=float(value), interpolationType="cubic")


def held_keyframe(frame, value):
    return element("KeyFrameDouble", frame=frame, value=float(value), interpolationType="linear")


def keyed(object_id, tracks, make_keyframe=eased_keyframe):
    properties = [
        element("KeyedProperty", [make_keyframe(f, v) for f, v in keys], **{key_attr: key})
        for key_attr, key, keys in tracks
    ]
    return element("KeyedObject", properties, objectId=object_id)


def load_alpha(image_path):
    image = Image.open(image_path)
    if image.mode != "RGBA":
        raise ValueError(f"{image_path} has mode {image.mode}; it needs a transparent background (RGBA)")
    return np.array(image)[..., 3]


def write_rive_yaml(character):
    path = character.directory / "rive.yaml"
    if not path.exists():
        path.write_text(f"name: {character.name}\n")


def main():
    parser = argparse.ArgumentParser(description="Generate scene.rml for a character directory.")
    parser.add_argument("character_dir")
    args = parser.parse_args()
    character = load_character(args.character_dir)
    mesh = build_mesh(load_alpha(character.image), character.mesh)
    scene = Scene(character, mesh)
    (character.directory / "scene.rml").write_text(scene.build())
    write_rive_yaml(character)
    print(
        f"vertices={len(mesh.points)} triangles={len(mesh.triangles)} "
        f"keyed_vertices={len(scene.keyed_vertices)} moods={[m.name for m in character.moods]}"
    )


if __name__ == "__main__":
    main()
