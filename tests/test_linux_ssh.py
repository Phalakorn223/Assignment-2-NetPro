import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock, patch
from connection_manager import ConnectionManager
import app

class TestLinuxSsh(unittest.TestCase):
    def setUp(self):
        self.cm = ConnectionManager()
        self.app = app.app.test_client()

    @patch("connection_manager.ConnectHandler")
    def test_linux_device_type_and_no_cisco_enable(self, mock_connect_handler):
        mock_conn = MagicMock()
        mock_connect_handler.return_value = mock_conn

        params = {
            "device_type_label": "pc",
            "connection_type": "SSH",
            "ip": "192.168.80.139",
            "port": 22,
            "username": "ubuntu",
            "password": "password123",
        }
        res = self.cm.connect("PC1", params, skip_ping=True)
        self.assertTrue(res["success"])

        # Verify device_type passed to ConnectHandler is "linux"
        mock_connect_handler.assert_called_once()
        call_kwargs = mock_connect_handler.call_args[1]
        self.assertEqual(call_kwargs["device_type"], "linux")
        self.assertEqual(call_kwargs["username"], "ubuntu")
        self.assertEqual(call_kwargs["password"], "password123")

        # Verify Cisco enable() and terminal length 0 were NOT called
        mock_conn.enable.assert_not_called()
        for call in mock_conn.send_command.call_args_list:
            self.assertNotIn("terminal length 0", call[0])

    def test_linux_prompt_detection_in_send_interactive(self):
        mock_conn = MagicMock()
        mock_conn.read_channel_timing.return_value = "ubuntu@ubuntu-desktop:~$ "
        self.cm.pool["PC1"] = {"handler": mock_conn, "type": "SSH", "is_linux": True, "params": {}}

        res = self.cm.send_interactive("PC1", "")
        self.assertTrue(res["success"])
        self.assertEqual(res["prompt"], "ubuntu@ubuntu-desktop:~$")
        self.assertFalse(res["is_password"])

    def test_linux_prompt_detection_root(self):
        mock_conn = MagicMock()
        mock_conn.read_channel_timing.return_value = "root@ubuntu:~# "
        self.cm.pool["PC1"] = {"handler": mock_conn, "type": "SSH", "is_linux": True, "params": {}}

        res = self.cm.send_interactive("PC1", "")
        self.assertTrue(res["success"])
        self.assertEqual(res["prompt"], "root@ubuntu:~#")

    def test_sudo_password_prompt_detection(self):
        mock_conn = MagicMock()
        mock_conn.read_channel_timing.return_value = "[sudo] password for user: "
        self.cm.pool["PC1"] = {"handler": mock_conn, "type": "SSH", "is_linux": True, "params": {}}

        res = self.cm.send_interactive("PC1", "sudo apt install net-tools")
        self.assertTrue(res["success"])
        self.assertEqual(res["prompt"], "[sudo] password for user:")
        self.assertTrue(res["is_password"])

if __name__ == "__main__":
    unittest.main()
