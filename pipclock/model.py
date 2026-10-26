"""Thread-safe, monotonic display state; nothing is persisted."""

import threading
import time

from .catalog import WEBSITE_ACTIONS


EVENT_DURATIONS = {
    "idle": 0, "smile": 8, "knock": 8, "waiting": 60,
    "coffee": 12, "reading": 20, "lens": 12, "ok": 8, "scared": 8,
    "phone_ringing": 10, "sunglasses": 12, "deal_with_it": 10,
    "closeup": 12, "heart_eyes": 10,
    "flag_pl": 12, "flag_aws": 12, "flag_shipstation": 12,
    "flag_stamps": 12, "cloud_engineering": 12,
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


def event_value(value):
    if not isinstance(value, str) or value not in EVENT_DURATIONS:
        raise ValueError("event must be one of: " + ", ".join(EVENT_DURATIONS))
    return value


def text_value(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 280:
        raise ValueError("text must contain 1 to 280 characters and not be blank")
    if any(not char.isprintable() and char != "\n" for char in value):
        raise ValueError("text may contain printable characters and newlines only")
    return value


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
        self._caption = None
        self._caption_until = 0

    def event(self, event, duration=None):
        event = event_value(event)
        seconds = EVENT_DURATIONS[event] if duration is None else duration_value(duration)
        with self._lock:
            now = self._clock()
            # Tool activity extends thinking; explicit actions replay on request.
            if self._state != event or event != "thinking":
                self._started = now
            self._state = event
            self._until = 0 if event == "idle" else now + seconds
            self._caption = None
            self._caption_until = 0

    def react(self, mood, text, duration=8):
        mood = event_value(mood)
        text = text_value(text)
        seconds = duration_value(duration)
        with self._lock:
            now = self._clock()
            self._state = mood
            self._started = now
            self._until = 0 if mood == "idle" else now + seconds
            self._caption = text
            self._caption_until = now + seconds

    def message(self, text, duration):
        text = text_value(text)
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
            if self._caption is not None and now >= self._caption_until:
                self._caption = None
            return {
                "state": self._state,
                "elapsed": max(0, now - self._started),
                "message": self._message,
                "message_remaining": max(0, self._message_until - now),
                "caption": self._caption,
                "caption_remaining": max(0, self._caption_until - now),
            }
