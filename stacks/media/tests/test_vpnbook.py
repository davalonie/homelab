import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import vpnbook


SERVER = "fr231.vpnbook.com"
SERVICES = ["gluetun", "qbittorrent"]


class ProviderTests(unittest.TestCase):
    def test_rejects_ambiguous_password(self):
        faq = "Username: vpnbook. Password: first123."
        self.assertEqual(vpnbook.credentials(faq), "first123")
        with self.assertRaises(ValueError):
            vpnbook.credentials(faq + " Username: vpnbook. Password: second123.")

    def test_only_imports_expected_server_and_pem_blocks(self):
        lines = [f"remote {SERVER} 443", "up /unexpected", "script-security 2"]
        for tag, label in (("ca", "CERTIFICATE"), ("cert", "CERTIFICATE"), ("key", "PRIVATE KEY")):
            lines.extend([f"<{tag}>", f"-----BEGIN {label}-----", "YQ==",
                          f"-----END {label}-----", f"</{tag}>"])
        source = "\n".join(lines)
        profile = vpnbook.client_profile(source, SERVER, "192.0.2.8")
        self.assertIn("remote 192.0.2.8 443", profile)
        self.assertIn("remote-cert-tls server", profile)
        self.assertNotIn("/unexpected", profile)
        with self.assertRaises(ValueError):
            vpnbook.client_profile(source.replace(" 443", " 80"), SERVER, "192.0.2.8")
        with self.assertRaises(ValueError):
            vpnbook.client_profile(source.replace("-----END PRIVATE KEY-----", "bad"), SERVER, "192.0.2.8")


class RotationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.state = Path(tmp.name)
        self.fetch = self.enterContext(patch.object(vpnbook, "fetch", return_value=("profile", "password1")))
        self.apply = self.enterContext(patch.object(vpnbook, "apply"))

    def refresh(self, services=SERVICES):
        vpnbook.refresh(self.state, SERVER, services)
        return os.readlink(self.state / "current")

    def test_offline_prepare_and_password_only_rotation(self):
        first = self.refresh([])
        self.apply.assert_not_called()
        self.assertFalse((self.state / "confirmed").exists())
        self.assertEqual(self.refresh(), first)
        self.fetch.return_value = ("profile", "password2")
        second = self.refresh()
        self.assertNotEqual(first, second)
        self.assertEqual(os.readlink(self.state / "confirmed"), second)
        self.assertEqual((self.state / "current/password").read_text().strip(), "password2")

    def test_provider_failure_preserves_live_generation(self):
        previous = self.refresh()
        self.apply.reset_mock()
        self.fetch.side_effect = ValueError("incomplete profile")
        with self.assertRaises(ValueError):
            self.refresh()
        self.assertEqual(os.readlink(self.state / "current"), previous)
        self.apply.assert_not_called()

    def test_interrupted_rotation_restores_confirmed_generation_on_failure(self):
        previous = self.refresh()
        self.fetch.return_value = ("another-profile", "password2")
        pending = vpnbook.stage(self.state, *self.fetch.return_value)
        vpnbook.point(self.state / "current", pending)
        attempted = []

        def deploy(_):
            attempted.append(os.readlink(self.state / "current"))
            if attempted[-1] == pending:
                raise subprocess.CalledProcessError(1, ["docker", "compose", "up"])

        self.apply.side_effect = deploy
        with self.assertRaises(subprocess.CalledProcessError):
            self.refresh()
        self.assertEqual(attempted, [pending, previous])
        self.assertEqual(os.readlink(self.state / "current"), previous)
        self.assertEqual(os.readlink(self.state / "confirmed"), previous)

    def test_resume_after_compose_stops_both_services_and_provider_is_offline(self):
        previous = self.refresh()
        self.fetch.return_value = ("new", "password2")
        self.apply.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.refresh()
        self.apply.reset_mock(side_effect=True)
        self.fetch.side_effect = OSError("offline")
        with self.assertRaises(OSError):
            self.refresh([])
        self.apply.assert_called_once_with(SERVICES)
        self.assertEqual(os.readlink(self.state / "current"), previous)
        self.assertFalse((self.state / "pending.json").exists())


if __name__ == "__main__":
    unittest.main()
