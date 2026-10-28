"""Wi-Fi indicator transitions against an isolated Linux sysfs fixture."""

from pathlib import Path
import shutil
import tempfile
import unittest

from pipclock.network import WifiMonitor


class WifiMonitorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.now = 100.0
        self.monitor = WifiMonitor(self.root, clock=lambda: self.now)

    def interface(self, name, state="up", carrier="1", wireless=True):
        path = self.root / name
        path.mkdir(exist_ok=True)
        if wireless:
            (path / "wireless").mkdir(exist_ok=True)
        (path / "operstate").write_text(state, encoding="ascii")
        (path / "carrier").write_text(carrier, encoding="ascii")
        return path

    def test_ethernet_connectivity_does_not_report_wifi_connected(self):
        self.interface("eth0", wireless=False)
        self.assertEqual(self.monitor.status(), "unavailable")

    def test_link_loss_and_reconnection_refresh_within_two_seconds(self):
        wifi = self.interface("wlan0")
        self.assertEqual(self.monitor.status(), "connected")
        (wifi / "carrier").write_text("0", encoding="ascii")
        self.now += 1.9
        self.assertEqual(self.monitor.status(), "connected")
        self.now += 0.1
        self.assertEqual(self.monitor.status(), "disconnected")
        (wifi / "carrier").write_text("1", encoding="ascii")
        self.now += 2
        self.assertEqual(self.monitor.status(), "connected")

    def test_disabled_radio_is_disconnected_even_when_carrier_cannot_be_read(self):
        wifi = self.interface("wlan0", state="down")
        (wifi / "carrier").unlink()
        self.assertEqual(self.monitor.status(), "disconnected")

    def test_any_associated_wireless_interface_counts_and_removal_is_detected(self):
        first = self.interface("wlan0", state="dormant")
        second = self.interface("wlx1234")
        self.assertEqual(self.monitor.status(), "connected")
        shutil.rmtree(second)
        self.now += 2
        self.assertEqual(self.monitor.status(), "disconnected")
        shutil.rmtree(first)
        self.now += 2
        self.assertEqual(self.monitor.status(), "unavailable")

    def test_unreadable_or_missing_wifi_state_never_reports_connected(self):
        wifi = self.interface("wlan0")
        (wifi / "operstate").unlink()
        self.assertEqual(self.monitor.status(), "unavailable")
        shutil.rmtree(self.root)
        self.now += 2
        self.assertEqual(self.monitor.status(), "unavailable")


if __name__ == "__main__":
    unittest.main()
