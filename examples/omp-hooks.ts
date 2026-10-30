import { fileURLToPath } from "node:url";
import type { ExtensionAPI, ExtensionContext } from "@oh-my-pi/pi-coding-agent";

const adapter = fileURLToPath(new URL("./pipclock_hook.py", import.meta.url));

export default function (pi: ExtensionAPI): void {
  const send = async (action: string, ctx: ExtensionContext): Promise<void> => {
    // Factories also bind to task/advisor sessions; don't let children clear the display.
    if (ctx.agent.kind !== "main") return;
    try {
      await pi.exec("python3", [adapter, "action", action], { timeout: 2500 });
    } catch {
      // Observational only: never block tools or return assistant decisions.
    }
  };

  pi.on("session_start", (_event, ctx) => send("start", ctx));
  pi.on("before_agent_start", (_event, ctx) => send("work", ctx));
  pi.on("turn_start", (_event, ctx) => send("work", ctx));
  pi.on("tool_call", (_event, ctx) => send("work", ctx));
  pi.on("tool_result", (event, ctx) => send(event.isError ? "error" : "work", ctx));
  pi.on("tool_approval_requested", (_event, ctx) => send("waiting", ctx));
  pi.on("tool_approval_resolved", (_event, ctx) => send("work", ctx));
  pi.on("auto_retry_start", (_event, ctx) => send("error", ctx));
  pi.on("agent_end", async (event, ctx) => {
    if (event.willContinue || event.awaitingAsyncWork) return;
    const last = event.messages.findLast(message => message.role === "assistant");
    if (last?.role === "assistant" && last.stopReason === "error") {
      await send("error", ctx);
    } else if (last?.role === "assistant" && last.stopReason === "aborted") {
      await send("idle", ctx);
    } else {
      await send("finish", ctx);
    }
  });
  pi.on("session_shutdown", (_event, ctx) => send("idle", ctx));
}
