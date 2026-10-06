# OmaIP contributor instructions

Build a native Omarchy shell plugin that checks an externally reported public IP. Keep HTTP evidence separate from claims about VPN health.

## Boundaries

- Read README.md and docs/PLAN.md before changing behavior.
- Never infer success from local interfaces, routes, VPN clients, NetworkManager, or proxy configuration.
- Whitelist membership and blacklist non-membership are the only success rules. Empty lists, invalid settings, failed requests, and expired results stay unknown.
- Do not add telemetry, IP history, fallback endpoints, routing changes, or dependencies without a concrete request.
- Keep TLS verification enabled. Disable curlrc, forbid redirects, bound time and response size, and invoke subprocesses with argument arrays, never shell strings.
- Keep credentials out of settings, fixtures, logs, and docs.
- Do not install or change the desktop plugin without explicit permission. Never edit /usr/share/omarchy.
- Work in the current checkout. Do not create branches or mutate Git history without permission.
- Use the bound af project for authorized tasks. Keep lasting implementation decisions in the task's Agent Log.

## Files and contracts

- manifest.json: plugin ID, defaults, inline settings schema.
- Widget.qml: native BarWidget, polling, Process lifecycle, indicator, popup routing, shell save API.
- Popup.qml: status view, editable settings draft, validation, focus scrolling, Save/Cancel.
- State.js: settings projection, result validation, poll bounds, expiry.
- checker.py: validated policy, bounded curl request, IP parsing, JSON CLI.
- tests/: offline Python checker tests and Node state checks.

Plugin ID: pbjorklund.omaip. Do not use the reserved omarchy.* namespace. Keep manifest, code defaults, and README examples consistent.

The checker emits one JSON object: state (ok/bad/unknown), ip, message, checkedAt. A policy mismatch is a valid result, not a process error. Preserve distinct thumb directions and the unknown symbol; color alone is not enough.

Settings changes must immediately invalidate previous results. Never accept an obsolete settings snapshot. Do not overlap polls.

## Validation

1. Add a focused offline regression test before changing behavior.
2. Run mise run test, then mise run validate.
3. For QML changes, compare with installed host components read-only. Run mise run test-shell. Run mise run test-desktop on an available Omarchy desktop, then state unverified behavior. Both use synthetic data, never the real shell configuration.
4. Settings writes must preserve unknown entry fields, reject refused changed updates, and leave the draft open on failure. The host API does not prove disk persistence.
5. Review docs for factual claims and run the available prose scanner after durable text changes.
6. Report live-network checks separately from offline tests. Never claim VPN protection from a passing policy test.

Routine tests must not contact external services. Live checks expose the exit IP to the provider and require an explicit operator action.
