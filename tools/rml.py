import base64


def fmt(value):
    return f"{value:.3f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)


def varuint(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def triangle_index_bytes(triangles):
    raw = b"".join(varuint(int(i)) for i in triangles.ravel())
    return base64.b64encode(raw).decode()


def attrs(**kwargs):
    return " ".join(f'{k}="{fmt(v)}"' for k, v in kwargs.items() if v is not None)


class Ids:
    def __init__(self, start=100):
        self.next_id = start

    def new(self):
        value = f"0:{self.next_id}"
        self.next_id += 1
        return value


def element(tag, children=None, **kwargs):
    head = f"<{tag} {attrs(**kwargs)}".rstrip()
    if not children:
        return [head + "/>"]
    lines = [head + ">"]
    for child in children:
        lines.extend("    " + line for line in child)
    lines.append(f"</{tag}>")
    return lines


def document(roots):
    lines = ['<Rive version="1" kind="fragment">']
    for root in roots:
        lines.extend("    " + line for line in root)
    lines.append("</Rive>")
    return "\n".join(lines) + "\n"
