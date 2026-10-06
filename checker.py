import ipaddress
import json
import os
import selectors
import subprocess
import sys
import time
from urllib.parse import urlsplit


MAX_RESPONSE_BYTES = 256
DEFAULT_ENDPOINT = "https://api.ipify.org"


class CheckFailure(Exception):
    pass


def _settings(settings):
    keys = {"mode", "addresses", "endpoint", "family", "timeoutSeconds"}
    if not isinstance(settings, dict) or settings.keys() - keys:
        raise ValueError
    mode = settings.get("mode", "whitelist")
    family = settings.get("family", "auto")
    timeout = settings.get("timeoutSeconds", 8)
    addresses = settings.get("addresses")
    endpoint = settings.get("endpoint", DEFAULT_ENDPOINT)
    if mode not in ("whitelist", "blacklist") or family not in ("auto", "ipv4", "ipv6"):
        raise ValueError
    if type(timeout) is not int or not 1 <= timeout <= 30:
        raise ValueError
    if not isinstance(addresses, str) or not addresses.strip() or "%" in addresses:
        raise ValueError
    networks = [ipaddress.ip_network(item.strip(), strict=False) for item in addresses.split(",")]
    if not isinstance(endpoint, str) or not endpoint or any(
        ord(char) <= 32 or ord(char) >= 127 or char in "\\{}" for char in endpoint
    ):
        raise ValueError
    url = urlsplit(endpoint)
    if (url.scheme != "https" or not url.hostname or url.username is not None
            or url.password is not None or "#" in endpoint):
        raise ValueError
    if url.port is not None and not 1 <= url.port <= 65535:
        raise ValueError
    return mode, family, timeout, endpoint, networks


def _fetch(endpoint, family, timeout):
    argv = ["curl", "-q", "--silent", "--fail", "--globoff", "--proto", "=https",
            "--proto-redir", "=https", "--max-redirs", "0",
            "--connect-timeout", str(timeout), "--max-time", str(timeout),
            "--max-filesize", str(MAX_RESPONSE_BYTES), "--write-out", "\n%{http_code}"]
    if family != "auto":
        argv.append("--" + family)
    argv.extend(["--url", endpoint])
    deadline = time.monotonic() + timeout + 1
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, shell=False)
    data = bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise CheckFailure("IP check timed out.")
                chunk = os.read(process.stdout.fileno(), MAX_RESPONSE_BYTES + 5 - len(data))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_RESPONSE_BYTES + 4:
                    raise CheckFailure("IP response exceeded the size limit.")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CheckFailure("IP check timed out.")
        if process.wait(timeout=remaining) != 0:
            raise CheckFailure("IP request failed (network, HTTP, or TLS error).")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
    body, separator, status = bytes(data).rpartition(b"\n")
    if not separator or len(status) != 3 or not status.isdigit() or not 200 <= int(status) < 300:
        raise CheckFailure("IP endpoint returned an unsuccessful HTTP status.")
    if len(body) > MAX_RESPONSE_BYTES:
        raise CheckFailure("IP response exceeded the size limit.")
    return body


def check(settings):
    result = {"state": "unknown", "ip": "", "message": "Invalid settings.", "checkedAt": 0}
    try:
        try:
            mode, family, timeout, endpoint, networks = _settings(settings)
        except (ValueError, TypeError, AttributeError):
            return result
        try:
            body = _fetch(endpoint, family, timeout)
        except CheckFailure as error:
            result["message"] = str(error)
            return result
        except subprocess.TimeoutExpired:
            result["message"] = "IP check timed out."
            return result
        except OSError:
            result["message"] = "IP request could not be run."
            return result
        try:
            text = body.decode("ascii").strip(" \t\r\n")
            if "%" in text:
                raise ValueError
            ip = ipaddress.ip_address(text)
            if not ip.is_global or ip.is_multicast or ip.is_reserved:
                raise ValueError
            if family != "auto" and ip.version != (4 if family == "ipv4" else 6):
                raise ValueError
        except (ValueError, UnicodeError):
            result["message"] = "Endpoint did not return a single public IP of the requested family."
            return result
        matched = any(ip.version == network.version and ip in network for network in networks)
        allowed = matched if mode == "whitelist" else not matched
        result.update(state="ok" if allowed else "bad", ip=str(ip),
                      message="Public IP satisfies the policy." if allowed else "Public IP violates the policy.")
        return result
    finally:
        result["checkedAt"] = int(time.time())


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if len(argv) != 2 or argv[0] != "--settings":
            raise ValueError
        settings = json.loads(argv[1], object_pairs_hook=_unique_object,
                              parse_constant=_reject_constant)
        result = check(settings)
    except (ValueError, TypeError, RecursionError):
        result = {"state": "unknown", "ip": "", "message": "Invalid settings or CLI arguments.",
                  "checkedAt": int(time.time())}
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
