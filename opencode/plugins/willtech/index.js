// WillTech-General 2.2 — automação nativa OpenCode V2 (plugin de projeto).
// Descoberto automaticamente em .opencode/plugins/ após instalação.
// Chama o núcleo determinístico tools/willtech-auto.py via python3/python/py:
// zero chamadas de modelo. Auxiliares falham aberto; a guarda de loop bloqueia
// via throw no execute.before (contrato V2). Desativação: remover
// .willtech/enabled (núcleo vira no-op) ou willtech-install.sh --uninstall.
// V1 não executa em V2: este plugin é exclusivamente V2 (export default com
// id + setup, sem dependência de @opencode/plugin).
import { spawnSync } from "node:child_process";
import { existsSync, statSync, readFileSync, readdirSync } from "node:fs";
import { join, dirname, basename } from "node:path";
import { homedir } from "node:os";

const TIMEOUT_MS = 8000;
const BUFFER_CAP = 1 << 20;

// Localiza interpretador Python >= 3.12 compatível de forma determinística e resiliente:
// 1. Em cache na memória do processo (PY).
// 2. Variável de ambiente explícita WILLTECH_PYTHON ou PYTHON.
// 3. Configuração gravada na instalação do projeto (.willtech/installed.json -> campo "python").
// 4. Candidatos por plataforma (Windows, macOS, Linux):
//    - Windows: py -3.12, py -3.13, py -3, python3, python, caminhos de Program Files e LocalAppData
//    - macOS / Linux: python3.12, python3.13, Homebrew (/opt/homebrew/bin, /usr/local/bin),
//      ~/.local/bin/python3.12, instalações do uv em ~/.local/share/uv/python/*/bin/python3,
//      pyenv (~/.pyenv/shims/python3), Frameworks oficiais e fallbacks no PATH.
// Validação estrita: executa -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)".
// Se a versão for inferior a 3.12 (ex.: /usr/bin/python3 3.9.6 do macOS), é rejeitada sem erro.
let PY = null;
function pythonCmd(dir) {
  if (PY) return PY;

  const testCompat = (cmd, args = []) => {
    try {
      if (typeof cmd === "string" && cmd.startsWith("/") && !existsSync(cmd)) return false;
      const r = spawnSync(cmd, [...args, "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"], {
        timeout: 2500, windowsHide: true,
      });
      return r.status === 0;
    } catch {
      return false;
    }
  };

  // 1. Variável de ambiente explícita
  const envPy = process.env.WILLTECH_PYTHON || process.env.PYTHON;
  if (envPy && testCompat(envPy)) {
    PY = [envPy, []];
    return PY;
  }

  // 2. Configuração persistida na instalação local do projeto
  if (dir) {
    try {
      const instPath = join(dir, ".willtech", "installed.json");
      if (existsSync(instPath)) {
        const data = JSON.parse(readFileSync(instPath, "utf8"));
        if (data && data.python && testCompat(data.python)) {
          PY = [data.python, []];
          return PY;
        }
      }
    } catch {}
  }

  // 3. Candidatos do sistema operacional
  const isWin = process.platform === "win32";
  const isMac = process.platform === "darwin";
  const home = typeof homedir === "function" ? homedir() : (process.env.HOME || process.env.USERPROFILE || "");
  const candidates = [];

  if (isWin) {
    candidates.push(["py", ["-3.12"]]);
    candidates.push(["py", ["-3.13"]]);
    candidates.push(["py", ["-3"]]);
    candidates.push(["python3", []]);
    candidates.push(["python", []]);
    const localApp = process.env.LOCALAPPDATA || (home ? join(home, "AppData", "Local") : "");
    if (localApp) {
      candidates.push([join(localApp, "Programs", "Python", "Python312", "python.exe"), []]);
      candidates.push([join(localApp, "Programs", "Python", "Python313", "python.exe"), []]);
    }
    const progFiles = process.env.ProgramFiles;
    if (progFiles) {
      candidates.push([join(progFiles, "Python312", "python.exe"), []]);
      candidates.push([join(progFiles, "Python313", "python.exe"), []]);
    }
  } else {
    // Comandos explícitos no PATH
    candidates.push(["python3.12", []]);
    candidates.push(["python3.13", []]);

    if (isMac) {
      // Homebrew Apple Silicon
      candidates.push(["/opt/homebrew/bin/python3.12", []]);
      candidates.push(["/opt/homebrew/bin/python3.13", []]);
      candidates.push(["/opt/homebrew/bin/python3", []]);
      // Homebrew Intel / python.org
      candidates.push(["/usr/local/bin/python3.12", []]);
      candidates.push(["/usr/local/bin/python3.13", []]);
      candidates.push(["/usr/local/bin/python3", []]);
      // Python.framework oficial
      candidates.push(["/Library/Frameworks/Python.framework/Versions/3.12/bin/python3", []]);
      candidates.push(["/Library/Frameworks/Python.framework/Versions/3.13/bin/python3", []]);
    } else {
      // Linux
      candidates.push(["/usr/bin/python3.12", []]);
      candidates.push(["/usr/bin/python3.13", []]);
      candidates.push(["/usr/local/bin/python3.12", []]);
      candidates.push(["/usr/local/bin/python3.13", []]);
    }

    // Gerenciadores no diretório home do usuário
    if (home) {
      candidates.push([join(home, ".local", "bin", "python3.12"), []]);
      candidates.push([join(home, ".local", "bin", "python3.13"), []]);
      candidates.push([join(home, ".local", "bin", "python3"), []]);

      // Detecta versões instaladas pelo uv em ~/.local/share/uv/python/*/bin/python3
      const uvBase = join(home, ".local", "share", "uv", "python");
      if (existsSync(uvBase)) {
        try {
          for (const ent of readdirSync(uvBase)) {
            const p = join(uvBase, ent, "bin", "python3");
            if (existsSync(p)) candidates.push([p, []]);
          }
        } catch {}
      }

      candidates.push([join(home, ".pyenv", "shims", "python3"), []]);
      candidates.push([join(home, ".asdf", "shims", "python3"), []]);
    }

    // Fallbacks genéricos no PATH (serão validados se >= 3.12)
    candidates.push(["python3", []]);
    candidates.push(["python", []]);
  }

  for (const cand of candidates) {
    if (testCompat(cand[0], cand[1])) {
      PY = cand;
      return PY;
    }
  }

  return null;
}

function core(dir, event) {
  const tool = join(dir, "tools", "willtech-auto.py");
  if (!existsSync(tool)) return {};
  const py = pythonCmd(dir);
  if (!py) return {};
  try {
    const r = spawnSync(py[0], [...py[1], tool, "opencode"], {
      input: JSON.stringify(event),
      timeout: TIMEOUT_MS,
      maxBuffer: BUFFER_CAP,
      encoding: "utf8",
      windowsHide: true,
    });
    if (r.status !== 0 || !r.stdout) return {};
    const d = JSON.parse(r.stdout);
    return d && typeof d === "object" ? d : {};
  } catch {
    return {};
  }
}

export default {
  id: "willtech-general",
  async setup(ctx) {
    const dir = ctx.location.directory;
    core(dir, { hook_event_name: "SessionStart", session_id: "plugin-load", cwd: dir });

    await ctx.tool.hook("execute.before", (ev) => {
      // Normalização protetiva e segura para ferramentas de busca e leitura:
      // Se o modelo invocar grep passando caminho de arquivo regular existente em `path`,
      // o OpenCode v2.3.0 rejeita com "Search path does not exist: <file>" pois espera diretório.
      // Normalizamos para buscar no diretório pai filtrando pelo arquivo correspondente.
      if (ev.tool === "grep" && ev.input && typeof ev.input.path === "string") {
        try {
          const rawP = ev.input.path.trim();
          const fullP = join(dir, rawP);
          if (existsSync(fullP) && statSync(fullP).isFile()) {
            const dirPart = dirname(rawP);
            const basePart = basename(rawP);
            ev.input.path = (!dirPart || dirPart === ".") ? "." : dirPart;
            ev.input.include = basePart;
          }
        } catch {}
      } else if (ev.tool === "read" && ev.input) {
        if (!ev.input.filePath && ev.input.path) {
          ev.input.filePath = ev.input.path;
        }
      }

      if (ev.tool !== "bash") return;
      const d = core(dir, {
        hook_event_name: "PreToolUse",
        session_id: ev.sessionID,
        cwd: dir,
        tool_name: "Bash",
        tool_input: ev.input || ev.args || {},
      });
      if (d.block) {
        throw new Error(d.reason || "WillTech: comando bloqueado pela guarda de loop");
      }
    });

    await ctx.tool.hook("execute.after", (ev) => {
      const base = {
        session_id: ev.sessionID,
        cwd: dir,
        tool_input: ev.input || ev.args || {},
      };
      if (ev.tool === "bash") {
        const failed = ev.status === "error";
        core(dir, {
          ...base,
          hook_event_name: failed ? "PostToolUseFailure" : "PostToolUse",
          tool_name: "Bash",
          tool_response: failed ? undefined : ev.result,
          error: failed ? (ev.error && ev.error.message) || "tool error" : undefined,
        });
      } else if (ev.tool === "edit" || ev.tool === "write") {
        const inp = ev.input || ev.args || {};
        core(dir, {
          ...base,
          hook_event_name: "PostToolUse",
          tool_name: "Edit",
          tool_input: { file_path: inp.filePath || inp.file_path || "" },
        });
      }
    });

    // O hook "context" roda antes de CADA request ao modelo.
    // Modo padrão (fallback 3.0): injeta uma única vez via `pending`.
    // Modo adaptativo (WILLTECH_ADAPTIVE_JIT=1 ou .willtech/adaptive-jit): isola por sessionID e mantém o
    // mesmo bloco estável durante todos os turnos de ferramentas daquela sessão
    // até `session.idle`, evitando invalidar o cache de prefixo no turno 2+ e
    // preservando a evidência da Sala na etapa final de síntese.
    const envFlag = String(process.env.WILLTECH_ADAPTIVE_JIT || "").trim().toLowerCase();
    const markerFile = join(dir, ".willtech", "adaptive-jit");
    const adaptive = ["1", "true", "yes", "on"].includes(envFlag) || existsSync(markerFile);
    let pending = null;
    const sessionCtx = new Map();
    await ctx.session.hook("prompt", (ev) => {
      const sid = (ev && ev.sessionID) || "default";
      const d = core(dir, {
        hook_event_name: "UserPromptSubmit",
        session_id: sid,
        cwd: dir,
        prompt: (ev.prompt && ev.prompt.text) || "",
      });
      if (adaptive) {
        if (d.context) {
          if (sessionCtx.size >= 64 && !sessionCtx.has(sid)) {
            const oldest = sessionCtx.keys().next().value;
            sessionCtx.delete(oldest);
          }
          sessionCtx.set(sid, d.context);
        } else {
          sessionCtx.delete(sid);
        }
      } else if (d.context) {
        pending = d.context;
      }
    });
    await ctx.session.hook("context", (ev) => {
      if (adaptive) {
        const sid = (ev && ev.sessionID) || "default";
        const active = sessionCtx.get(sid);
        if (active) {
          ev.system.push({ type: "text", text: active });
        }
      } else if (pending) {
        ev.system.push({ type: "text", text: pending });
        pending = null;
      }
    });

    // session.idle é o equivalente a Stop no V2: não pode bloquear; o núcleo
    // registra pendências (revisão/drift) entregues no próximo prompt.
    const ctrl = new AbortController();
    void (async () => {
      try {
        for await (const e of ctx.event.subscribe({ signal: ctrl.signal })) {
          if (e.type === "session.idle") {
            const idleSid = (e.properties && e.properties.sessionID) || "idle";
            sessionCtx.delete(idleSid);
            core(dir, {
              hook_event_name: "Stop",
              session_id: idleSid,
              cwd: dir,
              stop_hook_active: false,
            });
          }
        }
      } catch {}
    })();
    return () => ctrl.abort();
  },
};

// WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil