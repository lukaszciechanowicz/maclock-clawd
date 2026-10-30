# Assistant hooks

[Back to README](../README.md) · [API cookbook](api.md) · [Animation gallery](gallery.md) · [Raspberry Pi administration](raspberry-pi.md)

Separate, **opt-in** integrations for [Claude Code](#claude-code), [Codex CLI](#codex) and [OMP](#omp). Nothing here installs hooks or edits your assistant settings automatically. Review the examples before merging them; do not replace an existing configuration wholesale.

## Shared setup and Finished selection

All recommended examples use [`examples/pipclock_hook.py`](../examples/pipclock_hook.py), a Python 3 standard-library command adapter. It posts **only** `{"event":"…"}` to `/api/event`: no prompts, tool arguments, paths, session IDs, transcripts, model output or error text leave the assistant host. Claude/Codex supply their full hook input locally on stdin; the adapter reads only the event-name field for mapping and does not forward the input.

From the repository root, in the shell that will launch the assistant:

```sh
# Existing private file on this Mac; use your service's matching token elsewhere.
source "$HOME/Library/Application Support/maclock-clawd/api.env"
export PIPCLOCK_TOKEN
export PIPCLOCK_URL='http://maclock.internal.krosno.cloud:8765'
export PIPCLOCK_HOOK_SCRIPT="$PWD/examples/pipclock_hook.py"
export PIPCLOCK_FINISHED=dance
```

`PIPCLOCK_HOOK_SCRIPT` must be an absolute path to your reviewed checkout; do not move/delete it while hooks use it. `python3` must be on the launching process's `PATH`. GUI/IDE-launched assistants need these variables in **their** environment, not merely in another terminal. Never paste the token into JSON/TOML, command arguments, chat, screenshots or committed files; do not use shell tracing (`set -x`). Existing server configuration remains unchanged.

The default completion reaction really is `dance` (12 seconds), not a label attached to `thinking`. Select another member of the gallery's [Finished group](gallery.md#finished) before launching:

```sh
export PIPCLOCK_FINISHED=wave   # a wave, 8 seconds
# Or: export PIPCLOCK_FINISHED=pool   # chilling, 12 seconds
```

Allowed Finished values: `wave`, `bounce`, `dance`, `dancing_happy`, `jumping_happy`, `breakdancing`, `confetti`, `confetti_happy`, `excited`, `pool`, `meditating`. An invalid value skips completion rather than selecting a non-Finished action. Unset `PIPCLOCK_FINISHED` to restore `dance`. Durations come from existing API defaults; no new endpoint or server configuration is required.

The adapter has a two-second wall deadline (including stdin, DNS and HTTP), no retries, no proxy-environment routing and no redirects that could forward the bearer token. It fails open silently for missing tokens, malformed input, auth/network/HTTP errors and unknown events. It prints no permission/continuation decisions; Codex mode emits only `{}` to satisfy its JSON-output contract. A successful command exit therefore **does not prove delivery**. Hook runners allow three seconds for process startup; OMP's child-process cap is 2.5 seconds. These examples target **macOS/Linux** because the wall deadline uses POSIX `SIGALRM`; Windows needs a separately reviewed equivalent, not a claim that a socket timeout bounds DNS.

### Connection and host limitations

`maclock.internal.krosno.cloud` must resolve to the display server from the **assistant host**. This Mac's resolver did not resolve it during setup; arrange LAN DNS or a hosts entry yourself. No DNS, TLS or reverse-proxy changes are installed here. The existing native Pi service accepts authenticated trusted-LAN traffic; ordinary API calls need no SSH tunnel. Port `8765` is explicit.

Plain HTTP exposes the bearer token on the network even with event-only payloads. Use it only on a trusted LAN; never expose port 8765 to the Internet. For encrypted Mac-to-Pi access, keep/use a loopback-bound endpoint and open a tunnel with a provisioned SSH login:

```sh
ssh -i "$HOME/.ssh/omp_tmp_raspbery" -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8765:127.0.0.1:8765 lukasz@maclock.internal.krosno.cloud
```

In the assistant's launching shell, set `PIPCLOCK_URL=http://127.0.0.1:8765`. Do not also run a Mac preview on that port. The same bearer token is required at both ends. A separate SSH account can forward to Pi loopback; the display service account need not have SSH access. Remote/cloud assistants cannot necessarily reach this private LAN or read this checkout; run the integration where those prerequisites actually exist. See [Pi operations](raspberry-pi.md); do not start a second display process to configure hooks.

## Activity and event mapping

These are observational activity signals, **not** proof of successful work or token-level analysis. `thinking` lasts 300 seconds and is refreshed by the listed activity events; a long inference or tool can outlast that watchdog. There is no separate inference-start/analysis-stream callback in these examples, and no prompt or reasoning inspection.

| Activity | Clawd | Claude Code command hooks | Codex CLI 0.164.0 lifecycle hooks | OMP 18.12.1 extension |
| --- | --- | --- | --- | --- |
| Session starts/resumes | `wave` (8 s) | `SessionStart` | `SessionStart` | `session_start` (initial load) |
| Prompt accepted / work begins | `thinking` (300 s) | `UserPromptSubmit` | `UserPromptSubmit` | `before_agent_start` |
| Analysis / next model-loop iteration | `thinking` watchdog, not live reasoning | No separate callback configured | No separate callback configured | `turn_start`, not token-level thinking |
| Tool starts / succeeds | `thinking` (300 s) | `PreToolUse`, `PostToolUse` | `PreToolUse`, `PostToolUse` | `tool_call`, successful `tool_result` |
| Permission/input needed | `waiting` (60 s) | `PermissionRequest`, all `Notification` types | `PermissionRequest` | `tool_approval_requested` |
| Approval dialog resolves | resume `thinking` | Next lifecycle/tool signal | Next lifecycle/tool signal | `tool_approval_resolved` (does not imply approval) |
| Tool/API error | `knock` (8 s) | `PostToolUseFailure`, `StopFailure` | No dedicated failure event in this example; `PostToolUse` also fires on nonzero Bash exit and stays `thinking` | `tool_result.isError`, `auto_retry_start`; final assistant `stopReason: error` |
| Response/work loop finishes | configurable Finished, default `dance` | `Stop` | `Stop` | settled `agent_end`, unless error/abort |
| Interrupt / abort | `idle` when signalled | No interrupt hook configured | `Interrupt` | final assistant `stopReason: aborted` |
| Session ends | `idle` | `SessionEnd` | `SessionEnd` | `session_shutdown` |

A finish signal means a response/loop stopped, not that tests passed or the user's whole project is done. Other hooks may request another continuation after a Stop callback. The next activity event will replace the finish animation. Session shutdown also replaces it with `idle`: for a visible completion celebration, leave the interactive session open rather than immediately exiting a one-shot session.

The server is last-accepted-event-wins; independent sessions can overwrite each other, and one ending can clear another's display. Claude/Codex hooks can also run for subagent tool activity. OMP explicitly ignores subagent/advisor contexts and ignores `agent_end` with `willContinue` or `awaitingAsyncWork`; background waits are not falsely celebrated as finished. No ownership reconstruction or keepalive service is installed.

## Claude Code

Use [`examples/claude-hooks.json`](../examples/claude-hooks.json). It configures real command hooks for every Claude event in the table, with a three-second runner timeout and the shared adapter's two-second deadline. The Claude CLI is not installed on this host; event/configuration names come from the [official hooks reference](https://code.claude.com/docs/en/hooks), not a locally exercised Claude session.

1. Complete the shared launch environment above.
2. Review the JSON and merge its per-event matcher groups into your chosen settings file: `.claude/settings.local.json` for private project settings, `.claude/settings.json` for shared project settings, or `~/.claude/settings.json` for user scope. Preserve all other settings and existing `hooks` entries; append these groups rather than overwriting arrays. Configure one copy, not all three scopes.
3. Launch `claude` from that environment. Review `/hooks` and restart/review changes as directed by Claude's hooks documentation. Managed `allowManagedHooksOnly` policy can prevent local hooks.
4. Submit a small prompt. While processing, Clawd thinks; after `Stop`, it performs the selected Finished action. Permission hooks only show status: they never approve/deny a request.

To opt out, remove only the added matcher groups from the file you chose, preserving other hooks, then restart/review the session. For a temporary display-only opt-out, export `PIPCLOCK_HOOKS_DISABLED=1` **before** launching; unset it to re-enable. Disabling these notifications does not change Claude permissions.

### Optional native Claude HTTP endpoint

The existing `/hooks/claude` endpoint and its mapping remain supported. [`examples/claude-http-hooks.json`](../examples/claude-http-hooks.json) is an **alternative**, not something to install alongside the recommended command hooks. It uses real HTTP hooks with `timeout: 2`, `Authorization: Bearer ${PIPCLOCK_TOKEN}` and `allowedEnvVars: ["PIPCLOCK_TOKEN"]`. Organization HTTP URL/environment allowlists may need to permit the endpoint and variable. For a tunnel, manually change its URLs to `http://127.0.0.1:8765/hooks/claude`.

Unlike the recommended command adapter, native HTTP hooks transmit Claude's **complete** payload, potentially including prompts, arguments and paths, even though this server uses only `hook_event_name`. The 16 KiB request limit may reject large payloads. Use only after reviewing that privacy difference. Native mapping is unchanged: `SessionStart → wave`, `UserPromptSubmit/PreToolUse/PostToolUse → thinking`, `Stop → bounce` (a Finished member, 8 seconds), `Notification/PermissionRequest → waiting`, `PostToolUseFailure/StopFailure → knock`, `SessionEnd → idle`. `PIPCLOCK_FINISHED` does **not** customize the native endpoint; use the command adapter for configurable completion.

## Codex

This setup targets the **installed Codex CLI 0.164.0**, whose real lifecycle-hook surface is broader than the older completion-only notification interface. Check `codex --version`; if your release lacks these events, `features.hooks` or `/hooks`, upgrade before using this configuration. Do not invent Claude event names in Codex or assume an older `notify` command sees tools/permissions. This guide uses one lifecycle-hook path, not a parallel notification fallback.

Primary references: [Codex Hooks](https://developers.openai.com/codex/hooks), [advanced configuration](https://developers.openai.com/codex/config-advanced#hooks), [configuration reference](https://developers.openai.com/codex/config-reference), and [generated hook schemas](https://github.com/openai/codex/tree/main/codex-rs/hooks/schema/generated). Release documentation is the behavior reference; `main` schemas may be newer than the installed binary.

1. Complete the shared launch environment.
2. Review [`examples/codex-hooks.json`](../examples/codex-hooks.json). Merge its event groups into **one** `hooks.json` next to an active Codex config layer: `~/.codex/hooks.json` (or `$CODEX_HOME/hooks.json`) for user scope, or `<repo>/.codex/hooks.json` for a trusted project. Preserve existing groups. Inline `[hooks]` in the adjacent `config.toml` is also supported, but do not configure the same integration both inline and in JSON. Both sources would load.
3. Enable the lifecycle feature for the launch:

   ```sh
   codex --enable hooks
   ```

   For persistent opt-in, merge `hooks = true` into the **existing** `[features]` table in the chosen `config.toml`; do not add a duplicate table or replace other feature flags. User config is `~/.codex/config.toml` / `$CODEX_HOME/config.toml`; trusted project config is `.codex/config.toml`.
4. Open `/hooks` in Codex, review and trust the exact added definitions. Changed definitions require renewed review. Project-local hooks also require project trust; managed-only policy can block them. Do not use the dangerous hook-trust bypass flag just to skip review.
5. Submit a prompt and leave the interactive session open after the response to see `Stop → dance` (or your selected Finished action).

Supported events configured here: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `Stop`, `Interrupt`, `SessionEnd`. **No** `Notification`, `PostToolUseFailure` or `StopFailure` is invented. Post-tool callbacks include failed Bash commands, so the event name alone cannot honestly distinguish success/failure. Hosted tools such as web search do not use the local function-tool hook path; specialized paths can also opt out. There is no claim of complete tool visibility or live analysis detection. Codex using a model inside OMP instead follows OMP's event surface below, not these CLI hooks.

To opt out, remove/disable only the added definitions in `/hooks` or their source file and restart; preserve unrelated hooks and feature flags. Alternatively launch with `PIPCLOCK_HOOKS_DISABLED=1` to suppress only these display requests. Removing `--enable hooks` alone is not an opt-out if another configuration layer already enables the feature.

## OMP

This setup targets the installed **OMP 18.12.1**. New hooks use `ExtensionAPI`: current OMP loads TS/JS hook factories through the extension runner, and `--hook` aliases `--extension`. [`examples/omp-hooks.ts`](../examples/omp-hooks.ts) is an observational extension, not a legacy standalone `HookRunner` integration. It calls the same adjacent Python adapter with static action names, never prompt/tool content.

Reviewed primary docs: [Hooks](https://github.com/can1357/oh-my-pi/blob/main/packages/coding-agent/docs/hooks.md), [Authoring hooks](https://github.com/can1357/oh-my-pi/blob/main/packages/coding-agent/docs/skills/authoring-hooks.md), [Extensions](https://github.com/can1357/oh-my-pi/blob/main/packages/coding-agent/docs/extensions.md), [Extension loading](https://github.com/can1357/oh-my-pi/blob/main/packages/coding-agent/docs/extension-loading.md), and [shared event types](https://github.com/can1357/oh-my-pi/blob/main/packages/coding-agent/src/extensibility/shared-events.ts). The installed documentation is also available within OMP as `omp://hooks.md`, `omp://skills/authoring-hooks.md`, `omp://extensions.md` and `omp://extension-loading.md`.

After exporting the shared environment, the simplest opt-in needs **no config edits**:

```sh
# From this repository root; keep omp-hooks.ts beside pipclock_hook.py.
omp --extension "$PWD/examples/omp-hooks.ts"
```

For persistent use, merge the absolute extension path into the existing `extensions:` array in project `.omp/config.yml` or user `~/.omp/agent/config.yml` (`config.yaml` is the fallback). Preserve every other configured extension: OMP settings layers **replace arrays**, not concatenate them. Named profiles use `~/.omp/profiles/<name>/agent/`; agent-directory overrides follow OMP's profile rules. Alternatively, native discovery scans `.omp/extensions/` and `~/.omp/agent/extensions/`. If relocating this example, keep its adjacent Python adapter with it; adding only the TS file breaks its relative adapter lookup.

Native hook-directory discovery specifically requires `.omp/hooks/pre/*.ts` or `.omp/hooks/post/*.ts` (and corresponding user locations); a file directly in `.omp/hooks/` is **not** discovered. The `pre`/`post` directory does not register events automatically: the factory must call `pi.on(...)`. Use a single loading method to avoid duplicate notifications.

The example maps actual lifecycle/tool/approval/error events as listed above. Approval events fire only when a tool needs approval **and an approval handler is registered**; auto-approved tools do not create waiting status. Eval prelude/host bridge calls are not necessarily AgentTool calls. `before_agent_start` covers prompt preparation, including dequeued user work; `input` is deliberately not used because its ingress coverage excludes print/ACP/programmatic work. `turn_start` is a loop boundary, not a reasoning-token detector. No handler mutates context, tool input/output, permissions or continuation decisions. OMP extensions are unsandboxed host code, so review before loading.

To opt out, omit `--extension` on the next launch, or remove only the added configured path/discovered files and restart. `--no-extensions` disables ambient discovery **but explicit `--extension` / `--hook` paths still load**. `PIPCLOCK_HOOKS_DISABLED=1` suppresses this adapter without disabling other extensions.

## Manual smoke commands

Run these **after** loading the shared environment and arranging name resolution/server access. They do not install hooks, invoke a model, or transmit any real assistant content:

```sh
# Direct adapter interface (no stdin): greeting, watchdog, waiting, error, completion.
python3 "$PIPCLOCK_HOOK_SCRIPT" action start
python3 "$PIPCLOCK_HOOK_SCRIPT" action work
python3 "$PIPCLOCK_HOOK_SCRIPT" action waiting
python3 "$PIPCLOCK_HOOK_SCRIPT" action error
python3 "$PIPCLOCK_HOOK_SCRIPT" action finish

# Real Claude/Codex wire field, synthetic local payload; each should show Finished.
printf '%s\n' '{"hook_event_name":"Stop"}' | python3 "$PIPCLOCK_HOOK_SCRIPT" claude
printf '%s\n' '{"hook_event_name":"Stop"}' | python3 "$PIPCLOCK_HOOK_SCRIPT" codex

# One-command alternate completion; does not change the shell's selection.
printf '%s\n' '{"hook_event_name":"Stop"}' | PIPCLOCK_FINISHED=pool python3 "$PIPCLOCK_HOOK_SCRIPT" codex

# Confirm the selected event through the authenticated API; adapter exit 0 is not delivery proof.
curl -q --fail-with-body --silent --show-error --max-time 3 \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN" "$PIPCLOCK_URL/api/state"

# Opt-out should produce no display update and still exit 0.
PIPCLOCK_HOOKS_DISABLED=1 python3 "$PIPCLOCK_HOOK_SCRIPT" action finish

# Explicit reset (run only after observing the Finished action).
python3 "$PIPCLOCK_HOOK_SCRIPT" action idle
```

For payload-privacy, Finished selection, redirect/auth failure and bounded-time behavior tests, run from the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_hook_adapter.py'
```

Assistant-level smoke: launch each configured interactive CLI with the environment above, submit a short prompt, approve nothing just for this test, and observe its actual lifecycle callbacks. Claude requires installation on the caller host. A manual synthetic adapter POST is not evidence that a CLI has loaded/trusted its configuration.

## Verification boundaries

The integrated suite passed **98 tests**, including real local HTTP checks for event-only payload privacy, Finished eligibility, redirect refusal, authentication failure and the bounded observational deadline. The documented Claude/Codex command strings were also executed against the native Pi API: session start, work, waiting, error, default `dance`, selected `pool` and reset-to-idle behavior were observed.

The installed Codex 0.164.0 accepted the lifecycle feature/configuration in an isolated `CODEX_HOME`. Its interactive hook trust and a real Codex prompt were not exercised, and Claude Code is not installed on this workstation. An actual isolated OMP RPC process loaded `omp-hooks.ts`: after its initialized `get_state` startup barrier, `session_start` showed `wave`, and clean EOF shutdown showed `idle`, without extension errors or a model request. The blank smoke profile needed an explicit model selection; ordinary use assumes OMP already has its normal model configured. No real user hook settings were installed or changed.
