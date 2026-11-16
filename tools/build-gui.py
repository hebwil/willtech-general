#!/usr/bin/env python3
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "opencode/plugins/willtech/visual"
ASSETS = ROOT / "docs/assets"


def bundle():
    images = {}
    for name in ("general", "explorador", "pesquisador", "visual", "executor", "testador", "revisor"):
        filename = "willtech-general-static.webp" if name == "general" else f"willtech-{name}.webp"
        images[f"willtech-{name}"] = "data:image/webp;base64," + base64.b64encode((ASSETS / filename).read_bytes()).decode()
    images["generalAnimated"] = "data:image/apng;base64," + base64.b64encode(
        (ASSETS / "willtech-general-animated.apng").read_bytes()).decode()
    logic = (PACKAGE / "activity.cjs").read_text(encoding="utf-8")
    source = (PACKAGE / "gui-source.cjs").read_text(encoding="utf-8")
    source = source.replace('require("./activity.cjs")',
                            '(() => { const module = { exports: {} };\n' + logic + '\nreturn module.exports; })()')
    source = source.replace('require("./assets.cjs")', json.dumps(images, separators=(",", ":")))
    return source.encode("utf-8")


if __name__ == "__main__":
    destination = PACKAGE / "gui-experimental.cjs"
    destination.write_bytes(bundle())
    print(f"{destination.relative_to(ROOT)}: {destination.stat().st_size} bytes; zero dependências de build")
