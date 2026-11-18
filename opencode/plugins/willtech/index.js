// WillTech-General 2.2 — automação nativa OpenCode V2 (plugin de projeto).
// Descoberto automaticamente em .opencode/plugins/ após instalação.
// Chama o núcleo determinístico tools/willtech-auto.py via python3/python/py:
// zero chamadas de modelo. Auxiliares falham aberto; a guarda de loop bloqueia
// via throw no execute.before (contrato V2). Desativação: remover
// .willtech/enabled (núcleo vira no-op) ou willtech-install.sh --uninstall.
// V1 não executa em V2: este plugin é exclusivamente V2 (export default com
// id + setup, sem dependência de @opencode/plugin).
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const TIMEOUT_MS = 8000;
const BUFFER_CAP = 1 << 20;

// python3 (Unix) ou python/py -3 (Windows): primeiro que responder, em cache.
let PY = null;
function pythonCmd() {
  if (PY) return PY;
  for (const cand of [["python3", []], ["python", []], ["py", ["-3"]]]) {
    try {
      const r = spawnSync(cand[0], [...cand[1], "--version"], {
        timeout: 3000, encoding: "utf8", windowsHide: true,
      });
      if (r.status === 0) { PY = cand; return PY; }
    } catch {}
  }
  return null;
}

function core(dir, event) {
  const tool = join(dir, "tools", "willtech-auto.py");
  if (!existsSync(tool)) return {};
  const py = pythonCmd();
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