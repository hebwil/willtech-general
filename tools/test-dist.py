#!/usr/bin/env python3
"""Verifica os artefatos de distribuição: (1) os bytes do archive correspondem
exatamente ao código publicado (SHA-256 por arquivo + conjunto de arquivos ==
git ls-files do commit); (2) instalação limpa, atualização idempotente,
desativação, reativação e desinstalação funcionam a partir dos arquivos
DISTRIBUÍDOS (extraídos do archive, não do repo de trabalho), preservando
arquivos de terceiros. Labs git descartáveis; zero modelo/rede."""
import hashlib
import importlib.util
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_dist", ROOT / "tools/build-dist.py")
build_dist = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_dist)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extract(tarpath, dest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarpath, "r:gz") as tf:
        tf.extractall(dest, filter="data")
    return dest / build_dist.PREFIX


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dist-tests-", ignore_cleanup_errors=True)
        self.base = Path(self.temp.name)
        self.dist = self.base / "dist"
        self.manifest = build_dist.build("HEAD", self.dist)
        self.tarpath = self.dist / self.manifest["archive"]

    def tearDown(self):
        self.temp.cleanup()

    def test_distribution_version_is_consistent(self):
        """A versao no VERSION deve estar presente no archive e no manifesto."""
        source_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(source_version, build_dist.VERSION)
        self.assertEqual(self.manifest["version"], source_version)
        self.assertEqual(self.manifest["archive"], f"willtech-general-{source_version}.tar.gz")
        extracted = extract(self.tarpath, self.base / "version")
        self.assertEqual((extracted / "VERSION").read_text(encoding="utf-8").strip(), source_version)

    def test_archive_matches_published_code(self):
        sums = {}
        for line in (self.dist / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
            digest, rel = line.split("  ", 1)
            sums[rel] = digest
        src = extract(self.tarpath, self.base / "src")
        self.assertEqual(set(sums), {p.relative_to(src).as_posix() for p in src.rglob("*") if p.is_file()})
        tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
        self.assertEqual(set(sums), set(tracked))
        for rel, digest in sums.items():
            self.assertEqual(sha256(src / rel), digest, rel)
        self.assertEqual(sha256(self.tarpath), self.manifest["archive_sha256"])
        self.assertEqual(self.manifest["commit"],
                         subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip())
        self.assertEqual(self.manifest["files"], len(sums))

    def test_install_update_disable_uninstall_from_distribution(self):
        lab = extract(self.tarpath, self.base / "lab")
        subprocess.check_call(["git", "init", "-q"], cwd=lab)
        third = lab / ".opencode/plugins/thirdparty.js"
        third.parent.mkdir(parents=True, exist_ok=True)
        third.write_text("// terceiro\n", encoding="utf-8")
        install = ["sh", str(lab / "tools/willtech-install.sh"), "--repo", str(lab)]

        def run(*flags):
            return subprocess.run(install + list(flags), capture_output=True, text=True, cwd=lab, timeout=60)

        def probe(session):
            event = {"hook_event_name": "SessionStart", "session_id": session, "cwd": str(lab)}
            return subprocess.run(["python3", str(lab / "tools/willtech-auto.py"), "opencode"],
                                  input=json.dumps(event), capture_output=True, text=True, cwd=lab, timeout=30)

        r = run("--platform", "opencode", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((lab / ".willtech/enabled").is_file())
        self.assertTrue((lab / ".opencode/plugins/willtech/index.js").is_file())
        self.assertEqual(probe("plugin-load").returncode, 0)
        self.assertTrue((lab / ".willtech/state-plugin-load.json").is_file())

        r = run("--platform", "opencode", "--yes")  # atualização idempotente
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((lab / ".opencode/plugins/willtech/index.js").is_file())

        r = run("--disable")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((lab / ".willtech/enabled").exists())
        probe("disabled")
        self.assertFalse((lab / ".willtech/state-disabled.json").exists())  # núcleo no-op

        r = run("--enable")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((lab / ".willtech/enabled").is_file())

        r = run("--uninstall", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((lab / ".opencode/plugins/willtech/index.js").exists())
        self.assertFalse((lab / ".willtech/installed.json").exists())
        self.assertTrue(third.is_file())  # terceiro preservado
        self.assertEqual(third.read_text(encoding="utf-8"), "// terceiro\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)