"""Thread-safe, monotonic display state; nothing is persisted."""

import threading
import time

from .catalog import WEBSITE_ACTIONS


EVENT_DURATIONS = {
    "idle": 0, "smile": 8, "knock": 8, "waiting": 60,
    "coffee": 12, "reading": 20, "lens": 12, "ok": 8, "scared": 8,
    "phone_ringing": 10, "sunglasses": 12, "deal_with_it": 10,
    "closeup": 12, "heart_eyes": 10,
}
EVENT_DURATIONS.update(
    (event, action["duration"]) for event, action in WEBSITE_ACTIONS.items()
)
CLAUDE_EVENTS = {
    "SessionStart": "wave",
    "UserPromptSubmit": "thinking",
    "PreToolUse": "thinking",
    "PostToolUse": "thinking",
    "Stop": "bounce",
    "Notification": "waiting",
    "PermissionRequest": "waiting",
    "PostToolUseFailure": "knock",
    "StopFailure": "knock",
    "SessionEnd": "idle",
}


def duration_value(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("duration must be a number in seconds")
    if not 0 < value <= 3600:
        raise ValueError("duration must be greater than 0 and at most 3600 seconds")
    return float(value)


class Companion:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._state = "wave"
        self._started = clock()
        self._until = self._started + 8
        self._message = None
        self._message_until = 0

    def event(self, event, duration=None):
        if not isinstance(event, str) or event not in EVENT_DURATIONS:
            raise ValueError("event must be one of: " + ", ".join(EVENT_DURATIONS))
        seconds = EVENT_DURATIONS[event] if duration is None else duration_value(duration)
        with self._lock:
            now = self._clock()
            # Tool activity extends thinking; explicit actions replay on request.
            if self._state != event or event != "thinking":
                self._started = now
            self._state = event
            self._until = 0 if event == "idle" else now + seconds

    def message(self, text, duration):
        if not isinstance(text, str) or not text.strip() or len(text) > 280:
            raise ValueError("text must contain 1 to 280 characters and not be blank")
        if any(not char.isprintable() and char != "\n" for char in text):
            raise ValueError("text may contain printable characters and newlines only")
        seconds = duration_value(duration)
        with self._lock:
            self._message = text
            self._message_until = self._clock() + seconds

    def claude(self, payload):
        event = payload.get("hook_event_name")
        if not isinstance(event, str) or event not in CLAUDE_EVENTS:
            raise ValueError("unsupported hook_event_name")
        self.event(CLAUDE_EVENTS[event])

    def snapshot(self):
        with self._lock:
            now = self._clock()
            if self._until and now >= self._until:
                self._state = "idle"
                self._started = self._until
                self._until = 0
            if self._message is not None and now >= self._message_until:
                self._message = None
            return {
                "state": self._state,
                "elapsed": max(0, now - self._started),
                "message": self._message,
                "message_remaining": max(0, self._message_until - now),
            }
