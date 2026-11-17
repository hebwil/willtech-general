#!/usr/bin/env python3
"""Gera os artefatos definitivos de distribuição WillTech-General a partir de um
commit publicado: archive tar.gz canônico (git archive), SHA256SUMS por arquivo e
MANIFEST.json. Os hashes são calculados sobre os bytes do PRÓPRIO archive (o
código publicado), não sobre arquivos locais soltos — garantindo que os artefatos
correspondem exatamente ao commit. Zero dependências externas (stdlib + git)."""
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "3.0.0"
PREFIX = f"willtech-general-{VERSION}"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def build(ref="HEAD", outdir=None):
    outdir = Path(outdir) if outdir else ROOT / "dist"
    outdir.mkdir(parents=True, exist_ok=True)
    commit = git("rev-parse", ref)
    tarpath = outdir / f"{PREFIX}.tar.gz"
    subprocess.check_call(
        ["git", "archive", "--format=tar.gz", f"--prefix={PREFIX}/", "-o", str(tarpath), ref],
        cwd=ROOT)
    sums, sizes = {}, {}
    with tarfile.open(tarpath, "r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            rel = member.name[len(PREFIX) + 1:]
            data = tf.extractfile(member).read()
            sums[rel] = hashlib.sha256(data).hexdigest()
            sizes[rel] = len(data)
    (outdir / "SHA256SUMS.txt").write_text(
        "".join(f"{sums[p]}  {p}\n" for p in sorted(sums)), encoding="utf-8")
    manifest = {
        "name": "willtech-general",
        "version": VERSION,
        "commit": commit,
        "ref": ref,
        "files": len(sums),
        "total_bytes": sum(sizes.values()),
        "archive": tarpath.name,
        "archive_sha256": hashlib.sha256(tarpath.read_bytes()).hexdigest(),
    }
    (outdir / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    import sys
    ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    info = build(ref)
    print(f"{PREFIX}.tar.gz: {info['files']} arquivos, {info['total_bytes']} bytes")
    print(f"commit {info['commit']}")
    print(f"archive sha256 {info['archive_sha256']}")