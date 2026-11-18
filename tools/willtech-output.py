#!/usr/bin/env python3
"""Saídas eficientes de ferramentas com prova integral preservada (WillTech 3.0).

Inspirado em conceitos de compactação estruturada (RTK), implementado 100% em
stdlib Python de forma determinística, local e estritamente OPT-IN:
- NUNCA intercepta ou substitui comandos do usuário automaticamente.
- Salva SEMPRE o log bruto integral em disco (.willtech/logs/<sha256>.log) e
  emite caminho + hash SHA-256 de evidência verificável.
- Deduplica linhas informativas repetidas e sintetiza ruído de sucesso.
- JAMAIS oculta stderr, exit code != 0, stacktraces, Tracebacks, AssertionError,
  FAIL/ERROR ou avisos críticos: em presença de erro, todos os blocos de falha
  permanecem íntegros na saída.
- Testador e Revisor conservam acesso integral ao log original (`--full` ou
  subcomando `read-log` com verificação de SHA-256).
"""
import argparse
import hashlib
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

_dspec = importlib.util.spec_from_file_location(
    "willtech_dossie", os.path.join(HERE, "willtech-dossie.py"))
DOSSIE = importlib.util.module_from_spec(_dspec)
_dspec.loader.exec_module(DOSSIE)

_tspec_path = os.path.join(ROOT, "claude-code", "bin", "willtech_trace.py")
if os.path.isfile(_tspec_path):
    _tspec = importlib.util.spec_from_file_location("willtech_trace", _tspec_path)
    TRACE = importlib.util.module_from_spec(_tspec)
    _tspec.loader.exec_module(TRACE)
else:
    TRACE = None

CATEGORIES = ("test", "git", "list", "generic")
ROLES = ("explorer", "researcher", "visual", "executor", "tester", "reviewer", "general",
         "explorador", "pesquisador", "testador", "revisor", "comandante")

ERROR_LINE_RE = re.compile(
    r"(?i)(\btraceback\b|\bexception\b|\berror\b|\bfail(?:ed|ure)?\b|"
    r"\bassertionerror\b|\bfatal\b|\bpanic\b|\bsegfault\b|"
    r"\bsyntaxerror\b|\btypeerror\b|\bvalueerror\b|\bkeyerror\b|"
    r"^\s*E\s+|^\s*at\s+\S+\s*\()")
PASS_TEST_RE = re.compile(
    r"^(\s*test_[A-Za-z0-9_]+\s+\([^)]+\)\s+\.\.\.\s+ok\s*$|"
    r"\s*ok\s+\d*\s*\S.*$|\s*PASS\s+\S.*$|\s*✓\s+\S.*$)")


def _redact(text):
    return TRACE.redact(text) if TRACE else text


def _is_critical_block_start(line):
    low = line.strip().lower()
    return (low.startswith("traceback (most recent call last)")
            or low.startswith("======")
            or low.startswith("fail:")
            or low.startswith("error:"))


def deduplicate_lines(lines):
    """Deduplica linhas idênticas consecutivas e repetições frequentes de ruído,
    JAMAIS descartando linhas de erro/falha/stacktrace."""
    if not lines:
        return [], 0
    out = []
    deduped = 0
    i = 0
    n = len(lines)
    while i < n:
        cur = lines[i]
        if ERROR_LINE_RE.search(cur):
            out.append(cur)
            i += 1
            continue
        j = i + 1
        while j < n and lines[j] == cur:
            j += 1
        count = j - i
        if count > 1:
            out.append(f"{cur}  [repetido x{count}]")
            deduped += count - 1
        else:
            out.append(cur)
        i = j
    return out, deduped


def summarize_stream(stdout_text, stderr_text="", exit_code=0,
                     category="generic", max_chars=1600):
    """Gera resumo estruturado seguro. Nunca omite stderr ou blocos de erro."""
    raw_lines = (stdout_text or "").splitlines()
    err_lines = (stderr_text or "").splitlines()
    dedup_lines, dedup_count = deduplicate_lines(raw_lines)

    critical_lines = []
    normal_lines = []
    pass_count = 0
    in_trace = False

    for ln in dedup_lines:
        stripped = ln.strip()
        if _is_critical_block_start(ln):
            in_trace = True
            critical_lines.append(ln)
            continue
        if in_trace:
            critical_lines.append(ln)
            if stripped == "" and len(critical_lines) > 3:
                in_trace = False
            continue
        if ERROR_LINE_RE.search(ln):
            critical_lines.append(ln)
        elif category == "test" and PASS_TEST_RE.match(ln):
            pass_count += 1
        else:
            normal_lines.append(ln)

    has_failure = (exit_code not in (0, None)) or bool(err_lines) or bool(critical_lines)
    out = []
    status_tag = "ERROR_DETECTED" if has_failure else "OK"
    out.append(
        f"TOOL_SUMMARY status={status_tag} category={category} "
        f"exit={exit_code if exit_code is not None else 0} "
        f"lines={len(raw_lines)} dedup={dedup_count}"
    )

    if pass_count:
        out.append(f"CHECKS_OK: {pass_count} verificacoes aprovadas compactadas")

    # Stderr SEMPRE preservado integralmente (redigindo apenas segredos explícitos)
    if err_lines:
        out.append("STDERR (integral):")
        for el in err_lines:
            out.append(_redact(el))

    # Blocos críticos/falhas/tracebacks SEMPRE preservados
    if critical_lines:
        out.append("FALHAS_E_EVIDENCIAS (integral):")
        for cl in critical_lines:
            out.append(_redact(cl))

    # Em ausência de falha (ou como contexto complementar), inclui amostras úteis
    budget_left = max(200, int(max_chars) - sum(len(x) + 1 for x in out) - 180)
    if normal_lines and budget_left > 40:
        kept = []
        used = 0
        head_n = 12 if not has_failure else 6
        tail_n = 6
        if len(normal_lines) <= head_n + tail_n:
            candidates = normal_lines
            omitted_mid = 0
        else:
            candidates = normal_lines[:head_n] + [
                f"... ({len(normal_lines) - head_n - tail_n} linhas intermediarias no log bruto) ..."
            ] + normal_lines[-tail_n:]
            omitted_mid = len(normal_lines) - head_n - tail_n
        for nl in candidates:
            rnl = _redact(nl)
            if used + len(rnl) + 1 > budget_left and kept and not has_failure:
                kept.append("... (consulte RAW_LOG para listagem integral)")
                break
            kept.append(rnl)
            used += len(rnl) + 1
        if kept:
            out.extend(kept)

    return "\n".join(out)


def persist_and_summarize(stdout_text, stderr_text="", exit_code=0,
                          category="generic", log_dir=None, repo=".",
                          role="general", full=False, max_chars=1600):
    """Salva o log bruto imutável em disco, calcula SHA-256 e devolve resumo
    (ou conteúdo bruto integral quando `full=True`)."""
    repo_abs = os.path.abspath(repo)
    if log_dir is None:
        log_dir_abs = os.path.join(repo_abs, ".willtech", "logs")
    else:
        log_dir_abs = os.path.abspath(log_dir) if os.path.isabs(log_dir) else os.path.abspath(
            os.path.join(repo_abs, log_dir))

    if DOSSIE.is_credential_path(log_dir_abs):
        raise ValueError("recusado: diretório de log aponta para caminho sensível")

    combined = stdout_text or ""
    if stderr_text:
        if combined and not combined.endswith("\n"):
            combined += "\n"
        combined += "[STDERR]\n" + stderr_text
    raw_bytes = combined.encode("utf-8", "replace")
    sha = hashlib.sha256(raw_bytes).hexdigest()

    os.makedirs(log_dir_abs, exist_ok=True)
    log_path = os.path.join(log_dir_abs, f"{sha[:16]}.log")
    if not os.path.isfile(log_path):
        tmp = log_path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(raw_bytes)
        os.replace(tmp, log_path)

    try:
        rel_log = os.path.relpath(log_path, repo_abs).replace("\\", "/")
        if rel_log.startswith(".."):
            rel_log = log_path
    except ValueError:
        rel_log = log_path

    footer = (f"RAW_LOG: path={rel_log} evidence_hash={sha} "
              f"bytes={len(raw_bytes)}")

    if full:
        return _redact(combined) + ("\n" if not combined.endswith("\n") else "") + footer

    summary = summarize_stream(stdout_text, stderr_text=stderr_text,
                               exit_code=exit_code, category=category,
                               max_chars=max_chars)
    return summary + "\n" + footer


def cmd_summarize(a):
    if a.category not in CATEGORIES:
        print(f"recusado: --category inválida (use {', '.join(CATEGORIES)})")
        return 2
    if a.role and a.role.lower() not in ROLES:
        print("recusado: --role inválido")
        return 2
    if a.input_file:
        if DOSSIE.is_credential_path(a.input_file):
            print("recusado: caminho de credencial")
            return 2
        if not os.path.isfile(a.input_file):
            print("recusado: arquivo de entrada ausente")
            return 2
        with open(a.input_file, encoding="utf-8", errors="replace") as fh:
            stdout_text = fh.read()
    else:
        stdout_text = sys.stdin.read()

    stderr_text = ""
    if a.stderr_file:
        if DOSSIE.is_credential_path(a.stderr_file):
            print("recusado: caminho de credencial em --stderr-file")
            return 2
        if not os.path.isfile(a.stderr_file):
            print("recusado: --stderr-file ausente")
            return 2
        with open(a.stderr_file, encoding="utf-8", errors="replace") as fh:
            stderr_text = fh.read()

    try:
        rendered = persist_and_summarize(
            stdout_text, stderr_text=stderr_text, exit_code=a.exit_code,
            category=a.category, log_dir=a.log_dir, repo=a.repo,
            role=a.role or "general", full=a.full, max_chars=a.max_chars)
    except (OSError, ValueError) as exc:
        print(str(exc))
        return 2
    print(rendered)
    return 0


def cmd_read_log(a):
    if DOSSIE.is_credential_path(a.log_path):
        print("recusado: caminho de credencial")
        return 2
    p = os.path.abspath(a.log_path) if os.path.isabs(a.log_path) else os.path.abspath(
        os.path.join(a.repo, a.log_path))
    if not os.path.isfile(p):
        print("recusado: log bruto ausente")
        return 2
    with open(p, "rb") as fh:
        raw = fh.read()
    actual = hashlib.sha256(raw).hexdigest()
    if a.expected_sha256:
        exp = a.expected_sha256.strip().lower()
        if not actual.startswith(exp):
            print(f"recusado: hash divergente do log bruto (expected={exp[:16]} actual={actual[:16]})")
            return 2
    sys.stdout.write(raw.decode("utf-8", "replace"))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("summarize")
    s.add_argument("input_file", nargs="?")
    s.add_argument("--stderr-file")
    s.add_argument("--exit-code", type=int, default=0)
    s.add_argument("--category", default="generic")
    s.add_argument("--log-dir")
    s.add_argument("--repo", default=".")
    s.add_argument("--role", default="general")
    s.add_argument("--max-chars", type=int, default=1600)
    s.add_argument("--full", action="store_true")
    s.set_defaults(fn=cmd_summarize)

    s = sub.add_parser("read-log")
    s.add_argument("log_path")
    s.add_argument("--expected-sha256")
    s.add_argument("--repo", default=".")
    s.set_defaults(fn=cmd_read_log)

    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil
