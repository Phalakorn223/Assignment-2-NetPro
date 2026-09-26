"""
test_cli_and_telnet_switch.py — Comprehensive Test Suite for CLI Real Device Data & Telnet Switch Connection Loss
Tests the resolution of Assignment 2 issues:
1. CLI real device command execution, prompt extraction, and buffer hygiene
2. Telnet Switch connection stability: pagination (terminal length 0, width 512), liveness probe, auto-reconnect on session drop, and keepalive
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connection_manager import ConnectionManager
import app as flask_app


class MockTelnetChannel:
    """Mock Netmiko connection handler simulating a Cisco Switch Telnet session"""
    def __init__(self, hostname="S1", mode="exec", alive=True):
        self.hostname = hostname
        self.mode = mode
        self._alive = alive
        self.buffer = ""
        self.history = []

    def is_alive(self):
        return self._alive

    def clear_buffer(self):
        self.buffer = ""

    def write_channel(self, text):
        if not self._alive:
            raise ConnectionResetError("Connection reset by peer (Switch exec-timeout)")
        self.history.append(text)
        text_clean = text.strip()

        if not text_clean:
            # Empty return key pressed: echo prompt
            self.buffer = f"\r\n{self._get_prompt()}"
            return

        if text_clean == "terminal length 0" or text_clean == "terminal width 512":
            self.buffer = f"\r\n{self._get_prompt()}"
        elif text_clean == "configure terminal" or text_clean == "conf t":
            self.mode = "config"
            self.buffer = f"{text_clean}\r\nEnter configuration commands, one per line. End with CNTL/Z.\r\n{self._get_prompt()}"
        elif text_clean.startswith("interface "):
            self.mode = "config_if"
            self.buffer = f"{text_clean}\r\n{self._get_prompt()}"
        elif text_clean in ("exit", "end"):
            self.mode = "exec"
            self.buffer = f"{text_clean}\r\n{self._get_prompt()}"
        elif text_clean == "show vlan":
            self.buffer = f"{text_clean}\r\nVLAN Name                             Status    Ports\r\n---- -------------------------------- --------- -------------------------------\r\n1    default                          active    Fa0/1, Fa0/2, Gi0/1\r\n{self._get_prompt()}"
        elif text_clean == "show ip interface brief":
            self.buffer = f"{text_clean}\r\nInterface                  IP-Address      OK? Method Status                Protocol\r\nVlan1                      11.12.13.2      YES manual up                    up\r\nFastEthernet0/1            unassigned      YES unset  up                    up\r\n{self._get_prompt()}"
        elif text_clean in ("en", "enable"):
            self.buffer = f"{text_clean}\r\nPassword: "
        elif text_clean == "show run":
            self.buffer = f"{text_clean}\r\nline 1\r\n--More--\r\nline 2\r\n{self._get_prompt()}"
        elif text_clean in ("\x03", "^C"):
            self.buffer = f"^C\r\n{self._get_prompt()}"
        else:
            self.buffer = f"{text_clean}\r\nOutput of {text_clean} executed on real device\r\n{self._get_prompt()}"

    def read_channel_timing(self, last_read=1.5, read_timeout=20.0):
        if not self._alive:
            raise EOFError("Telnet session closed by remote host")
        out = self.buffer
        self.buffer = ""
        return out

    def send_command(self, cmd, **kwargs):
        if not self._alive:
            raise EOFError("Telnet session closed by remote host")
        self.write_channel(cmd + "\r\n")
        raw = self.read_channel_timing()
        lines = [l for l in raw.splitlines() if l.strip() and not l.strip().endswith("#") and not l.strip().endswith(">")]
        return "\n".join(lines).strip()

    def disconnect(self):
        self._alive = False

    def _get_prompt(self):
        if self.mode == "config":
            return f"{self.hostname}(config)#"
        elif self.mode == "config_if":
            return f"{self.hostname}(config-if)#"
        return f"{self.hostname}#"


class TestCliAndTelnetSwitch(unittest.TestCase):
    def setUp(self):
        self.mgr = ConnectionManager()
        self.client = flask_app.app.test_client()

    def tearDown(self):
        self.mgr.disconnect_all()

    # --------------------------------------------------------------------------
    # 1. CLI Execution & Real Device Output Tests
    # --------------------------------------------------------------------------
    def test_cli_interactive_real_output_and_prompt(self):
        """Test that send_interactive executes command on live session and extracts real prompt & output"""
        mock_handler = MockTelnetChannel(hostname="S1")
        self.mgr.pool["S1"] = {"handler": mock_handler, "type": "TELNET", "params": {"id": "S1", "name": "S1"}}

        # Send command 'show vlan'
        res = self.mgr.send_interactive("S1", "show vlan")
        self.assertTrue(res["success"])
        self.assertIn("VLAN Name", res["output"])
        self.assertIn("1    default", res["output"])
        self.assertEqual(res["prompt"], "S1#")

    def test_cli_mode_transitions_and_prompt_updates(self):
        """Test that entering config and interface modes updates prompt to S1(config)# and S1(config-if)#"""
        mock_handler = MockTelnetChannel(hostname="S1")
        self.mgr.pool["S1"] = {"handler": mock_handler, "type": "TELNET", "params": {"id": "S1", "name": "S1"}}

        # 1. Enter config terminal
        res1 = self.mgr.send_interactive("S1", "configure terminal")
        self.assertTrue(res1["success"])
        self.assertEqual(res1["prompt"], "S1(config)#")

        # 2. Enter interface config
        res2 = self.mgr.send_interactive("S1", "interface Vlan1")
        self.assertTrue(res2["success"])
        self.assertEqual(res2["prompt"], "S1(config-if)#")

        # 3. Exit back to exec mode
        res3 = self.mgr.send_interactive("S1", "end")
        self.assertTrue(res3["success"])
        self.assertEqual(res3["prompt"], "S1#")

    def test_cli_empty_command_prompt_refresh(self):
        """Test that sending an empty command refreshes and retrieves the exact live prompt without executing fake commands"""
        mock_handler = MockTelnetChannel(hostname="S1", mode="config")
        self.mgr.pool["S1"] = {"handler": mock_handler, "type": "TELNET", "params": {"id": "S1", "name": "S1"}}

        res = self.mgr.send_interactive("S1", "")
        self.assertTrue(res["success"])
        self.assertEqual(res["prompt"], "S1(config)#")

    # --------------------------------------------------------------------------
    # 2. Telnet Switch Connection Loss & Auto-Reconnect Tests
    # --------------------------------------------------------------------------
    def test_is_connected_liveness_check(self):
        """Test that is_connected(check_alive=True) detects when the Telnet socket has been terminated by the Switch"""
        mock_handler = MockTelnetChannel(hostname="S1", alive=True)
        self.mgr.pool["S1"] = {"handler": mock_handler, "type": "TELNET", "params": {"id": "S1", "name": "S1"}}

        # Initially alive
        self.assertTrue(self.mgr.is_connected("S1", check_alive=True))

        # Switch drops the connection (exec-timeout)
        mock_handler._alive = False

        # is_connected with check_alive must detect the dead socket, purge it from pool, and return False
        self.assertFalse(self.mgr.is_connected("S1", check_alive=True))
        self.assertNotIn("S1", self.mgr.pool)

    def test_send_interactive_auto_reconnect_on_connection_drop(self):
        """Test that send_interactive seamlessly auto-reconnects when the Switch drops connection during execution"""
        reconnected_handler = MockTelnetChannel(hostname="S1", alive=True)

        dead_handler = MockTelnetChannel(hostname="S1", alive=False)
        self.mgr.pool["S1"] = {"handler": dead_handler, "type": "TELNET", "params": {"id": "S1", "name": "S1"}}

        # Patch _ensure_connection to re-establish the connection with reconnected_handler
        def mock_ensure_conn(dev_id):
            self.mgr.pool["S1"] = {"handler": reconnected_handler, "type": "TELNET", "params": {"id": "S1", "name": "S1"}}
            return True

        with patch.object(self.mgr, "_ensure_connection", side_effect=mock_ensure_conn):
            res = self.mgr.send_interactive("S1", "show ip interface brief")
            self.assertTrue(res["success"])
            self.assertIn("Vlan1", res["output"])
            self.assertEqual(res["prompt"], "S1#")

    def test_send_keepalive_prevents_idle_timeout(self):
        """Test that send_keepalive verifies each session and triggers reconnect on dead sessions"""
        alive_handler = MockTelnetChannel(hostname="R1", alive=True)
        dead_handler = MockTelnetChannel(hostname="S1", alive=False)

        self.mgr.pool["R1"] = {"handler": alive_handler, "type": "TELNET", "params": {"id": "R1"}}
        self.mgr.pool["S1"] = {"handler": dead_handler, "type": "TELNET", "params": {"id": "S1"}}

        reconnected = []
        def mock_ensure_conn(dev_id):
            reconnected.append(dev_id)
            return True

        with patch.object(self.mgr, "_ensure_connection", side_effect=mock_ensure_conn):
            self.mgr.send_keepalive()

        # Dead S1 should have been cleaned up and reconnected
        self.assertIn("S1", reconnected)
        # Alive R1 should remain in pool
        self.assertIn("R1", self.mgr.pool)

    # --------------------------------------------------------------------------
    # 3. Flask API Endpoint Tests
    # --------------------------------------------------------------------------
    def test_api_cli_execute_endpoint(self):
        """Test that POST /api/cli/execute calls send_interactive and returns true device prompt & output"""
        mock_handler = MockTelnetChannel(hostname="S1")
        flask_app.conn_mgr.pool["S1"] = {"handler": mock_handler, "type": "TELNET", "params": {"id": "S1", "name": "S1"}}

        res = self.client.post("/api/cli/execute", json={"device_id": "S1", "command": "show vlan"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("prompt"), "S1#")
        self.assertIn("VLAN Name", data.get("output", ""))

    def test_api_connections_keepalive_endpoint(self):
        """Test that POST /api/connections/keepalive triggers keepalive without error"""
        mock_handler = MockTelnetChannel(hostname="S1")
        flask_app.conn_mgr.pool["S1"] = {"handler": mock_handler, "type": "TELNET", "params": {"id": "S1", "name": "S1"}}

        res = self.client.post("/api/connections/keepalive", json={"device_id": "S1"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))

    # --------------------------------------------------------------------------
    # 4. Tera Term / PuTTY CLI Stream Features (network_cli_teraterm_putty_vibecoding.md)
    # --------------------------------------------------------------------------
    def test_cli_password_prompt_detection(self):
        """Test that enable/password prompts are detected with is_password=True (Section 18-19, 44)"""
        mock_handler = MockTelnetChannel(hostname="R1")
        # Simulate router asking for Password:
        mock_handler.buffer = "en\r\nPassword: "
        self.mgr.pool["R1"] = {"handler": mock_handler, "type": "TELNET", "params": {"id": "R1", "name": "R1"}}

        res = self.mgr.send_interactive("R1", "en")
        self.assertTrue(res["success"])
        self.assertEqual(res["prompt"], "Password:")
        self.assertTrue(res["is_password"])

    def test_cli_paging_handling(self):
        """Test that --More-- paging artifacts are automatically stripped from final output (Section 14 & 24)"""
        mock_handler = MockTelnetChannel(hostname="R1")
        mock_handler.buffer = "show run\r\nline 1\r\n--More--\r\nline 2\r\nR1#"
        self.mgr.pool["R1"] = {"handler": mock_handler, "type": "TELNET", "params": {"id": "R1"}}

        res = self.mgr.send_interactive("R1", "show run")
        self.assertTrue(res["success"])
        self.assertNotIn("--More--", res["output"])
        self.assertIn("line 1", res["output"])
        self.assertIn("line 2", res["output"])
        self.assertEqual(res["prompt"], "R1#")

    def test_cli_break_signal_handling(self):
        """Test that Ctrl+C / \\x03 break signal interrupts execution and returns fresh prompt"""
        mock_handler = MockTelnetChannel(hostname="R1")
        mock_handler.buffer = "^C\r\nR1#"
        self.mgr.pool["R1"] = {"handler": mock_handler, "type": "TELNET", "params": {"id": "R1"}}

        res = self.mgr.send_interactive("R1", "\x03")
        self.assertTrue(res["success"])
        self.assertEqual(res["prompt"], "R1#")

    def test_api_cli_reconnect_endpoint(self):
        """Test that POST /api/cli/reconnect re-establishes session and returns active prompt"""
        mock_handler = MockTelnetChannel(hostname="R1")
        def mock_conn(dev_id, params, skip_ping=True):
            self.mgr.pool["R1"] = {"handler": mock_handler, "type": "TELNET", "params": {"id": "R1"}}
            return {"success": True, "message": "Connected"}

        with patch.object(flask_app.conn_mgr, "connect", side_effect=mock_conn), \
             patch.object(flask_app.conn_mgr, "send_interactive", return_value={"success": True, "prompt": "R1#"}):
            res = self.client.post("/api/cli/reconnect", json={"device_id": "R1"})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get("success"))

    # --------------------------------------------------------------------------
    # 5. Frontend Code Integrity Check
    # --------------------------------------------------------------------------
    def test_frontend_append_console_defined(self):
        """Verify that appendConsole is properly defined in static/js/app.js to prevent JavaScript runtime errors"""
        app_js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "js", "app.js"))
        with open(app_js_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("function appendConsole(", content, "appendConsole function must be defined in app.js")
        self.assertIn("setCliDirectPrompt(data.prompt)", content, "Prompt must be updated from real device response")
        self.assertIn("deviceTerminalState", content, "Terminal must maintain per-device session buffers")
        self.assertIn("cliIsPasswordMode", content, "Terminal must support password input masking")
        # Ensure showNotification does NOT append notification toasts into CLI console lines
        self.assertNotIn('appendConsole(`${prefix} ${message}`', content, "showNotification must not contaminate CLI console stream")


if __name__ == "__main__":
    unittest.main(verbosity=2)
