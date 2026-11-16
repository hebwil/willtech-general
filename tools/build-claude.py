#!/usr/bin/env python3
"""Gera os assets PNG/quadros e o nucleo ESM do Mod Claude Code.

Nucleo de interpretacao de estados: copia unica e verificavel do activity.cjs
canonico do painel OpenCode (sem drift). Imagens: WebP oficiais -> PNG (sips)
+ quadros de respiracao compostos em Python puro (sem IA, sem dependencias).
"""
import base64
import json
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "claude/plugins/willtech-visual"
ASSETS = ROOT / "docs/assets"
CANON = ROOT / "opencode/plugins/willtech/visual/activity.cjs"
NAMES = ["general", "explorador", "pesquisador", "visual", "executor", "testador", "revisor"]
MAXPX = 120
OFFSETS = [4, 2, 0, 2]


def png_read(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not png"
    pos = 8
    idat = b""
    w = h = bitdepth = colortype = None
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            w, h, bitdepth, colortype, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
            assert bitdepth == 8 and interlace == 0, "unsupported png"
        elif kind == b"IDAT":
            idat += chunk
        pos += 12 + length
    raw = zlib.decompress(idat)
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[colortype]
    stride = w * channels
    out = bytearray(w * h * 4)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        for x in range(stride):
            a = line[x - channels] if x >= channels else 0
            b = prev[x]
            c = prev[x - channels] if x >= channels else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        for x in range(w):
            o = (y * w + x) * 4
            if colortype == 6:
                out[o:o + 4] = line[x * 4:x * 4 + 4]
            elif colortype == 2:
                out[o:o + 3] = line[x * 3:x * 3 + 3]
                out[o + 3] = 255
            elif colortype == 4:
                out[o:o + 2] = line[x * 2:x * 2 + 2]
                out[o + 2:o + 4] = line[x * 2:x * 2 + 2]
            else:
                v = line[x]
                out[o:o + 4] = bytes([v, v, v, 255])
        prev = line
    return w, h, bytes(out)


def png_write(w, h, rgba):
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
    raw = b"".join(b"\x00" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def breathe(rgba, w, h, dy):
    canvas_h = h + 8
    out = bytearray(w * canvas_h * 4)
    for y in range(h):
        src = y * w * 4
        dst = (y + dy) * w * 4
        out[dst:dst + w * 4] = rgba[src:src + w * 4]
    return png_write(w, canvas_h, bytes(out))


def make_icon():
    tmp = MOD / ".tmp-icon.png"
    subprocess.run(["sips", "-s", "format", "png", "--resampleHeightWidthMax", "480",
                    str(ASSETS / "willtech-general-static.webp"), "--out", str(tmp)],
                   check=True, capture_output=True)
    w, h, rgba = png_read(tmp)
    tmp.unlink()
    side = 512
    out = bytearray(side * side * 4)
    ox, oy = (side - w) // 2, (side - h) // 2
    for y in range(h):
        src = y * w * 4
        dst = ((y + oy) * side + ox) * 4
        out[dst:dst + w * 4] = rgba[src:src + w * 4]
    dest = MOD / ".claude-plugin/icon.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(png_write(side, side, bytes(out)))


def main():
    hooks = MOD / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    png_b64, frames_b64, size = {}, {}, None
    for name in NAMES:
        src = ASSETS / ("willtech-general-static.webp" if name == "general" else f"willtech-{name}.webp")
        tmp = MOD / f".tmp-{name}.png"
        subprocess.run(["sips", "-s", "format", "png", "--resampleHeightWidthMax", str(MAXPX),
                        str(src), "--out", str(tmp)], check=True, capture_output=True)
        w, h, rgba = png_read(tmp)
        tmp.unlink()
        size = {"w": w, "h": h + 8}
        png_b64[f"willtech-{name}"] = base64.b64encode(breathe(rgba, w, h, 4)).decode()
        frames_b64[f"willtech-{name}"] = [base64.b64encode(breathe(rgba, w, h, dy)).decode() for dy in OFFSETS]
    assets = ("// Gerado por tools/build-claude.py a partir dos WebP oficiais; nao editar a mao.\n"
              + f"export const SIZE = {json.dumps(size)};\n"
              + f"export const PNG = {json.dumps(png_b64, separators=(',', ':'))};\n"
              + f"export const FRAMES = {json.dumps(frames_b64, separators=(',', ':'))};\n")
    (hooks / "assets.js").write_text(assets, encoding="utf-8")
    core = CANON.read_text(encoding="utf-8")
    marker = "module.exports = { AGENTS, EVENTS, projectAgents };"
    assert core.rstrip().endswith(marker), "canonical core export changed"
    body = core.rstrip()[: -len(marker)]
    esm = ("// Copia verificavel do nucleo canonico (opencode/.../activity.cjs); sem drift.\n"
           + body + "export { AGENTS, EVENTS, projectAgents };\n")
    (hooks / "activity.js").write_text(esm, encoding="utf-8")
    make_icon()
    for key, value in png_b64.items():
        svg_len = len(value) + 400
        assert svg_len < 131072, f"Svg de {key} excede limite: {svg_len}"
    print(f"assets.js {len(assets)} bytes; activity.js {len(esm)} bytes; SIZE={size}; "
          f"maior PNG base64={max(len(v) for v in png_b64.values())}")


if __name__ == "__main__":
    sys.exit(main())