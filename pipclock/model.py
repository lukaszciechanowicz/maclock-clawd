"""Thread-safe, monotonic display state with optional idle configuration storage."""

import json
import os
from pathlib import Path
import tempfile
import threading
import time

from .catalog import WEBSITE_ACTIONS

DEFAULT_TEXT_SIZE = 64
MIN_TEXT_SIZE = 32
MAX_TEXT_SIZE = 96
DEFAULT_IDLE_ACTIONS = (
    "idle", "pool", "skate", "headphones", "sleeping", "reading",
    "coffee", "kite", "swaying",
)
DEFAULT_IDLE_INTERVAL = 30


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


def text_size_value(value):
    if isinstance(value, bool) or not isinstance(value, int) or not MIN_TEXT_SIZE <= value <= MAX_TEXT_SIZE:
        raise ValueError(f"text_size must be an integer from {MIN_TEXT_SIZE} to {MAX_TEXT_SIZE}")
    return value


def idle_config_value(actions, interval):
    if not isinstance(actions, list) or not actions:
        raise ValueError("actions must be a nonempty list of unique event names")
    actions = [event_value(action) for action in actions]
    if len(set(actions)) != len(actions):
        raise ValueError("actions must contain unique event names")
    if isinstance(interval, bool) or not isinstance(interval, (int, float)) or not 5 <= interval <= 3600:
        raise ValueError("interval must be a number from 5 to 3600 seconds")
    return {"actions": actions, "interval": float(interval)}


class Companion:
    def __init__(self, clock=time.monotonic, idle_config_path=None):
        self._clock = clock
        self._lock = threading.Lock()
        self._idle_config_path = Path(idle_config_path) if idle_config_path is not None else None
        self._idle_config = {"actions": list(DEFAULT_IDLE_ACTIONS), "interval": DEFAULT_IDLE_INTERVAL}
        if self._idle_config_path is not None:
            try:
                config = json.loads(self._idle_config_path.read_text(encoding="utf-8"))
                if not isinstance(config, dict):
                    raise ValueError("idle configuration must be a JSON object")
                self._idle_config = idle_config_value(config.get("actions"), config.get("interval"))
            except FileNotFoundError:
                pass
            except (ValueError, RecursionError) as error:
                raise ValueError(f"invalid idle configuration in {self._idle_config_path}: {error}") from error
        self._state = "wave"
        self._started = clock()
        self._until = self._started + 8
        self._message = None
        self._message_until = 0
        self._message_started = 0
        self._message_text_size = DEFAULT_TEXT_SIZE
        self._caption = None
        self._caption_until = 0
        self._caption_started = 0
        self._caption_text_size = DEFAULT_TEXT_SIZE

    def idle_config(self):
        with self._lock:
            return {"actions": list(self._idle_config["actions"]), "interval": self._idle_config["interval"]}

    def _save_idle_config(self, config):
        path = self._idle_config_path
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, prefix=".idle-", delete=False,
            ) as handle:
                temporary = Path(handle.name)
                os.fchmod(handle.fileno(), 0o600)
                json.dump(config, handle)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def configure_idle(self, actions, interval):
        config = idle_config_value(actions, interval)
        with self._lock:
            if self._idle_config_path is not None:
                self._save_idle_config(config)
            now = self._clock()
            self._expire_event(now)
            self._idle_config = config
            if self._state == "idle":
                self._started = now
            return {"actions": list(config["actions"]), "interval": config["interval"]}

    def _expire_event(self, now):
        if self._until and now >= self._until:
            self._state = "idle"
            self._started = self._until
            self._until = 0

    def event(self, event, duration=None):
        event = event_value(event)
        seconds = EVENT_DURATIONS[event] if duration is None else duration_value(duration)
        with self._lock:
            now = self._clock()
            self._expire_event(now)
            # Tool activity extends thinking; explicit actions replay on request.
            if self._state != event or event != "thinking":
                self._started = now
            self._state = event
            self._until = 0 if event == "idle" else now + seconds
            self._caption = None
            self._caption_until = 0

    def react(self, mood, text, duration=8, text_size=DEFAULT_TEXT_SIZE):
        mood = event_value(mood)
        text = text_value(text)
        seconds = duration_value(duration)
        text_size = text_size_value(text_size)
        with self._lock:
            now = self._clock()
            self._state = mood
            self._started = now
            self._until = 0 if mood == "idle" else now + seconds
            self._caption = text
            self._caption_until = now + seconds
            self._caption_started = now
            self._caption_text_size = text_size

    def message(self, text, duration, text_size=DEFAULT_TEXT_SIZE):
        text = text_value(text)
        seconds = duration_value(duration)
        text_size = text_size_value(text_size)
        with self._lock:
            now = self._clock()
            self._message = text
            self._message_started = now
            self._message_until = now + seconds
            self._message_text_size = text_size

    def claude(self, payload):
        event = payload.get("hook_event_name")
        if not isinstance(event, str) or event not in CLAUDE_EVENTS:
            raise ValueError("unsupported hook_event_name")
        self.event(CLAUDE_EVENTS[event])

    def snapshot(self):
        with self._lock:
            now = self._clock()
            self._expire_event(now)
            if self._message is not None and now >= self._message_until:
                self._message = None
            if self._caption is not None and now >= self._caption_until:
                self._caption = None
            elapsed = max(0, now - self._started)
            animation = self._state
            animation_elapsed = elapsed
            if self._state == "idle":
                actions = self._idle_config["actions"]
                if len(actions) == 1:
                    animation = actions[0]
                else:
                    turn, animation_elapsed = divmod(elapsed, self._idle_config["interval"])
                    animation = actions[int(turn) % len(actions)]
            return {
                "state": self._state,
                "elapsed": elapsed,
                "animation": animation,
                "animation_elapsed": animation_elapsed,
                "message": self._message,
                "message_remaining": max(0, self._message_until - now),
                "message_text_size": self._message_text_size if self._message is not None else DEFAULT_TEXT_SIZE,
                "message_elapsed": max(0, now - self._message_started) if self._message is not None else 0,
                "caption": self._caption,
                "caption_remaining": max(0, self._caption_until - now),
                "caption_text_size": self._caption_text_size if self._caption is not None else DEFAULT_TEXT_SIZE,
                "caption_elapsed": max(0, now - self._caption_started) if self._caption is not None else 0,
            }
