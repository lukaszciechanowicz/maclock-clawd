#!/usr/bin/env python3
"""Opt-in assistant display notifications; never return assistant decisions."""

import json
import os
import signal
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


FINISHED = frozenset((
    "wave", "bounce", "dance", "dancing_happy", "jumping_happy", "breakdancing",
    "confetti", "confetti_happy", "excited", "pool", "meditating",
))
ACTIONS = {
    "start": "wave", "work": "thinking", "waiting": "waiting",
    "error": "knock", "idle": "idle",
}
CLAUDE = {
    "SessionStart": "start", "UserPromptSubmit": "work", "PreToolUse": "work",
    "PostToolUse": "work", "Stop": "finish", "Notification": "waiting",
    "PermissionRequest": "waiting", "PostToolUseFailure": "error",
    "StopFailure": "error", "SessionEnd": "idle",
}
CODEX = {
    "SessionStart": "start", "UserPromptSubmit": "work", "PreToolUse": "work",
    "PostToolUse": "work", "PermissionRequest": "waiting", "Stop": "finish",
    "SessionEnd": "idle", "Interrupt": "idle",
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the bearer token to a redirect target.
        return None


def deadline(_signum, _frame):
    raise TimeoutError("notification deadline")


def action_for(mode, args, stream):
    if mode == "action":
        return args[0] if args else None
    if mode in ("claude", "codex"):
        payload = json.load(stream)
        return (CLAUDE if mode == "claude" else CODEX).get(payload.get("hook_event_name"))
    return None


def post_action(action):
    event = ACTIONS.get(action)
    if action == "finish":
        event = os.environ.get("PIPCLOCK_FINISHED", "dance")
        if event not in FINISHED:
            return
    token = os.environ.get("PIPCLOCK_TOKEN")
    if not event or not token or os.environ.get("PIPCLOCK_HOOKS_DISABLED") == "1":
        return
    base = os.environ.get("PIPCLOCK_URL", "http://maclock.internal.krosno.cloud:8765")
    url = urlsplit(base)
    if (url.scheme not in ("http", "https") or not url.hostname or url.username
            or url.password or url.path not in ("", "/") or url.query or url.fragment):
        return
    request = Request(
        base.rstrip("/") + "/api/event",
        data=json.dumps({"event": event}).encode("utf-8"),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST",
    )
    # Do not route credentials through ambient HTTP proxies or follow redirects.
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=2):
        pass


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    mode = args[0] if args else ""
    try:
        # These examples target macOS/Linux: the wall deadline also bounds DNS
        # and stdin reads, unlike a socket timeout alone.
        signal.signal(signal.SIGALRM, deadline)
        signal.setitimer(signal.ITIMER_REAL, 2)
        post_action(action_for(mode, args[1:], sys.stdin))
    except Exception:
        # Observational only: no secrets, payloads, errors or decisions on stderr.
        pass
    finally:
        if hasattr(signal, "ITIMER_REAL"):
            signal.setitimer(signal.ITIMER_REAL, 0)
        if mode == "codex":
            # Stop accepts JSON output; an empty object makes no decision.
            print("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
