# Claude Code integration

[Back to README](../README.md) · [API](api.md)

[`examples/claude-hooks.json`](../examples/claude-hooks.json) follows the current official [Claude Code hooks reference](https://code.claude.com/docs/en/hooks): HTTP handlers with `timeout: 2`, an Authorization header interpolated from `${PIPCLOCK_TOKEN}`, and `allowedEnvVars: ["PIPCLOCK_TOKEN"]`. It includes every mapped event:

| Claude event | Clawd reaction |
| --- | --- |
| `SessionStart` | `wave`, 8 seconds |
| `UserPromptSubmit`, `PreToolUse`, `PostToolUse` | `thinking`, 300 seconds |
| `Stop` | `bounce`, 8 seconds |
| `Notification`, `PermissionRequest` | `waiting`, 60 seconds |
| `PostToolUseFailure`, `StopFailure` | `knock`, 8 seconds |
| `SessionEnd` | `idle` |

No active hooks are installed by this repository. To opt in, review the example and merge its `hooks` entries into your chosen Claude settings file (for example `.claude/settings.local.json`), preserving existing settings and hooks. Export the same `PIPCLOCK_TOKEN` before starting Claude Code and the companion server. Restart/review Claude's hook configuration as directed by its documentation. Organization HTTP URL/environment allowlists may also need to permit this endpoint and variable. Remove only these entries to opt out.

The example posts real Claude payloads. The app ignores prompt text, tool arguments, transcripts and paths and uses only the event name; nevertheless Claude sends the complete payload over the connection. Do not send it to an untrusted endpoint. The 16 KiB limit can reject large real tool payloads: such notifications will not update the display. Hooks return no permission decisions; a waiting animation does not approve anything. Hook failures are observational, not a security control.

`thinking` is a 300-second watchdog refreshed by lifecycle/tool activity, **not** token-level inference or proof that Claude is still working. Events from multiple sessions/subagents compete: the most recent accepted event wins, and a session ending can clear another session's status. No attempt is made to reconstruct task ownership.

## Recommended Mac-to-Pi connection: SSH tunnel

Keep the Pi server bound to loopback. On the Mac running Claude, open this tunnel (replace `pipclock@raspberrypi.local` with your provisioned SSH login/host):

```sh
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8765:127.0.0.1:8765 pipclock@raspberrypi.local
```

The example hook URL remains `http://127.0.0.1:8765/hooks/claude`. Do not also run the Mac preview on that port. The tunnel encrypts traffic; use the same bearer token at both ends. The service account need not allow SSH: a separate provisioned SSH account can forward to Pi loopback.

## Existing trusted-LAN Pi deployment

The current native Pi service already accepts authenticated LAN requests. Ordinary API requests and hooks need no SSH tunnel. On this Mac, load the existing private token before starting Claude Code:

```sh
source "$HOME/Library/Application Support/maclock-clawd/api.env"
export PIPCLOCK_TOKEN
```

In your reviewed copy of the hook settings, change each HTTP hook URL to `http://192.168.1.57:8765/hooks/claude`; retain its bearer header and `allowedEnvVars`. The example's loopback URL is suitable for the tunnel instead, not direct LAN access. Do not generate a different client token: it must match the service's configured token.

Plain HTTP does not encrypt the token or complete Claude payloads. Use direct access only on a trusted LAN; prefer the encrypted tunnel on untrusted networks, and never expose port 8765 to the Internet. Preview cannot be enabled on a non-loopback bind.

See the [API cookbook](api.md#client-setup-on-this-mac) for direct requests and [Raspberry Pi administration](raspberry-pi.md) for native service configuration. Do not start a second display process to configure the installed service.
