import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

import checker


class CheckerTests(unittest.TestCase):
    def run_check(self, settings=None, body=b"8.8.8.8", status=b"200", code=0):
        read_fd, write_fd = os.pipe()
        os.write(write_fd, body + b"\n" + status)
        os.close(write_fd)
        process = Mock(stdout=os.fdopen(read_fd, "rb"))
        process.wait.return_value = code
        process.poll.return_value = code
        with patch("checker.subprocess.Popen", return_value=process) as spawn:
            result = checker.check(settings or {"addresses": "8.8.8.8"})
        return result, spawn, process

    def test_default_whitelist_success(self):
        result, _, _ = self.run_check()
        self.assertEqual(result["state"], "ok")
        self.assertEqual(result["ip"], "8.8.8.8")
        self.assertEqual(set(result), {"state", "ip", "message", "checkedAt"})
        self.assertIsInstance(result["checkedAt"], int)

    def test_policies_and_cidrs(self):
        for mode, addresses, state in [
            ("whitelist", "8.8.0.1/16", "ok"),
            ("whitelist", "1.1.1.1", "bad"),
            ("blacklist", "8.8.8.8, 1.1.1.0/24", "bad"),
            ("blacklist", "1.1.1.1", "ok"),
        ]:
            with self.subTest(mode=mode, addresses=addresses):
                result, _, _ = self.run_check({"mode": mode, "addresses": addresses})
                self.assertEqual(result["state"], state)

    def test_ipv6_normalization_and_family(self):
        result, spawn, _ = self.run_check(
            {"addresses": "2606:4700::/32", "family": "ipv6"},
            b"2606:4700:4700:0000:0000:0000:0000:1111\n",
        )
        self.assertEqual(result["state"], "ok")
        self.assertEqual(result["ip"], "2606:4700:4700::1111")
        self.assertIn("--ipv6", spawn.call_args.args[0])
        for family, body in [("ipv6", b"8.8.8.8"), ("ipv4", b"2606:4700::1111")]:
            result, _, _ = self.run_check({"addresses": "0.0.0.0/0,::/0", "family": family}, body)
            self.assertEqual(result["state"], "unknown")

    def test_invalid_settings_do_not_spawn(self):
        invalid = [None, [], "x", {}, {"addresses": ""}, {"addresses": " , "},
                   {"addresses": 3}, {"addresses": "8.8.8.8,"},
                   {"addresses": "8.8.8.8,wrong"}, {"addresses": "fe80::1%eth0"}]
        for key, values in {
            "mode": [None, "allow", [], True], "family": [None, "4", [], True],
            "timeoutSeconds": [0, 31, True, "8", None, 1.5],
            "endpoint": [None, "http://example.com", "https://", "--insecure",
                         "https://user:secret@example.com", "https://example.com/#frag",
                         "https://example.com/\n", "https://example.com/{a,b}",
                         "https://example.com:99999", "https://example.com\\evil"],
            "extra": [1],
        }.items():
            invalid.extend({"addresses": "8.8.8.8", key: value} for value in values)
        with patch("checker.subprocess.Popen") as spawn:
            for settings in invalid:
                with self.subTest(settings=settings):
                    result = checker.check(settings)
                    self.assertEqual(result["state"], "unknown")
                    self.assertEqual(result["ip"], "")
            spawn.assert_not_called()

    def test_invalid_responses(self):
        for body in [b"", b"<html>8.8.8.8</html>", b'"8.8.8.8"', b"8.8.8.8\n1.1.1.1",
                     b"127.0.0.1", b"10.0.0.1", b"100.64.0.1", b"192.0.2.1",
                     b"224.0.0.1", b"::1", b"fe80::1", b"ff02::1", b"fe80::1%eth0",
                     b"8.8.8.8\x00", b"\xff", b"x" * 257]:
            with self.subTest(body=body):
                result, _, _ = self.run_check(body=body)
                self.assertEqual(result["state"], "unknown")
                self.assertEqual(result["ip"], "")
                decoded = body.decode("ascii", errors="ignore")
                if decoded:
                    self.assertNotIn(decoded, result["message"])

    def test_http_and_curl_failures_are_sanitized(self):
        for status, code in [(b"301", 0), (b"404", 22), (b"500", 22),
                             (b"200", 6), (b"200", 7), (b"200", 28),
                             (b"200", 35), (b"200", 60), (b"200", 63)]:
            with self.subTest(status=status, code=code):
                result, _, _ = self.run_check(body=b"SECRET", status=status, code=code)
                self.assertEqual(result["state"], "unknown")
                self.assertNotIn("SECRET", json.dumps(result))
        for error in [FileNotFoundError("SECRET"), OSError("SECRET")]:
            with patch("checker.subprocess.Popen", side_effect=error):
                self.assertEqual(checker.check({"addresses": "8.8.8.8"})["state"], "unknown")

    def test_argv_security_and_timeout_bounds(self):
        for timeout in [1, 8, 30]:
            result, spawn, _ = self.run_check({"addresses": "8.8.8.8", "family": "ipv4",
                                              "timeoutSeconds": timeout,
                                              "endpoint": "https://example.com/ip?x=;$(bad)"})
            self.assertEqual(result["state"], "ok")
            argv = spawn.call_args.args[0]
            self.assertEqual(argv[:2], ["curl", "-q"])
            self.assertIn("--ipv4", argv)
            self.assertEqual(argv[argv.index("--max-time") + 1], str(timeout))
            self.assertEqual(argv[argv.index("--proto") + 1], "=https")
            self.assertEqual(argv[argv.index("--max-filesize") + 1], "256")
            self.assertIn("--globoff", argv)
            for option in ["-k", "--insecure", "-L", "--location"]:
                self.assertNotIn(option, argv)
            self.assertNotIn("env", spawn.call_args.kwargs)
            self.assertFalse(spawn.call_args.kwargs.get("shell", False))
            self.assertEqual(spawn.call_args.kwargs["stderr"], subprocess.DEVNULL)

    def test_output_cap_stops_and_kills_child(self):
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b"SECRET" * 300)
        os.close(write_fd)
        process = Mock(stdout=os.fdopen(read_fd, "rb"))
        process.poll.return_value = None
        with patch("checker.subprocess.Popen", return_value=process), patch("checker.os.read", wraps=os.read) as read:
            result = checker.check({"addresses": "8.8.8.8"})
        self.assertEqual(result["state"], "unknown")
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertLessEqual(sum(call.args[1] for call in read.call_args_list), 261)
        process.kill.assert_called_once()
        self.assertTrue(process.stdout.closed)

    def test_response_size_boundary(self):
        for size, expected in [(256, "ok"), (257, "unknown")]:
            result, _, _ = self.run_check(body=b"8.8.8.8" + b" " * (size - 7))
            self.assertEqual(result["state"], expected)

    def test_watchdog_kills_stalled_child(self):
        read_fd, write_fd = os.pipe()
        process = Mock(stdout=os.fdopen(read_fd, "rb"))
        process.poll.return_value = None
        try:
            with patch("checker.subprocess.Popen", return_value=process), patch("checker.selectors.DefaultSelector") as selector:
                selector.return_value.__enter__.return_value.select.return_value = []
                result = checker.check({"addresses": "8.8.8.8", "timeoutSeconds": 1})
            self.assertEqual(result["state"], "unknown")
            self.assertIn("timed out", result["message"])
            process.kill.assert_called_once()
            process.wait.assert_called_once()
            self.assertTrue(process.stdout.closed)
        finally:
            os.close(write_fd)

    def test_wait_timeout_is_sanitized_and_reaped(self):
        read_fd, write_fd = os.pipe()
        os.close(write_fd)
        process = Mock(stdout=os.fdopen(read_fd, "rb"))
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("SECRET", 1), 0]
        with patch("checker.subprocess.Popen", return_value=process):
            result = checker.check({"addresses": "8.8.8.8"})
        self.assertEqual(result["state"], "unknown")
        self.assertNotIn("SECRET", json.dumps(result))
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)

    def test_no_cached_success(self):
        self.assertEqual(self.run_check()[0]["state"], "ok")
        self.assertEqual(self.run_check(code=7)[0]["state"], "unknown")

    def test_cli_json_for_invalid_invocations(self):
        script = str(Path(checker.__file__).resolve())
        for args in [[], ["--help"], ["--settings", "not-json"],
                     ["--settings", "{}"], ["--settings", "null"],
                     ["--settings", '{"addresses":"8.8.8.8","addresses":"1.1.1.1"}'],
                     ["--settings", "{}", "--extra", "SECRET"]]:
            completed = subprocess.run([sys.executable, script, *args], capture_output=True, timeout=2)
            result = json.loads(completed.stdout)
            self.assertEqual(result["state"], "unknown")
            self.assertEqual(completed.stderr, b"")
            self.assertEqual(len(completed.stdout.splitlines()), 1)

    def test_cli_success_with_mocked_network(self):
        with patch("checker.check", return_value={"state": "ok", "ip": "8.8.8.8", "message": "Allowed", "checkedAt": 1}):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                checker.main(["--settings", '{"addresses":"8.8.8.8"}'])
            self.assertEqual(json.loads(output.getvalue())["state"], "ok")


if __name__ == "__main__":
    unittest.main()
