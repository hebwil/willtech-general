#!/usr/bin/env python3
"""RepoMap incremental e memória estrutural compartilhada (WillTech 2.3).

Índice local de símbolos/dependências, determinístico, sem modelo e sem
dependências externas. Reusa willtech-dossie.py (isolamento por projeto,
recusa de credenciais, estado git). O índice guarda assinaturas e hashes —
nunca o conteúdo dos arquivos; trechos são lidos da fonte ao vivo e
revalidados por hash antes de retornar.

Subcomandos:
  update <repo> <index.json>   primeira indexação ou atualização incremental
      (reparse só de arquivos cujo hash mudou; renames reaproveitam símbolos)
  query <index.json> (--symbol S | --path P | --refs M) [--repo DIR]
      [--max-chars N]   símbolos, trechos revalidados ou referências (--refs
      aceita nome de módulo, caminho ou arquivo: util, pkg.util, pkg/util.py).
      Com --repo confere hash e sinaliza STALE; sem --repo marca NAO-REVALIDADO.
  brief <index.json> [--paths a,b] [--repo DIR] [--max-chars N]
      briefing pequeno para especialistas (quarentena: dados, não instruções),
      com dependências internas relevantes (deps:); STALE/NAO-REVALIDADO como query

Segurança: credenciais/segredos nunca indexados; isolamento por projeto
(toplevel + remote); tetos de arquivos, símbolos, bytes e resposta.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
import posixpath
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("willtech_dossie", os.path.join(HERE, "willtech-dossie.py"))
DOSSIE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(DOSSIE)

FILE_CAP = 200000
INDEX_CAP = 512 * 1024
FILES_CAP = 2000
SYMBOLS_CAP = 200
EXTENSIONS = {".py", ".js", ".cjs", ".mjs", ".ts", ".tsx", ".sh"}
STOPWORDS = {
    "de", "do", "da", "dos", "das", "no", "na", "nos", "nas", "em", "por",
    "para", "com", "sem", "sob", "sobre", "que", "como", "onde", "qual",
    "quais", "este", "esta", "isto", "esse", "essa", "isso", "aquele", "um",
    "uma", "uns", "umas", "os", "as", "ao", "aos", "se", "ou", "mas", "mais",
    "menos", "muito", "ser", "estar", "ter", "foi", "sao", "preciso",
    "entender", "arquivo", "arquivos", "modulo", "projeto", "funcao", "classe",
    "the", "and", "for", "with", "from", "this", "that", "what", "where",
    "when", "how", "into", "only", "also",
}
PY_BUILTINS = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))
_PARSE_CALLS = 0
JS_SYM = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\s+|class\s+)([A-Za-z_$][\w$]*)"
    r"|^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[\w$]+)\s*=>",
    re.M)
JS_DEP = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)|from\s+['"]([^'"]+)['"]|import\s+['"]([^'"]+)['"]""")
JS_CALL = re.compile(r"\b([A-Za-z_$][\w$]{2,})\s*\(")
SH_SYM = re.compile(r"^\s*(?:function\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(\)", re.M)


def git_files(repo):
    r = subprocess.run(["git", "-C", repo, "ls-files", "-co", "--exclude-standard", "-z"],
                       capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        return None
    return [p for p in r.stdout.split("\0") if p]


def eligible(rel):
    if os.path.splitext(rel)[1].lower() not in EXTENSIONS:
        return False
    # Política central de credenciais do dossiê (P1) cobre .env*, secrets*,
    # credentials*, chaves privadas e diretórios protegidos.
    if DOSSIE.is_credential_path(rel):
        return False
    return True


def py_symbols_ext(text):
    symbols, deps, calls = [], [], []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return symbols, deps, calls
    defined = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = ", ".join(a.arg for a in node.args.args)
            symbols.append({"n": node.name, "k": "function", "l": node.lineno, "s": f"{node.name}({args})"})
            defined.add(node.name)
        elif isinstance(node, ast.ClassDef):
            symbols.append({"n": node.name, "k": "class", "l": node.lineno, "s": node.name})
            defined.add(node.name)
        elif isinstance(node, ast.Import):
            deps.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            # P4: registra módulo e nomes importados (from pkg.util import helper
            # referencia helper) e imports relativos (from . import util).
            prefix = "." * node.level + (node.module or "")
            if node.module:
                deps.append(prefix)
            deps.extend(prefix + "." + a.name for a in node.names if a.name != "*")
        elif isinstance(node, ast.Call):
            fn = node.func
            cname = None
            if isinstance(fn, ast.Name):
                cname = fn.id
            elif isinstance(fn, ast.Attribute):
                cname = fn.attr
            if cname and len(cname) >= 2 and cname not in PY_BUILTINS:
                calls.append(cname)
    uniq_calls = [c for c in dict.fromkeys(calls) if c not in defined][:SYMBOLS_CAP]
    return symbols[:SYMBOLS_CAP], list(dict.fromkeys(deps)), uniq_calls


def py_symbols(text):
    symbols, deps, _ = py_symbols_ext(text)
    return symbols, deps


def parse_symbols_ext(rel, text):
    global _PARSE_CALLS
    _PARSE_CALLS += 1
    ext = os.path.splitext(rel)[1].lower()
    if ext == ".py":
        return py_symbols_ext(text)
    if ext == ".sh":
        return ([{"n": m.group(1), "k": "function", "l": text.count("\n", 0, m.start()) + 1,
                  "s": m.group(1) + "()"} for m in SH_SYM.finditer(text)][:SYMBOLS_CAP], [], [])
    symbols, defined = [], set()
    for m in JS_SYM.finditer(text):
        name = m.group(1) or m.group(2)
        kind = "class" if "class " in m.group(0) else "function"
        symbols.append({"n": name, "k": kind, "l": text.count("\n", 0, m.start()) + 1, "s": name})
        defined.add(name)
    deps = [next(g for g in m.groups() if g) for m in JS_DEP.finditer(text)]
    js_reserved = {"if", "for", "while", "switch", "catch", "function", "return", "require", "import"}
    calls = [m.group(1) for m in JS_CALL.finditer(text)
             if m.group(1) not in defined and m.group(1) not in js_reserved]
    return symbols[:SYMBOLS_CAP], deps, list(dict.fromkeys(calls))[:SYMBOLS_CAP]


def parse_symbols(rel, text):
    symbols, deps, _ = parse_symbols_ext(rel, text)
    return symbols, deps


def raw_digest(repo, rel):
    """Lê bytes e calcula SHA-256 sem parsear AST/regex. Retorna (raw, sha256) ou None."""
    path = os.path.join(repo, rel)
    try:
        if os.path.getsize(path) > FILE_CAP:
            return None
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    if b"\0" in raw:
        return None
    return raw, hashlib.sha256(raw).hexdigest()


def file_entry(repo, rel):
    res = raw_digest(repo, rel)
    if res is None:
        return None
    raw, digest = res
    symbols, deps, calls = parse_symbols_ext(rel, raw.decode("utf-8", "replace"))
    entry = {"sha256": digest, "symbols": symbols, "deps": deps}
    if calls:
        entry["calls"] = calls
    return entry


def cmd_update(a):
    repo = os.path.abspath(a.repo)
    head, _ = DOSSIE.git_state(repo)
    if head is None:
        print("erro: não é um repositório git")
        return 2
    project = DOSSIE.project_id(repo)
    listing = git_files(repo)
    if listing is None:
        print("erro: git ls-files falhou")
        return 2
    old = {}
    if os.path.isfile(a.index):
        try:
            with open(a.index, encoding="utf-8") as fh:
                stored = json.load(fh)
            if stored.get("project") == project:
                old = stored.get("files", {})
        except (OSError, ValueError):
            old = {}
    current = [p for p in listing if eligible(p)
               and os.path.isfile(os.path.join(repo, p))][:FILES_CAP]
    removed = {k: v for k, v in old.items() if k not in set(current)}
    by_hash = {v["sha256"]: v for v in removed.values()}
    files, parsed, reused, renamed = {}, 0, 0, 0
    for rel in current:
        # Correção incremental real: revalida SHA-256 ANTES de parsear AST/regex.
        # Arquivos cujo hash não mudou (ou que foram apenas renomeados) nunca
        # reexecutam parse_symbols_ext.
        res = raw_digest(repo, rel)
        if res is None:
            continue
        raw, digest = res
        prev = old.get(rel)
        if prev and prev.get("sha256") == digest:
            files[rel] = prev
            reused += 1
        elif digest in by_hash:
            carried = by_hash[digest]
            carried_entry = {"sha256": digest, "symbols": carried["symbols"], "deps": carried["deps"]}
            if "calls" in carried:
                carried_entry["calls"] = carried["calls"]
            files[rel] = carried_entry
            renamed += 1
        else:
            symbols, deps, calls = parse_symbols_ext(rel, raw.decode("utf-8", "replace"))
            new_entry = {"sha256": digest, "symbols": symbols, "deps": deps}
            if calls:
                new_entry["calls"] = calls
            files[rel] = new_entry
            parsed += 1
    index = {"project": project, "head": head,
             "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": files}
    blob = json.dumps(index, ensure_ascii=False)
    if len(blob.encode("utf-8")) > INDEX_CAP:
        print(f"erro: índice excede teto de {INDEX_CAP} bytes; reduza o escopo do projeto")
        return 2
    tmp = a.index + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(blob)
    os.replace(tmp, a.index)
    print(f"update: parsed={parsed} reused={reused} renamed={renamed} "
          f"dropped={len(removed) - renamed} files={len(files)} bytes={len(blob.encode('utf-8'))}")
    return 0


def load_index(a):
    try:
        with open(a.index, encoding="utf-8") as fh:
            index = json.load(fh)
    except (OSError, ValueError):
        print("erro: índice ausente ou ilegível; rode update primeiro")
        return None
    if a.repo:
        if index.get("project") != DOSSIE.project_id(os.path.abspath(a.repo)):
            print("recusado: índice de outro projeto (isolamento por projeto)")
            return None
    return index


def live_snippet(repo, rel, entry, line):
    path = os.path.join(repo, rel)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return "STALE: fonte ausente"
    if hashlib.sha256(raw).hexdigest() != entry.get("sha256"):
        return "STALE: fonte mudou desde o índice; rode update (o índice não substitui a fonte)"
    lines = raw.decode("utf-8", "replace").splitlines()
    return "\n".join(lines[max(0, line - 1):line + 2])


UNREVALIDATED = ("NAO-REVALIDADO: sem --repo; índice pode estar desatualizado "
                 "(rode update ou use --repo para conferir a fonte).")


def source_state(repo, rel, entry):
    # P6: confere o hash da fonte ao vivo; devolve motivo STALE ou None (fresco).
    path = os.path.join(repo, rel)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return "STALE: fonte ausente"
    if hashlib.sha256(raw).hexdigest() != entry.get("sha256"):
        return "STALE: fonte mudou desde o índice; rode update (o índice não substitui a fonte)"
    return None


def module_path(rel):
    stem = os.path.splitext(rel)[0].replace("\\", "/")
    if stem.endswith("/__init__"):
        stem = stem[: -len("/__init__")]
    elif stem == "__init__":
        stem = ""
    return stem.replace("/", ".").lower()


def ref_key(s):
    # P4: forma canônica de módulo p/ comparação (extensão, separadores, caixa,
    # prefixos relativos "./"/"../" e dots iniciais normalizados).
    s = str(s).replace("\\", "/").lower().strip()
    s = re.sub(r"\.(py|js|cjs|mjs|ts|tsx|sh)$", "", s)
    return s.replace("/", ".").lstrip(".")


def ref_match(dep, needle):
    if not needle:
        return False
    dk = ref_key(dep)
    return dk == needle or dk.endswith("." + needle)


def dep_targets(dep, rel, by_module):
    # P4: dependência relevante = a que mapeia para um arquivo indexado do
    # projeto (interno). Externos (stdlib/libs) não entram no brief.
    d = dep.replace("\\", "/")
    if d.lower().startswith("."):
        base = posixpath.normpath(posixpath.join(posixpath.dirname(rel), d))
        cands = [base] + [base + e for e in sorted(EXTENSIONS)]
        cands += [base + "/index" + e for e in sorted(EXTENSIONS)]
        out = []
        for c in cands:
            mp = module_path(c)
            if mp in by_module and by_module[mp] not in out:
                out.append(by_module[mp])
        return out
    key = ref_key(d)
    if not key:
        return []
    if key in by_module:
        return [by_module[key]]
    parts = key.split(".")
    while len(parts) > 1:
        parts.pop()
        prefix = ".".join(parts)
        if prefix in by_module:
            return [by_module[prefix]]
    return []


def build_graph(files):
    """Constrói mapa módulo->arquivo, arestas de dependência (out_edges) e
    dependentes reversos (in_edges), incluindo acoplamento por símbolos."""
    by_module = {}
    by_symbol = {}
    for r, entry in files.items():
        mp = module_path(r)
        if mp:
            by_module.setdefault(mp, r)
        for s in entry.get("symbols", []):
            by_symbol.setdefault(s["n"].lower(), []).append(r)
    out_edges = {r: [] for r in files}
    in_edges = {r: [] for r in files}
    for r, entry in files.items():
        targets = []
        for d in entry.get("deps", []):
            for t in dep_targets(d, r, by_module):
                if t != r and t not in targets:
                    targets.append(t)
        for cname in entry.get("calls", []):
            defs = by_symbol.get(cname.lower(), [])
            if 1 <= len(defs) <= 3:
                for t in defs:
                    if t != r and t not in targets:
                        targets.append(t)
        out_edges[r] = targets
        for t in targets:
            if r not in in_edges[t]:
                in_edges[t].append(r)
    return by_module, out_edges, in_edges


def _is_test_file(rel):
    low = rel.replace("\\", "/").lower()
    base = posixpath.basename(low)
    return ("/tests/" in "/" + low or "/test/" in "/" + low
            or base.startswith("test") or "_test." in base or "-test." in base
            or ".spec." in base or ".test." in base)


def objective_tokens(objective):
    raw = re.findall(r"[A-Za-z0-9_./\-]+", (objective or "").lower())
    out = []
    for tok in raw:
        t = tok.strip("./-")
        if not t:
            continue
        if "/" in t or "." in t:
            out.append(t)
            for part in re.split(r"[/._\-]+", t):
                if len(part) >= 2 and part not in STOPWORDS:
                    out.append(part)
        elif len(t) >= 2 and t not in STOPWORDS:
            out.append(t)
    return list(dict.fromkeys(out))


def rank_files(files, objective="", scope=None, specialty=None):
    """Ranking determinístico inspirado em Personalized PageRank (Aider) +
    afinidade de símbolos (Serena), 100% stdlib sem dependências externas."""
    if not files:
        return [], {}, {}, {}
    by_module, out_edges, in_edges = build_graph(files)
    tokens = set(objective_tokens(objective))
    obj_low = (objective or "").lower()
    spec = (specialty or "").strip().lower()
    spec_map = {"explorador": "explorer", "pesquisador": "researcher",
                "testador": "tester", "revisor": "reviewer"}
    spec = spec_map.get(spec, spec)
    scope = scope or []

    seed = {}
    for r, entry in files.items():
        s = 0.05
        r_low = r.replace("\\", "/").lower()
        stem = posixpath.splitext(posixpath.basename(r_low))[0]
        if scope and any(r == sc or r.startswith(sc + "/") for sc in scope):
            s += 6.0
        if r_low in obj_low or (len(stem) >= 3 and stem in tokens):
            s += 5.0
        for part in re.split(r"[/._\-]+", r_low):
            if len(part) >= 3 and part in tokens:
                s += 1.5
        for sym in entry.get("symbols", []):
            sn = sym["n"].lower()
            if sn in tokens:
                s += 4.5
            elif len(sn) >= 4 and any(sn in t or t in sn for t in tokens if len(t) >= 4):
                s += 2.0
        is_test = _is_test_file(r)
        if spec == "tester" and is_test:
            s += 2.0
        elif spec == "visual" and (r_low.endswith((".tsx", ".ts", ".js", ".cjs", ".mjs"))
                                   or any(k in r_low for k in ("visual", "gui", "ui", "view"))):
            s += 2.0
        elif spec in ("explorer", "executor") and not is_test:
            s += 0.3
        # Centralidade estrutural leve quando não há termos fortes
        s += min(1.0, 0.15 * len(in_edges.get(r, [])))
        seed[r] = s

    total_seed = sum(seed.values()) or 1.0
    pers = {r: v / total_seed for r, v in seed.items()}
    scores = dict(pers)
    damping = 0.82
    caller_weight = 1.25 if spec == "tester" else 0.75

    for _ in range(10):
        nxt = {r: (1.0 - damping) * pers[r] for r in files}
        for r in files:
            neighbors = [(t, 1.0) for t in out_edges.get(r, [])]
            neighbors += [(c, caller_weight) for c in in_edges.get(r, [])]
            wsum = sum(w for _, w in neighbors)
            if wsum > 0:
                share = damping * scores[r] / wsum
                for nb, w in neighbors:
                    nxt[nb] += share * w
            else:
                # Nó isolado redistribui proporcionalmente ao vetor de personalização
                for nb in files:
                    nxt[nb] += damping * scores[r] * pers[nb]
        scores = nxt

    ranked = sorted(files.keys(), key=lambda r: (-round(scores[r], 8), r))
    return ranked, scores, out_edges, in_edges


def affected_tests(files, target_paths):
    """Retorna arquivos de teste impactados direta ou transitivamente (até 3 saltos)."""
    _, _, in_edges = build_graph(files)
    targets = set()
    for tp in target_paths or []:
        tp_norm = tp.replace("\\", "/").strip("/")
        for r in files:
            if r == tp_norm or r.startswith(tp_norm + "/") or module_path(r).endswith(ref_key(tp_norm)):
                targets.add(r)
    visited = set(targets)
    frontier = list(targets)
    tests = []
    for _ in range(3):
        nxt = []
        for cur in frontier:
            if _is_test_file(cur) and cur not in tests:
                tests.append(cur)
            for caller in in_edges.get(cur, []):
                if caller not in visited:
                    visited.add(caller)
                    nxt.append(caller)
                    if _is_test_file(caller) and caller not in tests:
                        tests.append(caller)
        frontier = nxt
    return sorted(tests)


def cmd_query(a):
    index = load_index(a)
    if index is None:
        return 2
    files = index.get("files", {})
    repo = os.path.abspath(a.repo) if a.repo else None
    out = []
    if a.path:
        entry = files.get(a.path)
        if not entry:
            if repo is None:
                print(UNREVALIDATED)
            print("nenhum resultado")
            return 0
        stale = source_state(repo, a.path, entry) if repo else None
        for s in entry["symbols"]:
            line = f"{a.path}:{s['l']} {s['k']} {s['s']}"
            out.append(line + ("  [STALE]" if stale else ""))
        if stale:
            out.append(stale)
    elif a.symbol:
        needle = a.symbol.lower()
        hits = [(rel, s) for rel, e in files.items() for s in e["symbols"] if needle in s["n"].lower()]
        for rel, s in hits[:10]:
            stale = source_state(repo, rel, files[rel]) if repo else None
            line = f"{rel}:{s['l']} {s['k']} {s['s']}"
            out.append(line + ("  [STALE]" if stale else ""))
        if repo:
            for rel, s in hits[:3]:
                out.append(f"TRECHO {rel}:{s['l']}\n{live_snippet(repo, rel, files[rel], s['l'])}")
    elif a.refs:
        needle = ref_key(a.refs)
        target_stale = None
        if repo:
            for tr, te in files.items():
                mp = module_path(tr)
                if mp == needle or mp.endswith("." + needle):
                    target_stale = source_state(repo, tr, te)
                    if target_stale:
                        break
        for rel, e in files.items():
            if any(ref_match(d, needle) for d in e.get("deps", [])):
                stale = (source_state(repo, rel, e) if repo else None) or target_stale
                line = f"{rel} referencia {a.refs}"
                out.append(line + ("  [STALE]" if stale else ""))
                if stale:
                    out.append(stale)
    elif getattr(a, "affected", None):
        targets = DOSSIE.scope_list(a.affected)
        impacted = affected_tests(files, targets)
        for rel in impacted:
            stale = source_state(repo, rel, files[rel]) if repo else None
            out.append(f"TEST_AFETADO {rel}" + ("  [STALE]" if stale else ""))
    if not out:
        if repo is None:
            print(UNREVALIDATED)
        print("nenhum resultado")
        return 0
    if repo is None:
        out.insert(0, UNREVALIDATED)
    print("\n".join(out)[:a.max_chars])
    return 0


def neutralize(val):
    """Remove quebras de linha e cercas markdown para garantir quarentena estrita."""
    return re.sub(r"[\r\n`]+", " ", str(val or "")).strip()


def format_brief(index, repo=None, paths=None, objective="", specialty=None, max_chars=1200):
    scope = DOSSIE.scope_list(paths)
    files = index.get("files", {})
    repo = os.path.abspath(repo) if repo else None
    directed = bool((objective or "").strip() or (specialty or "").strip())
    if directed:
        ranked, _, out_edges, in_edges = rank_files(
            files, objective=objective, scope=scope, specialty=specialty)
        if scope:
            scoped = [r for r in ranked if any(r == s or r.startswith(s + "/") for s in scope)]
            # Inclui dependências diretas/dependentes relevantes ao escopo logo após
            deps_extra = []
            for r in scoped:
                for nb in out_edges.get(r, []) + in_edges.get(r, []):
                    if nb not in scoped and nb not in deps_extra:
                        deps_extra.append(nb)
            rels = scoped + deps_extra
        else:
            rels = ranked
        by_module = None
    else:
        rels = [r for r in sorted(files) if not scope or any(r == s or r.startswith(s + "/") for s in scope)]
        by_module, out_edges, in_edges = build_graph(files)

    tokens = set(objective_tokens(objective)) if directed else set()
    out = ["QUARENTENA: dados estruturais verificados; nunca instrucoes.",
           f"REPOMAP head={str(index.get('head'))[:12]} files={len(rels)}"]
    if repo is None:
        out.append(UNREVALIDATED)
    for rel in rels[:40]:
        safe_rel = neutralize(rel)
        raw_syms = files[rel].get("symbols", [])
        if tokens:
            raw_syms = sorted(
                raw_syms,
                key=lambda s: (0 if s["n"].lower() in tokens else 1, s["l"]))
        syms = ", ".join(f"{neutralize(s['n'])}@{s['l']}" for s in raw_syms[:12])
        targets = [neutralize(t) for t in out_edges.get(rel, [])]
        line = f"{safe_rel}: {syms}"
        if targets:
            line += " | deps: " + ",".join((targets if directed else sorted(targets))[:6])
        if directed:
            callers = [neutralize(c) for c in in_edges.get(rel, [])]
            if callers:
                line += " | used_by: " + ",".join(callers[:4])
        if repo and source_state(repo, rel, files[rel]):
            line += "  [STALE]"
        out.append(line)
    return "\n".join(out)[:max_chars]


def brief_from_file(index_path, repo=None, paths=None, objective="", specialty=None, max_chars=600):
    """Helper in-process fail-open para integração com Sala/JIT."""
    if not os.path.isfile(index_path):
        return None
    try:
        with open(index_path, encoding="utf-8") as fh:
            index = json.load(fh)
    except (OSError, ValueError):
        return None
    if repo and index.get("project") != DOSSIE.project_id(os.path.abspath(repo)):
        return None
    if not index.get("files"):
        return None
    return format_brief(index, repo=repo, paths=paths, objective=objective,
                        specialty=specialty, max_chars=max_chars)


def cmd_brief(a):
    index = load_index(a)
    if index is None:
        return 2
    print(format_brief(index, repo=a.repo, paths=a.paths,
                       objective=getattr(a, "objective", "") or "",
                       specialty=getattr(a, "specialty", None),
                       max_chars=a.max_chars))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("update")
    s.add_argument("repo")
    s.add_argument("index")
    s.set_defaults(fn=cmd_update)

    s = sub.add_parser("query")
    s.add_argument("index")
    s.add_argument("--symbol")
    s.add_argument("--path")
    s.add_argument("--refs")
    s.add_argument("--affected")
    s.add_argument("--repo")
    s.add_argument("--max-chars", type=int, default=1500)
    s.set_defaults(fn=cmd_query)

    s = sub.add_parser("brief")
    s.add_argument("index")
    s.add_argument("--paths")
    s.add_argument("--objective", default="")
    s.add_argument("--specialty")
    s.add_argument("--repo")
    s.add_argument("--max-chars", type=int, default=1200)
    s.set_defaults(fn=cmd_brief)

    a = p.parse_args()
    if a.cmd == "query" and not (a.symbol or a.path or a.refs or a.affected):
        p.error("query exige --symbol, --path, --refs ou --affected")
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil