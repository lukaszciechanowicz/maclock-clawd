"""Optional, active-low GPIO buttons for stepping the idle action group."""

from contextlib import ExitStack
import os
import threading


class IdleButtons:
    def __init__(self, companion, previous_pin, next_pin, *, pin_factory=None):
        if any(type(pin) is not int or not 0 <= pin <= 27 for pin in (previous_pin, next_pin)):
            raise ValueError("GPIO button pins must be BCM integers between 0 and 27")
        if previous_pin == next_pin:
            raise ValueError("PIPCLOCK_BUTTON_PREV and PIPCLOCK_BUTTON_NEXT must use distinct BCM pins")
        self.previous_pin = previous_pin
        self.next_pin = next_pin
        self._companion = companion
        self._lock = threading.Lock()
        self._closed = False
        self._resources = ExitStack()
        try:
            try:
                from gpiozero import Button
                if pin_factory is None:
                    from gpiozero.pins.lgpio import LGPIOFactory
            except ImportError as error:
                raise RuntimeError(
                    "GPIO buttons require gpiozero and lgpio; on Raspberry Pi install "
                    "the python3-gpiozero and python3-lgpio distro packages"
                ) from error
            if pin_factory is None:
                pin_factory = LGPIOFactory()
                self._resources.callback(pin_factory.close)
            previous = self._resources.enter_context(
                Button(previous_pin, pull_up=True, bounce_time=0.05, pin_factory=pin_factory)
            )
            next_button = self._resources.enter_context(
                Button(next_pin, pull_up=True, bounce_time=0.05, pin_factory=pin_factory)
            )
            previous.when_pressed = lambda: self._step(-1)
            next_button.when_pressed = lambda: self._step(1)
        except Exception as error:
            self.close()
            raise RuntimeError(
                f"Cannot initialize GPIO buttons on BCM {previous_pin} and {next_pin}: {error}. "
                "Check GPIO device permissions (the service needs the gpio group) "
                "and that neither pin is claimed by another device"
            ) from error
        except BaseException:
            self.close()
            raise

    @classmethod
    def from_environment(cls, companion, environ=None, *, pin_factory=None):
        environ = os.environ if environ is None else environ
        previous = environ.get("PIPCLOCK_BUTTON_PREV", "").strip()
        next_pin = environ.get("PIPCLOCK_BUTTON_NEXT", "").strip()
        if not previous and not next_pin:
            return None
        if not previous or not next_pin:
            raise ValueError("set both PIPCLOCK_BUTTON_PREV and PIPCLOCK_BUTTON_NEXT, or clear both")
        try:
            previous, next_pin = int(previous), int(next_pin)
        except ValueError as error:
            raise ValueError(
                "PIPCLOCK_BUTTON_PREV and PIPCLOCK_BUTTON_NEXT must be BCM integers between 0 and 27"
            ) from error
        return cls(companion, previous, next_pin, pin_factory=pin_factory)

    def _step(self, direction):
        # Wait for an in-flight press before closing, and reject callbacks queued
        # before close even if the GPIO backend delivers them afterwards.
        with self._lock:
            if not self._closed:
                self._companion.step_idle(direction)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
        # Device close can join backend threads; never join while holding the
        # callback lock. ExitStack still closes every resource if one fails.
        self._resources.close()
