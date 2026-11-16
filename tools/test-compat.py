#!/usr/bin/env python3
"""Bateria de compatibilidade WILLTECH (macOS/Linux/Windows) — custo zero.

Exercita os pontos tocados pela compatibilidade Windows sem gastar modelo:
importação do núcleo, locks reais com PROCESSOS concorrentes (8×25), prune
concorrente sem perda de appends, recuperação anti-loop pós-learn, dossiê
antigo legível, caminhos de credencial com separadores Windows, eventos de
hooks simulados nas 3 plataformas e falha fechado com dossiê corrompido.
No Windows valida ainda o sidecar .lock; no POSIX confirma que o caminho
histórico (flock no próprio dossiê) segue em uso.

Uso: python3 tools/test-compat.py   (exit 0 = tudo passou)
"""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name} {detail}")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(args, inp=None, cwd=None):
    return subprocess.run(args, input=inp, capture_output=True, text=True,
                          cwd=cwd, timeout=60)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main():
    lab = tempfile.mkdtemp(prefix="willtech-compat-")
    try:
        # 1. importação/inicialização do núcleo
        d = load("dossie", os.path.join(HERE, "willtech-dossie.py"))
        a = load("auto", os.path.join(HERE, "willtech-auto.py"))
        check("import-nucleo", hasattr(d, "append") and hasattr(a, "main"))
        check("python-executavel", bool(PY))

        # 2. caminhos de credencial (separadores Windows e Unix)
        check("cred-backslash", d.is_credential_path("C:\\Users\\x\\.ssh\\id_rsa"))
        check("cred-env-windows", d.is_credential_path("C:\\repo\\.env"))
        check("cred-env-unix", d.is_credential_path("repo/.env"))
        check("cred-ok", not d.is_credential_path("C:\\repo\\src\\main.py"))

        dos = os.path.join(lab, "dossie.jsonl")

        # 3. locks reais: 8 PROCESSOS × 25 appends + prune concorrente
        worker = (
            "import importlib.util as u,sys\n"
            "s=u.spec_from_file_location('d',sys.argv[1]);m=u.module_from_spec(s);s.loader.exec_module(m)\n"
            "for i in range(25): m.append(sys.argv[2],{'kind':'finding','agent':'w'+sys.argv[3],'summary':'s'+str(i)})\n"
        )
        stop = threading.Event()

        def prune_loop():
            while not stop.is_set():
                d.prune_entries(dos)

        t = threading.Thread(target=prune_loop)
        t.start()
        procs = [subprocess.Popen([PY, "-c", worker,
                                   os.path.join(HERE, "willtech-dossie.py"),
                                   dos, str(k)]) for k in range(8)]
        codes = [p.wait() for p in procs]
        stop.set()
        t.join()
        entries = d.read_entries(dos) or []
        raw = [l for l in open(dos, encoding="utf-8") if l.strip()]
        bad = sum(1 for l in raw if not _is_json(l))
        check("conc-8x25-exit", all(c == 0 for c in codes), str(codes))
        check("conc-8x25-delta", len(entries) == 200, f"esperado 200, obtido {len(entries)}")
        check("conc-sem-corrupcao", bad == 0, f"{bad} linhas inválidas")
        if os.name == "nt":
            check("win-sidecar-lock", os.path.isfile(dos + ".lock"))
        else:
            check("posix-sem-sidecar", not os.path.exists(dos + ".lock"))

        # 4. recuperação anti-loop pós-learn (guard-attempt → learn → guarda livre)
        g = lambda: run([PY, os.path.join(HERE, "willtech-dossie.py"),
                         "guard-attempt", dos, "--key", "KREC"])
        check("guard-1", g().returncode == 0)
        check("guard-2", g().returncode == 0)
        check("guard-stop-3", g().returncode == 3)
        ev = os.path.join(lab, "evidencia.txt")
        open(ev, "w").write("ok\n")
        lr = run([PY, os.path.join(HERE, "willtech-dossie.py"), "learn", dos,
                  "--key", "KREC", "--resolution", "resolvido",
                  "--command", "pytest -q", "--output-file", ev, "--repo", lab])
        check("learn-registra", lr.returncode == 0, lr.stdout + lr.stderr)
        check("guard-liberado-pos-learn", g().returncode == 0)

        # 5. dossiê antigo (formato pré-2.2) continua legível e verificável
        legacy = os.path.join(lab, "legacy.jsonl")
        alvo = os.path.join(lab, "alvo.txt")
        open(alvo, "w").write("conteudo\n")
        with open(legacy, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": "2026-01-01T00:00:00Z", "agent": "general",
                                 "kind": "finding", "summary": "antigo",
                                 "path": alvo, "sha256": sha(alvo)}) + "\n")
        vr = run([PY, os.path.join(HERE, "willtech-dossie.py"), "verify", legacy])
        check("dossie-antigo-legivel", vr.returncode == 0, vr.stdout)
        br = run([PY, os.path.join(HERE, "willtech-dossie.py"), "brief", legacy,
                  "--repo", lab])
        check("brief-antigo", br.returncode == 0 and "QUARENTENA" in br.stdout)

        # 6. eventos de hooks simulados nas 3 plataformas (núcleo real)
        hlab = os.path.join(lab, "hooks")
        os.makedirs(os.path.join(hlab, "tools"))
        os.makedirs(os.path.join(hlab, "claude-code", "bin"))
        for f in ("willtech-dossie.py", "willtech-auto.py", "willtech-drift.py"):
            shutil.copy(os.path.join(HERE, f), os.path.join(hlab, "tools", f))
        shutil.copy(os.path.join(ROOT, "claude-code", "bin", "willtech_trace.py"),
                    os.path.join(hlab, "claude-code", "bin", "willtech_trace.py"))
        os.makedirs(os.path.join(hlab, ".willtech"))
        open(os.path.join(hlab, ".willtech", "enabled"), "w").close()
        auto = os.path.join(hlab, "tools", "willtech-auto.py")
        cmd = "pytest -q"

        def hook(platform, ev):
            r = run([PY, auto, platform], inp=json.dumps(ev), cwd=hlab)
            try:
                return r.returncode, json.loads(r.stdout) if r.stdout.strip() else {}
            except ValueError:
                return r.returncode, {}

        base = {"cwd": hlab, "tool_name": "Bash", "tool_input": {"command": cmd}}
        for platform, fail_ev in (
            ("claude", {"hook_event_name": "PostToolUseFailure"}),
            ("codex", {"hook_event_name": "PostToolUse", "tool_response": {"exit_code": 1}}),
            ("opencode", {"hook_event_name": "PostToolUseFailure"}),
        ):
            sid = "compat-" + platform
            for _ in range(2):
                hook(platform, dict(fail_ev, session_id=sid, **base))
            code, out = hook(platform, {"hook_event_name": "PreToolUse",
                                        "session_id": sid, **base})
            if platform == "opencode":
                denied = out.get("block") is True
            else:
                denied = (out.get("hookSpecificOutput", {})
                          .get("permissionDecision") == "deny")
            check(f"hook-{platform}-deny-3a", code == 0 and denied, json.dumps(out))

        # Stop → revisão goldfish (claude, 3 arquivos editados)
        sid = "compat-stop"
        for i in range(3):
            hook("claude", {"hook_event_name": "PostToolUse", "session_id": sid,
                            "cwd": hlab, "tool_name": "Edit",
                            "tool_input": {"file_path": f"f{i}.py"}})
        code, out = hook("claude", {"hook_event_name": "Stop", "session_id": sid,
                                    "cwd": hlab})
        check("hook-claude-stop-review", code == 0 and out.get("decision") == "block",
              json.dumps(out))

        # 7. falha fechado: dossiê corrompido bloqueia PreToolUse
        hd = os.path.join(hlab, ".willtech", "dossie.jsonl")
        with open(hd, "w", encoding="utf-8") as fh:
            fh.write("linha corrompida\noutra inválida\n")
        code, out = hook("claude", {"hook_event_name": "PreToolUse",
                                    "session_id": "compat-corrupt", **base})
        check("fail-closed-corrompido",
              code == 0 and out.get("hookSpecificOutput", {})
              .get("permissionDecision") == "deny", json.dumps(out))

        print(f"\n{PASS} PASS / {FAIL} FAIL  (plataforma: {os.name})")
        return 1 if FAIL else 0
    finally:
        shutil.rmtree(lab, ignore_errors=True)


def _is_json(line):
    try:
        json.loads(line)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    sys.exit(main())

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil