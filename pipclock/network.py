"""Read Linux Wi-Fi link state without subprocesses or Internet requests."""

from pathlib import Path
import time


class WifiMonitor:
    """Cache association state so rendering never polls sysfs every frame."""

    def __init__(self, directory=Path("/sys/class/net"), clock=time.monotonic):
        self._directory = Path(directory)
        self._clock = clock
        self._next_check = 0.0
        self._status = "unavailable"

    def status(self):
        now = self._clock()
        if now >= self._next_check:
            self._status = self._read_status()
            self._next_check = now + 2.0
        return self._status

    def _read_status(self):
        try:
            interfaces = tuple(self._directory.iterdir())
        except OSError:
            return "unavailable"
        available = False
        for interface in interfaces:
            if not (interface / "wireless").is_dir():
                continue
            try:
                state = (interface / "operstate").read_text(encoding="ascii").strip()
                # A down Wi-Fi device can reject carrier reads with EINVAL.
                if state != "up":
                    available = True
                    continue
                carrier = (interface / "carrier").read_text(encoding="ascii").strip()
            except (OSError, UnicodeError):
                continue
            available = True
            if carrier == "1":
                return "connected"
        return "disconnected" if available else "unavailable"
