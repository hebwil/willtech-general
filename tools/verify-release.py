#!/usr/bin/env python3
"""Verifica uma release publicada WillTech-General em ambiente limpo: baixa os
artefatos (feitos pelo build-dist), confere que correspondem EXATAMENTE ao código
publicado no commit da tag (SHA-256 por arquivo + conjunto == git ls-files da tag)
e exercita instalação limpa → sonda do núcleo → desinstalação a partir dos
arquivos DISTRIBUÍDOS. Uso: verify-release.py <dir-artefatos> <tag>. Sai != 0 em
qualquer divergência. Zero modelo/rede além do download dos artefatos."""
import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFIX = "willtech-general-3.0.0"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    artifacts, tag = Path(sys.argv[1]), sys.argv[2]
    manifest = json.loads((artifacts / "MANIFEST.json").read_text(encoding="utf-8"))
    tarpath = artifacts / manifest["archive"]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert manifest["commit"] == commit, f"commit da tag {commit} != manifesto {manifest['commit']}"
    assert sha256(tarpath) == manifest["archive_sha256"], "sha256 do archive diverge do manifesto"
    print(f"archive ok: {manifest['archive']} sha256={manifest['archive_sha256']}")

    sums = {}
    for line in (artifacts / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        digest, rel = line.split("  ", 1)
        sums[rel] = digest
    with tempfile.TemporaryDirectory(prefix="release-verify-", ignore_cleanup_errors=True) as tmp:
        src = Path(tmp) / "src"
        src.mkdir()
        with tarfile.open(tarpath, "r:gz") as tf:
            tf.extractall(src, filter="data")
        src = src / PREFIX
        extracted = {p.relative_to(src).as_posix() for p in src.rglob("*") if p.is_file()}
        assert extracted == set(sums), "conjunto de arquivos extraídos != SHA256SUMS"
        tracked = set(subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines())
        assert set(sums) == tracked, "SHA256SUMS != git ls-files da tag"
        for rel, digest in sums.items():
            assert sha256(src / rel) == digest, f"hash diverge: {rel}"
        print(f"hashes ok: {len(sums)} arquivos idênticos ao código publicado ({commit[:12]})")

        lab = Path(tmp) / "lab"
        lab.mkdir()
        with tarfile.open(tarpath, "r:gz") as tf:
            tf.extractall(lab, filter="data")
        lab = lab / PREFIX
        subprocess.check_call(["git", "init", "-q"], cwd=lab)
        install = ["sh", str(lab / "tools/willtech-install.sh"), "--repo", str(lab)]
        r = subprocess.run(install + ["--platform", "opencode", "--yes"],
                           capture_output=True, text=True, cwd=lab, timeout=60)
        assert r.returncode == 0, f"instalação limpa falhou: {r.stderr}"
        assert (lab / ".willtech/enabled").is_file()
        assert (lab / ".opencode/plugins/willtech/index.js").is_file()
        event = {"hook_event_name": "SessionStart", "session_id": "plugin-load", "cwd": str(lab)}
        p = subprocess.run(["python3", str(lab / "tools/willtech-auto.py"), "opencode"],
                           input=json.dumps(event), capture_output=True, text=True, cwd=lab, timeout=30)
        assert p.returncode == 0 and (lab / ".willtech/state-plugin-load.json").is_file(), "núcleo não executou"
        r = subprocess.run(install + ["--uninstall", "--yes"],
                           capture_output=True, text=True, cwd=lab, timeout=60)
        assert r.returncode == 0, f"uninstall falhou: {r.stderr}"
        assert not (lab / ".opencode/plugins/willtech/index.js").exists()
        print("instalação limpa a partir da release: PASS (install → núcleo → uninstall)")
    print(f"RELEASE {tag} VERIFICADA: artefatos == código publicado; instalação limpa OK")


if __name__ == "__main__":
    main()