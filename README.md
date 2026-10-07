# OmaIP

OmaIP checks the public IP reported by an external HTTPS service and shows the result in the Omarchy shell bar. It never reads local VPN, interface, route, or system proxy configuration.

When you setup a blacklist or whitelist it will quickly let you know if you are on the IP(s) you think:

<img width="823" height="414" alt="image" src="https://github.com/user-attachments/assets/42310ca6-f6d0-4d09-8b01-20bdec8c16e5" />


| Mode | Normal-color thumbs up | Red thumbs down |
|---|---|---|
| Whitelist | IP is in the list | IP is not in the list |
| Blacklist | IP is not in the list | IP is in the list |

A question mark means unknown: invalid settings, failed request, invalid response, or an expired result. Hover for IP, reason, and check time. Click to open the status popup, then use Refresh or Settings. Right or middle click checks again.

## Requirements

Omarchy's Quickshell shell with its third-party bar-widget API, Python 3, curl, and a Nerd Font for monochrome thumb icons. This is not a Waybar module.

## Settings

Click the thumb, choose Settings, edit the policy and connection fields, then Save. Cancel discards edits. Escape returns from settings to status, then closes the popup. The form preserves unrelated entry fields and shows errors when Omarchy refuses a changed configuration.

Omarchy stores settings inline in `~/.config/omarchy/shell.json`. Its save API accepts changes in memory and requests a disk write, but exposes no disk-write receipt to plugins. Check shell logs and the file if settings do not survive a restart.

For manual configuration, keep the rest of your shell configuration and add this entry to `bar.layout.right`:

```json
{
  "id": "pbjorklund.omaip",
  "mode": "whitelist",
  "addresses": "203.0.113.42, 2001:db8:1234::/48",
  "endpoint": "https://api.ipify.org",
  "family": "auto",
  "timeoutSeconds": 8,
  "intervalSeconds": 60
}
```

Replace those documentation-only addresses with real approved company exits. Settings are also declared in the manifest for Omarchy's bar settings.

- `mode`: `whitelist` (default) or `blacklist`, one policy at a time.
- `addresses`: comma-separated IPv4/IPv6 addresses or CIDRs. Empty/malformed lists give unknown. CIDRs with host bits are normalized to their network.
- `endpoint`: HTTPS, returning one public IP as plain text. Default `https://api.ipify.org`. HTML pages such as Proton's browser IP-check page are not supported.
- `family`: `auto` (default), `ipv4`, or `ipv6`. The endpoint must support that family; the default endpoint is IPv4-focused. `https://api64.ipify.org` is a dual-stack alternative.
- `timeoutSeconds`: integer 1-30, default 8.
- `intervalSeconds`: integer 15-3600, default 60.

Checks clear the previous result. Results expire after the poll interval plus 35 seconds, allowing for the longest request. Changing settings during a request discards its result and queues a fresh check.

Prefer a whitelist when approved exits are known. A blacklist accepts every unlisted exit.

## Install

Review the source, add the plugin, then enable it:

```bash
omarchy plugin add https://github.com/pbjorklund/omaip
omarchy plugin enable pbjorklund.omaip
```

An unconfigured plugin shows unknown. Open its Settings to enter your policy. Plugins run unsandboxed inside the shell; no hooks or privileges are needed.

For development, copy runtime files into a new user-owned folder without overwriting an existing installation:

```bash
mkdir -p ~/.config/omarchy/plugins
mkdir ~/.config/omarchy/plugins/pbjorklund.omaip
cp manifest.json Widget.qml Popup.qml State.js checker.py ~/.config/omarchy/plugins/pbjorklund.omaip/
omarchy plugin validate ~/.config/omarchy/plugins/pbjorklund.omaip
omarchy-shell shell rescanPlugins
omarchy plugin enable pbjorklund.omaip
```

Disable with `omarchy plugin disable pbjorklund.omaip`. Remove the user plugin folder only when you no longer need it. Never modify `/usr/share/omarchy/`.

## Tests

```bash
mise run test
mise run validate
```

Tests need Python 3 and Node.js. Validation also needs Omarchy. Without mise: `python3 -m unittest discover -s tests -v` and `node tests/test_state.cjs`.

On an Omarchy machine, `mise run test-shell` checks actual controls with only the layer-shell surface replaced for headless use. `mise run test-desktop` briefly shows a temporary test bar and the real popup. Both use a synthetic checker, never external requests or your shell configuration. They check popup opening, validation, numeric cancel/reset, locale parsing, focus scrolling, refused/accepted saves, refresh, and missing save support.

For a manual live check, replace the example address:

```bash
python3 checker.py --settings '{"mode":"whitelist","addresses":"203.0.113.42","endpoint":"https://api.ipify.org"}'
```

The CLI prints one JSON object: `state` (ok/bad/unknown), `ip`, `message`, `checkedAt` (Unix seconds). Inspect state, not process exit status.

## Limits

A thumbs up means this request's observed IP satisfied the policy. It does not prove encryption, VPN ownership, all-app routing, DNS safety, or absence of IPv6 leaks.

Curl inherits process proxy environment variables but ignores curlrc. The measured IP may be the proxy's exit. Browser PAC rules, extensions, cookies, and app-specific proxy settings are not shared with this check. Compare browser and widget against the same endpoint and proxy path before treating them as equivalent evidence.

One address family is checked per poll. Auto does not test both IPv4 and IPv6. A proxy may resolve the target itself; curl's family flag does not prove the proxy's upstream transport family. Each monitor's bar instance can make its own requests.

TLS verification stays enabled, redirects are rejected, and responses are capped at 256 bytes. Company TLS interception must already be trusted by curl. Never disable certificate verification. Errors omit response bodies and endpoint credentials. Providers see the requests; settings and process arguments are not secret storage.

There is no fallback endpoint, persistent IP history, telemetry, firewall enforcement, or routing change. Failed checks never reuse successful results.

Offline tests cover policy, transport, state expiry, and popup/settings wiring. Desktop tests use an in-memory settings host, not your actual shell file. Suspend/resume, full keyboard navigation, multi-monitor dismissal, and the real company proxy path still need operator checks. See [the plan](docs/PLAN.md).
