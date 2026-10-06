# Project plan

Deliver an Omarchy bar indicator that compares an externally reported public IP with a whitelist or blacklist. Local VPN state is not evidence.

## Delivered

- Bounded HTTPS checker, public IPv4/IPv6 parsing, IP/CIDR matching, and unknown on failures.
- Normal-color thumbs up for passing policy, red thumbs down for failing policy.
- Click status popup with Refresh and Settings.
- Settings draft with validation, Save/Cancel, keyboard focus scrolling, and own-entry shell persistence.
- Offline checker/state tests, native-control and desktop popup tests, and CI.

Omarchy accepts settings changes and requests disk writes through its scoped API. The plugin cannot confirm the disk write. A refused change keeps the draft open.

## Operator acceptance

The user owns approved company exit ranges and the choice of policy.

1. Install after reviewing the public source, enter real policy addresses.
2. Compare widget and browser against the same endpoint and proxy path.
3. Confirm known passing and failing exits, unavailable service, and settings persistence after shell restart.
4. Check suspend/resume expiry, full keyboard navigation, and multi-monitor dismissal.

Offline or synthetic desktop tests cannot close this company-path gate.

## Limits and decisions

- Prefer a whitelist when approved exits are known. Blacklists accept every unlisted exit.
- One HTTP request samples one address family, not all app traffic.
- Browser and shell proxy paths may differ. Report differences, do not change local routing to make the indicator pass.
- Provider failures produce unknown; no silent fallback or HTML scraping.
- Keep plugin installation user-owned, no privileged hooks or persistent IP history.

No VPN control, kill switch, DNS leak test, dual-stack leak audit, geolocation, or guarantee that all traffic is protected.
