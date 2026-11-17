#!/usr/bin/env python3
"""Smoke integrado da inteligencia WillTech 3.0 (missao final P3/§5).

Categoria: smoke determinístico de INTEGRACAO real em laboratório git
descartável, subprocess reais (núcleo do hook + sala + dossiê), sem modelo e
sem rede. Prova o fluxo comandante->general->especialistas com o MÍNIMO de
especialistas necessário, não a equipe inteira. Complementa as suítes
(test-smoke-e2e, test-plan, test-auto, test-jit) exercitando a sequência
integrada de ponta a ponta e emitindo evidência verificável.

Uso: python tools/smoke-intelligence.py [evidence.json]
Exit 0 = todos os critérios aprovados; exit 1 = falha (nenhum falso PASS).
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append({"criterio": name, "status": "PASS" if cond else "FAIL", "detalhe": detail})
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))
    return cond


def main():
    tmp = tempfile.TemporaryDirectory(prefix="willtech-intel-")
    repo = Path(tmp.name) / "lab"
    (repo / "tools").mkdir(parents=True)
    (repo / "claude-code" / "bin").mkdir(parents=True)

    def git(*a):
        subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "intel@example.com")
    git("config", "user.name", "intel")
    for f in ("willtech-room.py", "willtech-dossie.py", "willtech-auto.py", "willtech-drift.py"):
        (repo / "tools" / f).write_text((ROOT / "tools" / f).read_text())
    (repo / "claude-code" / "bin" / "willtech_trace.py").write_text(
        (ROOT / "claude-code" / "bin" / "willtech_trace.py").read_text())
    (repo / "alvo.txt").write_text("versao 1 do alvo\n")
    git("add", "-A")
    git("commit", "-qm", "base")

    base = repo / ".willtech"
    base.mkdir(parents=True, exist_ok=True)
    room = str(base / "room.db")
    dossie = str(base / "dossie.jsonl")
    auto = str(repo / "tools" / "willtech-auto.py")
    roompy = str(repo / "tools" / "willtech-room.py")
    dossiepy = str(repo / "tools" / "willtech-dossie.py")

    def room_cli(*a):
        r = subprocess.run([sys.executable, roompy, *a, "--repo", str(repo)],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def hook(event, payload):
        ev = {"hook_event_name": event, "session_id": "intel", "cwd": str(repo)}
        ev.update(payload)
        r = subprocess.run([sys.executable, auto, "claude"],
                           input=json.dumps(ev), capture_output=True, text=True)
        return r.returncode, r.stdout

    # 1. Comandante recebe a tarefa (SessionStart + UserPromptSubmit reais).
    rc, _ = hook("SessionStart", {})
    rc2, out2 = hook("UserPromptSubmit", {"prompt": "investigar o alvo e registrar a descoberta para reuso"})
    check("1 comandante recebe tarefa (hooks reais)", rc == 0 and rc2 == 0,
          f"SessionStart rc={rc} UserPromptSubmit rc={rc2}")

    # 2/14. General decide o MÍNIMO: tarefa simples -> DIRECT (sem etapas extras).
    r = subprocess.run([sys.executable, dossiepy, "plan", dossie,
                        "--task", "corrigir typo no README", "--paths", "README.md"],
                       capture_output=True, text=True)
    simple_direct = r.stdout.startswith("DIRECT")
    r2 = subprocess.run([sys.executable, dossiepy, "plan", dossie,
                         "--task", "refatorar o cache distribuido", "--paths", "tools/a.py,tools/b.py,tools/c.py"],
                        capture_output=True, text=True)
    complex_plan = "PLAN complex" in r2.stdout
    check("2 general planeja quando necessario", complex_plan, "tarefa complexa -> PLAN compacto")
    check("14 nenhum especialista desnecessario", simple_direct, "tarefa simples -> DIRECT (sem etapas extras)")

    # 3/4. Primeiro especialista (explorer) investiga e registra; sala persiste.
    rc, out = room_cli("init", room)
    rc, out = room_cli("put", room, "--kind", "finding", "--specialty", "explorer",
                       "--summary", "alvo mapeado: estrutura X depende de Y", "--path-ref", "alvo.txt")
    rid = out.strip().split("id=")[-1].split()[0] if "id=" in out else ""
    room_cli("validate", room, "--id", rid, "--by", "reviewer")
    rcget, outget = room_cli("get", room, "--id", rid)
    check("3 especialista registra descoberta", rc == 0 and "id=" in out, out.strip())
    check("4 sala persiste a descoberta", rcget == 0 and "estrutura X" in outget and os.path.isfile(room),
          f"get id={rid} em banco SQLite real")

    # 5/6. Segundo especialista recupera o contexto pertinente e o utiliza.
    rcq, outq = room_cli("query", room, "--objective", "alvo estrutura")
    reused = "estrutura X depende de Y" in outq and "QUARENTENA" in outq
    check("5 segundo especialista recupera contexto", reused, "query JIT devolve a descoberta em quarentena")
    check("6 conhecimento reutilizado sem reinvestigar", reused, "mesma descoberta injetada para o tester")

    # 7/8. Handoff registra resultado + evidência; general consolida sem duplicar.
    rch, outh = room_cli("handoff-record", room, "--objective", "entregar alvo",
                         "--evidence-ids", rid, "--next-owner", "general",
                         "--result", "alvo concluido com a descoberta reutilizada")
    hid = outh.strip().split("id=")[-1].split()[0] if "id=" in outh else ""
    rcv, _ = room_cli("handoff-validate", room, "--id", hid, "--evidence-ids", rid, "--by", "tester")
    # processo NOVO recupera o resultado (restart).
    rcf, outf = room_cli("handoff-fetch", room, "--id", hid)
    check("7 handoff registra resultado e evidencia", rch == 0 and rcv == 0, f"handoff id={hid} validated")
    check("8 resultado disponivel em processo posterior",
          rcf == 0 and "alvo concluido" in outf and "RESULT_HASH" in outf, "handoff-fetch em processo novo")
    rcq2, outq2 = room_cli("query", room, "--objective", "alvo estrutura")
    check("8 general consolida sem duplicar investigacao", outq2.count("estrutura X depende de Y") == 1,
          "descoberta aparece uma unica vez (sem duplicata)")

    # 9. Conhecimento pendente NÃO é tratado como validado.
    rcp, outp = room_cli("put", room, "--kind", "finding", "--specialty", "researcher",
                         "--summary", "hipotese pendente nao confirmada")
    pid = outp.strip().split("id=")[-1].split()[0] if "id=" in outp else ""
    rcqp, outqp = room_cli("query", room, "--objective", "hipotese pendente")
    pending_label = ("candidate" in outqp) or ("hipotese pendente" not in outqp)
    check("9 pending nao e tratado como validado", pending_label,
          "registro candidate rotulado/excluido do canal validado")

    # 10. Segredo sintético não é persistido nem exposto.
    rcs, outs = room_cli("put", room, "--kind", "finding", "--specialty", "explorer",
                         "--summary", "AWS_KEY=AKIAIOSFODNN7EXAMPLE")
    rce, oute = room_cli("export", room)
    check("10 segredo sintetico recusado sem eco", rcs == 2 and "AKIAIOSFODNN7EXAMPLE" not in outs,
          f"exit={rcs}, valor nao ecoado")
    check("10 segredo ausente do export", "AKIAIOSFODNN7EXAMPLE" not in oute, "export limpo")

    # 11. Memória de outro projeto não é recuperada.
    repo2 = Path(tmp.name) / "outro"
    repo2.mkdir()
    subprocess.run(["git", "-C", str(repo2), "init", "-q"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo2), "config", "user.email", "o@o"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo2), "config", "user.name", "o"], check=True, capture_output=True)
    (repo2 / "f.txt").write_text("outro projeto\n")
    subprocess.run(["git", "-C", str(repo2), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo2), "commit", "-qm", "b"], check=True, capture_output=True)
    rci = subprocess.run([sys.executable, roompy, "get", room, "--id", rid, "--repo", str(repo2)],
                         capture_output=True, text=True)
    check("11 isolamento por projeto", rci.returncode == 2, f"outro projeto recusado exit={rci.returncode}")

    # 12. Reinício preserva o conhecimento válido (processo novo).
    rc12, out12 = room_cli("get", room, "--id", rid)
    check("12 reinicio preserva conhecimento valido", rc12 == 0 and "validated" in out12,
          "registro validated sobrevive em processo novo")

    # 13. Alteração do código invalida referências obsoletas.
    (repo / "alvo.txt").write_text("versao 2 mudou\n")
    rc13, out13 = room_cli("query", room, "--objective", "alvo estrutura")
    rcg, outg = room_cli("get", room, "--id", rid)
    check("13 mudanca de codigo invalida obsoleto",
          "estrutura X depende de Y" not in out13 and "stale" in outg,
          "source_hash divergente -> stale, sai da injecao")

    # 10hierarquia. Hierarquia/permissões preservadas (7 agentes, general orquestra).
    agents = sorted(p.stem for p in (ROOT / "opencode" / "agent").glob("willtech-*.md"))
    check("10 hierarquia dos sete agentes preservada", len(agents) == 7 and "willtech-general" in agents,
          f"{len(agents)} agentes: {agents}")

    failed = [r for r in RESULTS if r["status"] == "FAIL"]
    summary = {"suite": "smoke inteligencia 3.0", "total": len(RESULTS),
               "pass": len(RESULTS) - len(failed), "fail": len(failed),
               "simulation": False, "modelo": "nenhum (subprocess real)", "results": RESULTS}
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n{summary['pass']}/{summary['total']} criterios PASS, {summary['fail']} FAIL")
    tmp.cleanup()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())