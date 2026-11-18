#!/usr/bin/env python3
"""Suíte de Homologação Anti-Falso-Pass — Inteligência Adaptativa 3.0.

Categoria: PASS DETERMINÍSTICO / PASS INTEGRAÇÃO (subprocessos reais, SQLite real,
repositórios Git descartáveis reais, sem mocks da Sala, sem enfraquecer asserções).

Cobre integralmente a Seção 7 (Testes positivos + negativos e adversariais):
- Recuperação da evidência correta e orçamentos 0 / 256 / 512 / 1200 + --expand
- Memória especializada dos 7 agentes (explorer, researcher, visual, executor,
  tester, reviewer, general) com exclusão mecânica de conclusões no revisor
- Reaproveitamento entre sessões + histórico hit_count + deduplicação
- Conhecimento obsoleto (stale) invalidado por mudança/remoção de código
- Candidatos e inválidos nunca promovidos sem evidência/autoridade/gate humano
- Isolamento estrito entre projetos + biblioteca interprojetos controlada
- Segredos recusados sem eco + injeção neutralizada sob QUARENTENA
- Compactação opt-in de logs (willtech-output.py) sem jamais omitir stderr/erros
  e com detecção de hash divergente no log bruto
- Fallback automático para comportamento 3.0 seguro se o mecanismo adaptativo falhar
- Preservação integral de ferramentas/permissões dos 7 agentes nas 3 plataformas
- Concorrência SQLite + fallback real sem FTS5 + backup/restore sem perda
"""
import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROOM_TOOL = ROOT / "tools" / "willtech-room.py"
AUTO_TOOL = ROOT / "tools" / "willtech-auto.py"
REPOMAP_TOOL = ROOT / "tools" / "willtech-repomap.py"
OUTPUT_TOOL = ROOT / "tools" / "willtech-output.py"


def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def run_tool(tool, *args, env=None, inp=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    r = subprocess.run([sys.executable, str(tool), *[str(a) for a in args]],
                       input=inp, capture_output=True, text=True, env=e, timeout=30)
    return r.returncode, r.stdout + r.stderr


def make_lab_repo(base, name):
    repo = Path(base) / name
    (repo / "tools").mkdir(parents=True)
    (repo / "claude-code" / "bin").mkdir(parents=True)
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "homolog@willtech.local")
    git(repo, "config", "user.name", "homolog")
    for fn in ("willtech-room.py", "willtech-dossie.py", "willtech-auto.py",
               "willtech-repomap.py", "willtech-output.py", "willtech-drift.py",
               "willtech-supervisor.py"):
        shutil.copy(ROOT / "tools" / fn, repo / "tools" / fn)
    shutil.copy(ROOT / "claude-code" / "bin" / "willtech_trace.py",
                repo / "claude-code" / "bin" / "willtech_trace.py")
    (repo / "src" / "validator.py").write_text(
        "def validar_taxa(taxa):\n    return 0.0 <= taxa <= 0.5\n", encoding="utf-8")
    (repo / "src" / "calc.py").write_text(
        "from src.validator import validar_taxa\n\n"
        "def calcular_desconto(valor, taxa):\n"
        "    if not validar_taxa(taxa):\n        raise ValueError('taxa invalida')\n"
        "    return round(valor * (1.0 - taxa), 2)\n", encoding="utf-8")
    (repo / "src" / "ui_card.tsx").write_text(
        "export function PriceCard(props) { return null; }\n", encoding="utf-8")
    (repo / "tests" / "test_calc.py").write_text(
        "from src.calc import calcular_desconto\n\n"
        "def test_desconto():\n    assert calcular_desconto(100, 0.1) == 90.0\n",
        encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    return repo


class AdaptiveIntelligencePositiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="wt-adapt-pos-", ignore_cleanup_errors=True)
        cls.repo = make_lab_repo(cls.tmp.name, "proj-main")
        cls.base = cls.repo / ".willtech"
        cls.base.mkdir(parents=True, exist_ok=True)
        (cls.base / "enabled").write_text("", encoding="utf-8")
        cls.room = str(cls.base / "room.db")
        cls.repomap = str(cls.base / "repomap.json")

        rc, out = run_tool(ROOM_TOOL, "init", cls.room, "--repo", cls.repo)
        assert rc == 0, out
        rc, out = run_tool(REPOMAP_TOOL, "update", cls.repo, cls.repomap)
        assert rc == 0, out

        # Semeia registros reais para todas as 7 especialidades + ruído irrelevante
        seeds = [
            ("finding", "explorer", "calcular_desconto aplica validar_taxa e arredonda 2 casas", "src/calc.py", True),
            ("finding", "explorer", "validar_taxa aceita intervalo fechado 0.0 ate 0.5", "src/validator.py", True),
            ("ref", "researcher", "Documentacao decimal Python 3.12 recomenda round bancario", "src/calc.py", True),
            ("decision", "visual", "PriceCard exige contraste WCAG AA 4.5:1 e aria-label", "src/ui_card.tsx", True),
            ("decision", "executor", "Preservar assinatura calcular_desconto(valor, taxa) sem alterar API", "src/calc.py", True),
            ("test_result", "tester", "test_calc.py 4/4 verdes cobrindo bordas 0.0 e 0.5", "tests/test_calc.py", True),
            ("risk", "reviewer", "Risco de float impreciso acima de 10^9 sem Decimal", "src/calc.py", True),
            ("finding", "explorer", "Modulo legado de relatorio CSV sem relacao com desconto", None, False),
        ]
        cls.ids = {}
        for kind, spec, summary, pref, should_val in seeds:
            args = ["put", cls.room, "--repo", cls.repo, "--kind", kind,
                    "--specialty", spec, "--summary", summary]
            if pref:
                args += ["--path-ref", pref]
            else:
                args += ["--evidence-hash", "deadbeef1234"]
            rc, out = run_tool(ROOM_TOOL, *args)
            assert rc == 0, out
            rid = int(out.split("id=")[1].split()[0])
            cls.ids[(kind, spec, summary[:18])] = rid
            if should_val:
                rc, vout = run_tool(ROOM_TOOL, "validate", cls.room, "--repo", cls.repo,
                                    "--id", rid, "--by", "reviewer")
                assert rc == 0, vout

        # Promove 1 micro-skill com aprovação humana explícita para tester
        rc, out = run_tool(ROOM_TOOL, "skill-add", cls.room, "--repo", cls.repo,
                           "--specialty", "tester",
                           "--instruction", "Executar python3 -m unittest tests/test_calc.py antes de validar",
                           "--scope", "src/calc.py", "--trigger", "desconto",
                           "--evidence-hash", "cafebabe1234")
        assert rc == 0, out
        sid = int(out.split("id=")[1].split()[0])
        rc, out = run_tool(ROOM_TOOL, "skill-promote", cls.room, "--repo", cls.repo,
                           "--id", sid, "--i-approve-human")
        assert rc == 0, out

        # Registra handoff com conclusão do executor (não pode vazar ao revisor)
        first_id = next(iter(cls.ids.values()))
        rc, out = run_tool(ROOM_TOOL, "handoff-record", cls.room, "--repo", cls.repo,
                           "--objective", "Revisar modulo calcular_desconto",
                           "--evidence-ids", f"{first_id}",
                           "--files", "src/calc.py,tests/test_calc.py",
                           "--next-owner", "reviewer",
                           "--result", "EXECUTOR_AFIRMA_TUDO_PERFEITO_SEM_DEFEITOS_999")
        assert rc == 0, out
        cls.handoff_id = int(out.split("id=")[1].split()[0])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_01_adaptive_budgets_0_256_512_1200_and_expand(self):
        # Orçamento 0 quando nada pertinente casa (mesmo com prompt longo cheio de stopwords!)
        rc, out0 = run_tool(
            ROOM_TOOL, "query", self.room, "--repo", self.repo, "--adaptive",
            "--objective", "Preciso entender o comportamento de kubernetes helm chart neste projeto")
        self.assertEqual(rc, 0)
        self.assertEqual(out0.strip(), "", f"esperava 0 bytes para assunto alheio, obtive: {out0}")

        # Orçamentos explícitos 0, 256, 512 e 1200 respeitados e funcionais
        rc, b0 = run_tool(ROOM_TOOL, "query", self.room, "--repo", self.repo,
                          "--adaptive", "--budget-chars", "0",
                          "--objective", "calcular_desconto validar_taxa")
        self.assertEqual(rc, 0)
        self.assertEqual(b0, "")

        for b in (256, 512, 1200):
            rc, bout = run_tool(ROOM_TOOL, "query", self.room, "--repo", self.repo,
                                "--adaptive", "--budget-chars", str(b),
                                "--objective", "calcular_desconto validar_taxa src/calc.py")
            self.assertEqual(rc, 0, bout)
            self.assertIn("QUARENTENA", bout)
            self.assertIn("calcular_desconto", bout)
            self.assertNotIn("CSV sem relacao", bout)
            self.assertLessEqual(len(bout.rstrip("\n")), b)

        # Expansão sob demanda (--expand e get --full) recupera evidência integral
        rc, exp_out = run_tool(ROOM_TOOL, "query", self.room, "--repo", self.repo,
                               "--adaptive", "--expand",
                               "--objective", "calcular_desconto validar_taxa PriceCard Decimal")
        self.assertEqual(rc, 0, exp_out)
        self.assertIn("budget=8000", exp_out)
        self.assertIn("calcular_desconto", exp_out)
        self.assertIn("validar_taxa", exp_out)

        first_id = next(iter(self.ids.values()))
        rc, full_get = run_tool(ROOM_TOOL, "get", self.room, "--repo", self.repo,
                                "--id", first_id, "--full")
        self.assertEqual(rc, 0, full_get)
        self.assertIn("live_source=FRESH", full_get)
        self.assertIn("hit_count", full_get)

    def test_02_seven_specialists_receive_tailored_context_and_reviewer_stays_independent(self):
        # 1. Explorador: recebe símbolos/deps do RepoMap + findings estruturais
        rc, p_exp = run_tool(ROOM_TOOL, "context-pack", self.room, "--repo", self.repo,
                             "--for-agent", "explorador",
                             "--objective", "calcular_desconto", "--paths", "src/calc.py")
        self.assertEqual(rc, 0, p_exp)
        self.assertIn("agent=explorer", p_exp)
        self.assertIn("src/calc.py: calcular_desconto", p_exp)
        self.assertIn("deps: src/validator.py", p_exp)

        # 2. Pesquisador: recebe refs verificadas com data de atualização
        rc, p_res = run_tool(ROOM_TOOL, "context-pack", self.room, "--repo", self.repo,
                             "--for-agent", "pesquisador", "--objective", "decimal round")
        self.assertEqual(rc, 0, p_res)
        self.assertIn("agent=researcher", p_res)
        self.assertIn("ref/researcher", p_res)
        self.assertIn("updated=", p_res)

        # 3. Visual: recebe decisões de UI/WCAG
        rc, p_vis = run_tool(ROOM_TOOL, "context-pack", self.room, "--repo", self.repo,
                             "--for-agent", "visual", "--objective", "PriceCard contraste")
        self.assertEqual(rc, 0, p_vis)
        self.assertIn("agent=visual", p_vis)
        self.assertIn("WCAG AA", p_vis)

        # 4. Executor: recebe escopo + decisões de implementação + RepoMap
        rc, p_exe = run_tool(ROOM_TOOL, "context-pack", self.room, "--repo", self.repo,
                             "--for-agent", "executor",
                             "--objective", "calcular_desconto", "--paths", "src/calc.py")
        self.assertEqual(rc, 0, p_exe)
        self.assertIn("ESCOPO: src/calc.py", p_exe)
        self.assertIn("Preservar assinatura calcular_desconto", p_exe)

        # 5. Testador: recebe critérios de aceite + TESTES_AFETADOS via grafo reverso + skill
        rc, p_tst = run_tool(ROOM_TOOL, "context-pack", self.room, "--repo", self.repo,
                             "--for-agent", "testador",
                             "--objective", "desconto", "--paths", "src/validator.py",
                             "--accept", "bordas 0.0 e 0.5 validadas")
        self.assertEqual(rc, 0, p_tst)
        self.assertIn("ACEITE: bordas 0.0 e 0.5 validadas", p_tst)
        self.assertIn("TESTES_AFETADOS: tests/test_calc.py", p_tst)
        self.assertIn("skill/tester validated", p_tst)

        # 6. Revisor: recebe aceite + evidências independentes; JAMAIS conclusão do executor
        rc, p_rev = run_tool(ROOM_TOOL, "context-pack", self.room, "--repo", self.repo,
                             "--for-agent", "revisor", "--handoff-id", self.handoff_id,
                             "--objective", "calcular_desconto")
        self.assertEqual(rc, 0, p_rev)
        self.assertIn("POLITICA_GOLDFISH", p_rev)
        self.assertIn("EVIDENCE", p_rev)
        self.assertNotIn("EXECUTOR_AFIRMA_TUDO_PERFEITO_SEM_DEFEITOS_999", p_rev)
        self.assertNotIn("decision/executor", p_rev)
        self.assertIn("omitido por política", p_rev)

        # 7. General: recebe visão consolidada de handoffs, owners e achados validados
        rc, p_gen = run_tool(ROOM_TOOL, "context-pack", self.room, "--repo", self.repo,
                             "--for-agent", "general", "--objective", "calcular_desconto")
        self.assertEqual(rc, 0, p_gen)
        self.assertIn("agent=general", p_gen)
        self.assertIn("HANDOFF_PENDENTE", p_gen)

    def test_03_hook_auto_modes_A_B_C_and_non_private_metrics(self):
        prompt_hit = (
            "Preciso investigar a funcao calcular_desconto em src/calc.py e sua "
            "dependencia validar_taxa para planejar uma evolucao segura do calculo "
            "financeiro mantendo compatibilidade total com os testes atuais."
        )
        prompt_miss = (
            "Preciso entender como configurar um cluster erlang distribuido "
            "inexistente neste repositorio apenas para tirar uma duvida conceitual "
            "longa com mais de duzentos caracteres sem tocar em nenhum modulo daqui."
        )
        ev_hit = json.dumps({"hook_event_name": "UserPromptSubmit",
                             "session_id": "s-hit", "cwd": str(self.repo),
                             "prompt": prompt_hit})
        ev_miss = json.dumps({"hook_event_name": "UserPromptSubmit",
                              "session_id": "s-miss", "cwd": str(self.repo),
                              "prompt": prompt_miss})

        # Modo A (baseline 3.0): injeta DOSSIE absent mesmo no prompt_miss
        rc, out_a_miss = run_tool(self.repo / "tools" / "willtech-auto.py", "opencode",
                                  env={"WILLTECH_ADAPTIVE_JIT": "0"}, inp=ev_miss)
        self.assertEqual(rc, 0)
        da_miss = json.loads(out_a_miss)
        self.assertIn("DOSSIE absent", da_miss["context"])

        # Modo B (JIT adaptativo): 0 chars em prompt_miss; achado validado em prompt_hit
        rc, out_b_miss = run_tool(self.repo / "tools" / "willtech-auto.py", "opencode",
                                  env={"WILLTECH_ADAPTIVE_JIT": "1",
                                       "WILLTECH_SPECIALIZED_MEMORY": "0"}, inp=ev_miss)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out_b_miss)["context"], "")

        rc, out_b_hit = run_tool(self.repo / "tools" / "willtech-auto.py", "opencode",
                                 env={"WILLTECH_ADAPTIVE_JIT": "1",
                                      "WILLTECH_SPECIALIZED_MEMORY": "0"}, inp=ev_hit)
        self.assertEqual(rc, 0)
        ctx_b = json.loads(out_b_hit)["context"]
        self.assertIn("calcular_desconto", ctx_b)
        self.assertNotIn("DOSSIE absent", ctx_b)

        # Modo C (JIT adaptativo + RepoMap direcionado + memória especializada)
        rc, out_c_hit = run_tool(self.repo / "tools" / "willtech-auto.py", "opencode",
                                 env={"WILLTECH_ADAPTIVE_JIT": "1",
                                      "WILLTECH_SPECIALIZED_MEMORY": "1"}, inp=ev_hit)
        self.assertEqual(rc, 0)
        ctx_c = json.loads(out_c_hit)["context"]
        self.assertIn("calcular_desconto", ctx_c)
        self.assertIn("MAP src/calc.py", ctx_c)
        self.assertIn("deps:src/validator.py", ctx_c)

        # Métricas gravadas sem conteúdo privado do prompt
        mfile = self.base / "jit-metrics.jsonl"
        self.assertTrue(mfile.is_file())
        raw_metrics = mfile.read_text(encoding="utf-8")
        self.assertNotIn("erlang distribuido", raw_metrics)
        self.assertNotIn("evolucao segura do calculo", raw_metrics)

        # Valida que o plugin OpenCode V2 possui normalização defensiva de grep e read
        plugin_code = (ROOT / "opencode" / "plugins" / "willtech" / "index.js").read_text(encoding="utf-8")
        self.assertIn('ev.tool === "grep"', plugin_code)
        self.assertIn("statSync(fullP).isFile()", plugin_code)
        self.assertIn('ev.tool === "read"', plugin_code)


class AdaptiveIntelligenceAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wt-adapt-adv-", ignore_cleanup_errors=True)
        self.repo = make_lab_repo(self.tmp.name, "proj-a")
        self.room = str(self.repo / ".willtech" / "room.db")
        run_tool(ROOM_TOOL, "init", self.room, "--repo", self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_04_stale_detection_and_deduplication(self):
        # Registra 2 descobertas quase idênticas -> dedup entrega apenas 1
        for s in ("calcular_desconto valida taxa e arredonda resultado",
                  "calcular_desconto valida a taxa e arredonda o resultado"):
            rc, out = run_tool(ROOM_TOOL, "put", self.room, "--repo", self.repo,
                               "--kind", "finding", "--specialty", "explorer",
                               "--summary", s, "--path-ref", "src/calc.py")
            self.assertEqual(rc, 0, out)
            rid = out.split("id=")[1].split()[0]
            run_tool(ROOM_TOOL, "validate", self.room, "--repo", self.repo,
                     "--id", rid, "--by", "tester")

        rc, q1 = run_tool(ROOM_TOOL, "query", self.room, "--repo", self.repo,
                          "--adaptive", "--objective", "calcular_desconto taxa")
        self.assertEqual(rc, 0, q1)
        self.assertIn("hits=1", q1)

        # Altera src/calc.py -> source_hash diverge -> ambos viram stale e saem!
        (self.repo / "src" / "calc.py").write_text(
            "def calcular_desconto(valor, taxa):\n    return valor\n", encoding="utf-8")
        rc, q2 = run_tool(ROOM_TOOL, "query", self.room, "--repo", self.repo,
                          "--adaptive", "--objective", "calcular_desconto taxa")
        self.assertEqual(rc, 0)
        self.assertEqual(q2.strip(), "", "conhecimento stale jamais pode ser injetado como vigente")

    def test_05_interproject_isolation_and_controlled_pattern_library(self):
        repo_b = make_lab_repo(self.tmp.name, "proj-b")
        room_b = str(repo_b / ".willtech" / "room.db")
        run_tool(ROOM_TOOL, "init", room_b, "--repo", repo_b)

        # Registra candidato (id 1) e validado (id 2) e skill validada (id 3) em A
        run_tool(ROOM_TOOL, "put", self.room, "--repo", self.repo,
                 "--kind", "decision", "--specialty", "executor",
                 "--summary", "Padrao candidato nao exportavel",
                 "--evidence-hash", "aaaa1111")
        run_tool(ROOM_TOOL, "put", self.room, "--repo", self.repo,
                 "--kind", "decision", "--specialty", "executor",
                 "--summary", "Usar transacao atomica com rollback explicito em migracoes SQLite",
                 "--evidence-hash", "bbbb2222")
        run_tool(ROOM_TOOL, "validate", self.room, "--repo", self.repo,
                 "--id", "2", "--by", "reviewer")
        run_tool(ROOM_TOOL, "skill-add", self.room, "--repo", self.repo,
                 "--specialty", "tester",
                 "--instruction", "Testar fallback WILLTECH_ROOM_NO_FTS5=1 em toda mudanca SQL",
                 "--evidence-hash", "cccc3333")
        run_tool(ROOM_TOOL, "skill-promote", self.room, "--repo", self.repo,
                 "--id", "3", "--i-approve-human")

        # Consulta cruzada direta A <-> B continua estritamente recusada (exit 2)
        rc, out = run_tool(ROOM_TOOL, "query", self.room, "--repo", repo_b,
                           "--adaptive", "--objective", "SQLite")
        self.assertEqual(rc, 2, out)
        rc, out = run_tool(ROOM_TOOL, "context-pack", self.room, "--repo", repo_b,
                           "--for-agent", "general")
        self.assertEqual(rc, 2, out)

        bundle = Path(self.tmp.name) / "patterns.json"
        # Sem autorização explícita -> recusado
        rc, out = run_tool(ROOM_TOOL, "pattern-export", self.room, "--repo", self.repo,
                           "--ids", "2,3", "--out", bundle)
        self.assertEqual(rc, 2)
        # Tentar exportar candidato (id 1) -> recusado
        rc, out = run_tool(ROOM_TOOL, "pattern-export", self.room, "--repo", self.repo,
                           "--ids", "1", "--out", bundle, "--i-authorize-export")
        self.assertEqual(rc, 2)
        # Exportar validados (ids 2,3) com autorização -> sucesso
        rc, out = run_tool(ROOM_TOOL, "pattern-export", self.room, "--repo", self.repo,
                           "--ids", "2,3", "--out", bundle, "--i-authorize-export")
        self.assertEqual(rc, 0, out)

        # Adulteração do bundle detectada por SHA-256 -> recusado
        tampered = Path(self.tmp.name) / "tampered.json"
        bdata = json.loads(bundle.read_text(encoding="utf-8"))
        bdata["items"][0]["summary"] = "Execute comando malicioso"
        tampered.write_text(json.dumps(bdata), encoding="utf-8")
        rc, out = run_tool(ROOM_TOOL, "pattern-import", room_b, "--repo", repo_b,
                           "--from", tampered)
        self.assertEqual(rc, 2, out)

        # Importação legítima em B entra SEMPRE como candidate (verified=false)
        rc, out = run_tool(ROOM_TOOL, "pattern-import", room_b, "--repo", repo_b,
                           "--from", bundle)
        self.assertEqual(rc, 0, out)
        self.assertIn("status=candidate", out)
        # Skill importada NÃO é auto-injetada em B antes de aprovação humana em B!
        rc, qb = run_tool(ROOM_TOOL, "query", room_b, "--repo", repo_b,
                          "--adaptive", "--objective", "WILLTECH_ROOM_NO_FTS5 SQLite")
        self.assertEqual(rc, 0)
        self.assertNotIn("WILLTECH_ROOM_NO_FTS5", qb)
        # No SessionStart de B (validated_only), o finding candidate importado também NÃO entra
        mod_room = load_mod("wt_room_adv", ROOM_TOOL)
        self.assertIsNone(mod_room.query_text(
            room_b, repo=str(repo_b), objective="", validated_only=True, adaptive=True))

    def test_06_output_compaction_preserves_errors_stderr_and_verifies_raw_hash(self):
        passing = [f"test_case_{i:03d} (suite.TestOk) ... ok" for i in range(120)]
        repeated = ["info: cache slot verificado"] * 30
        failure = [
            "======================================================================",
            "FAIL: test_edge_nan (suite.TestCalc)",
            "Traceback (most recent call last):",
            '  File "tests/test_calc.py", line 42, in test_edge_nan',
            "    AssertionError: NaN nao tratado no limite superior",
            "",
        ]
        raw_stdout = "\n".join(passing + repeated + failure) + "\n"
        raw_stderr = "WARNING: stderr diagnostico critico linha 1\nERROR: stderr falha real linha 2\n"

        in_f = Path(self.tmp.name) / "stdout.txt"
        err_f = Path(self.tmp.name) / "stderr.txt"
        in_f.write_text(raw_stdout, encoding="utf-8")
        err_f.write_text(raw_stderr, encoding="utf-8")

        rc, summary = run_tool(
            OUTPUT_TOOL, "summarize", in_f, "--stderr-file", err_f,
            "--exit-code", "1", "--category", "test", "--repo", self.repo)
        self.assertEqual(rc, 0, summary)
        self.assertLess(len(summary), len(raw_stdout) // 2)
        self.assertIn("status=ERROR_DETECTED", summary)
        self.assertIn("CHECKS_OK: 120", summary)
        self.assertIn("[repetido x30]", summary)
        # Nenhum erro, stacktrace ou linha de stderr foi omitido!
        self.assertIn("STDERR (integral):", summary)
        self.assertIn("ERROR: stderr falha real linha 2", summary)
        self.assertIn("Traceback (most recent call last):", summary)
        self.assertIn("AssertionError: NaN nao tratado no limite superior", summary)

        # Extrai caminho e SHA-256 do log bruto e recupera 100% sem perda para Testador/Revisor
        raw_line = [l for l in summary.splitlines() if l.startswith("RAW_LOG:")][0]
        parts = dict(tok.split("=", 1) for tok in raw_line.replace("RAW_LOG:", "").split())
        rc, recovered = run_tool(
            OUTPUT_TOOL, "read-log", parts["path"],
            "--expected-sha256", parts["evidence_hash"], "--repo", self.repo)
        self.assertEqual(rc, 0)
        self.assertIn("test_case_000", recovered)
        self.assertIn("test_case_119", recovered)
        self.assertIn("AssertionError: NaN nao tratado", recovered)

        # Adulteração de 1 byte no log bruto -> hash divergente detectado (exit 2)
        log_file = self.repo / parts["path"]
        log_file.write_bytes(log_file.read_bytes() + b" ")
        rc, bad_out = run_tool(
            OUTPUT_TOOL, "read-log", parts["path"],
            "--expected-sha256", parts["evidence_hash"], "--repo", self.repo)
        self.assertEqual(rc, 2)
        self.assertIn("hash divergente", bad_out)

        # Anti-traversal e validação estrita de expected-sha256
        rc, trav_out = run_tool(
            OUTPUT_TOOL, "read-log", "src/calc.py",
            "--expected-sha256", parts["evidence_hash"], "--repo", self.repo)
        self.assertEqual(rc, 2)
        self.assertIn("fora do diretorio .willtech/logs", trav_out)

        rc, short_h = run_tool(
            OUTPUT_TOOL, "read-log", parts["path"],
            "--expected-sha256", "   ", "--repo", self.repo)
        self.assertEqual(rc, 2)
        self.assertIn("formato invalido", short_h)

        # Redação em persist_and_summarize e read-log
        # Se arquivo de entrada for caminho sensível (ex: secret.txt), deve recusar com rc=2
        cred_file = Path(self.tmp.name) / "secret_leak.txt"
        cred_file.write_text("token=123", encoding="utf-8")
        rc_cred, _ = run_tool(OUTPUT_TOOL, "summarize", cred_file, "--repo", self.repo)
        self.assertEqual(rc_cred, 2)

        secret_out = "dump: authorization: bearer sk-sec1234567890abcdef\nRuntimeError: falha encadeada\n"
        in_sec = Path(self.tmp.name) / "sample_out.txt"
        in_sec.write_text(secret_out, encoding="utf-8")
        rc, sec_sum = run_tool(
            OUTPUT_TOOL, "summarize", in_sec, "--repo", self.repo)
        self.assertEqual(rc, 0)
        self.assertNotIn("sk-sec1234567890abcdef", sec_sum)
        sec_raw_p = [l for l in sec_sum.splitlines() if l.startswith("RAW_LOG:")][0].split()[1].split("=")[1]
        log_disk = (self.repo / sec_raw_p).read_text(encoding="utf-8")
        self.assertNotIn("sk-sec1234567890abcdef", log_disk)
        rc, sec_read = run_tool(OUTPUT_TOOL, "read-log", sec_raw_p, "--repo", self.repo)
        self.assertEqual(rc, 0)
        self.assertNotIn("sk-sec1234567890abcdef", sec_read)
        self.assertTrue("<redacted>" in sec_read or "[REDACTED]" in sec_read)

    def test_07_adaptive_failure_falls_back_safely_to_canonical_30(self):
        run_tool(ROOM_TOOL, "put", self.room, "--repo", self.repo,
                 "--kind", "finding", "--specialty", "explorer",
                 "--summary", "ZZFALLBACK evidencia preservada no modo seguro",
                 "--path-ref", "src/calc.py")
        run_tool(ROOM_TOOL, "validate", self.room, "--repo", self.repo,
                 "--id", "1", "--by", "tester")
        mod_room = load_mod("wt_room_fb", ROOM_TOOL)
        orig_fn = mod_room.build_adaptive_query

        def broken_adaptive(*_a, **_kw):
            raise RuntimeError("falha simulada no motor adaptativo")

        mod_room.build_adaptive_query = broken_adaptive
        try:
            res = mod_room.query_text(self.room, repo=str(self.repo),
                                      objective="ZZFALLBACK", adaptive=True)
            self.assertIsNotNone(res, "fallback seguro deve recuperar pelo caminho 3.0 atual")
            self.assertIn("ZZFALLBACK evidencia preservada", res)
            self.assertIn("QUARENTENA", res)
        finally:
            mod_room.build_adaptive_query = orig_fn

    def test_08_seven_agents_tools_permissions_and_contracts_100_percent_intact(self):
        # Verifica os 7 contratos nas 3 plataformas + check-permissions oficial
        oc_agents = sorted((ROOT / "opencode" / "agent").glob("willtech-*.md"))
        cx_agents = sorted((ROOT / "codex" / "agents").glob("willtech-*.toml"))
        cc_agents = sorted((ROOT / "claude-code" / "agents").rglob("willtech-*.md"))
        self.assertEqual(len(oc_agents), 7)
        self.assertEqual(len(cx_agents), 7)
        self.assertEqual(len(cc_agents), 7)

        r = subprocess.run([sys.executable,
                            str(ROOT / "opencode" / "tests" / "check-permissions.py"),
                            str(ROOT / "opencode" / "agent")],
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

        base_ref = None
        for cand in ("origin/main", "main", "50b18d0406f6622b5e04bb9ee8dc62a4e2ee6d48", "v3.0.0"):
            chk = subprocess.run(
                ["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", cand],
                capture_output=True, text=True)
            if chk.returncode == 0:
                base_ref = cand
                break
        self.assertIsNotNone(base_ref, "nenhuma ref git base encontrada")
        diff = subprocess.check_output(
            ["git", "-C", str(ROOT), "diff", "--name-only", base_ref, "--",
             "opencode/agent", "opencode/AGENTS.md", "opencode/bin",
             "codex/agents", "claude-code/agents", "claude-code/settings"],
            text=True)
        self.assertEqual(diff.strip(), "", f"contratos/permissões alterados: {diff}")

    def test_09_no_fts5_concurrency_and_backup_restore_with_adaptive_attrs(self):
        env_no_fts = {"WILLTECH_ROOM_NO_FTS5": "1", "WILLTECH_ADAPTIVE_JIT": "1"}
        repo_nf = make_lab_repo(self.tmp.name, "proj-nofts")
        room_nf = str(repo_nf / ".willtech" / "room.db")
        rc, out = run_tool(ROOM_TOOL, "init", room_nf, "--repo", repo_nf, env=env_no_fts)
        self.assertEqual(rc, 0, out)

        procs = [subprocess.Popen(
            [sys.executable, str(ROOM_TOOL), "put", room_nf, "--repo", str(repo_nf),
             "--kind", "finding", "--specialty", "explorer",
             "--summary", f"calcular_desconto concorrente item {i}",
             "--path-ref", "src/calc.py"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={**os.environ, **env_no_fts})
            for i in range(6)]
        for p in procs:
            o, e = p.communicate(timeout=30)
            self.assertEqual(p.returncode, 0, o + e)

        run_tool(ROOM_TOOL, "validate", room_nf, "--repo", repo_nf,
                 "--id", "1", "--by", "tester", env=env_no_fts)
        rc, q_nf = run_tool(ROOM_TOOL, "query", room_nf, "--repo", repo_nf,
                            "--adaptive", "--objective", "calcular_desconto item 0",
                            env=env_no_fts)
        self.assertEqual(rc, 0, q_nf)
        self.assertIn("calcular_desconto", q_nf)

        # Backup + restore preserva integridade e metadados hit_count
        bak = str(Path(self.tmp.name) / "nf.bak")
        scon = sqlite3.connect(room_nf)
        dcon = sqlite3.connect(bak)
        scon.backup(dcon)
        dcon.close()
        scon.close()
        run_tool(ROOM_TOOL, "put", room_nf, "--repo", repo_nf,
                 "--kind", "risk", "--specialty", "reviewer",
                 "--summary", "registro temporario pos-backup",
                 "--evidence-hash", "1234abcd", env=env_no_fts)
        rc, rout = run_tool(ROOM_TOOL, "restore", room_nf, "--repo", repo_nf,
                            "--from", bak, env=env_no_fts)
        self.assertEqual(rc, 0, rout)
        rc, full1 = run_tool(ROOM_TOOL, "get", room_nf, "--repo", repo_nf,
                             "--id", "1", "--full", env=env_no_fts)
        self.assertEqual(rc, 0, full1)
        self.assertIn('"hit_count": 1', full1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil
