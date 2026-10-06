const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const state = vm.createContext({});
vm.runInContext(fs.readFileSync("State.js", "utf8"), state);
assert.equal(state.interval({}), 60);
for (const value of [0, 14, 3601, "60", null, true, 60.5])
    assert.equal(state.interval({intervalSeconds: value}), 0);
for (const value of [15, 60, 3600])
    assert.equal(state.interval({intervalSeconds: value}), value);
assert.equal(state.request({id: "pbjorklund.omaip", intervalSeconds: 60, addresses: "1.1.1.1"}), '{"addresses":"1.1.1.1"}');
const ok = {state: "ok", ip: "1.1.1.1", message: "Allowed", checkedAt: 100};
assert.equal(state.parse(JSON.stringify(ok), 100).state, "ok");
for (const value of ["", "null", "{}", JSON.stringify({...ok, state: "green"}), JSON.stringify({...ok, checkedAt: 200}), JSON.stringify({...ok, ip: ""})])
    assert.equal(state.parse(value, 100).state, "unknown");
assert.equal(state.display(ok, 195, 60).state, "ok");
assert.equal(state.display(ok, 196, 60).state, "unknown");
assert.equal(state.display(ok, 94, 60).state, "unknown");
assert.equal(state.display(ok, 100, 0).state, "unknown");
assert.equal(state.display({...ok, state: "bad"}, 100, 60).state, "bad");
const defaults = {mode: "whitelist", addresses: "", endpoint: "https://api.ipify.org", family: "auto", timeoutSeconds: 8, intervalSeconds: 60};
assert.deepEqual(JSON.parse(JSON.stringify(state.draft({}))), defaults);
const draft = {...defaults, addresses: "203.0.113.42, 2001:db8::/48"};
assert.equal(state.validateDraft(draft), "");
for (const patch of [{mode: "allow"}, {family: "both"}, {addresses: " "}, {addresses: "203.0.113.42,"},
    {endpoint: "http://example.test"}, {endpoint: "https://"}, {endpoint: "https://user@example.test"},
    {endpoint: "https://example.test/#fragment"}, {endpoint: "https://example.test/ bad"}, {endpoint: "https://example.test:0"}, {endpoint: "https://example.test:65536"},
    {timeoutSeconds: 0}, {timeoutSeconds: 31}, {timeoutSeconds: "8"}, {timeoutSeconds: NaN},
    {intervalSeconds: 14}, {intervalSeconds: 3601}, {intervalSeconds: 60.5}])
    assert.notEqual(state.validateDraft({...draft, ...patch}), "", JSON.stringify(patch));
for (const patch of [{timeoutSeconds: 1, intervalSeconds: 15}, {timeoutSeconds: 30, intervalSeconds: 3600},
    {mode: "blacklist", family: "ipv6", endpoint: "https://[2001:db8::1]:443/ip"}])
    assert.equal(state.validateDraft({...draft, ...patch}), "");
// The checker, not the form, parses IP addresses and CIDRs.
assert.equal(state.validateDraft({...draft, addresses: "not-an-ip"}), "");
const original = {id: "pbjorklund.omaip", custom: {keep: true}, addresses: "old", mode: "blacklist"};
const merged = state.mergeDraft(original, draft, "pbjorklund.omaip");
assert.deepEqual(JSON.parse(JSON.stringify(merged)), {...original, ...draft});
assert.equal(original.addresses, "old");
assert.equal(state.mergeDraft({}, draft, "pbjorklund.omaip").id, "pbjorklund.omaip");
assert.equal(state.mergeDraft(original, {...draft, id: "other", custom: "discard"}, "pbjorklund.omaip").custom.keep, true);
assert.equal(state.sameEntry({id: "pbjorklund.omaip", custom: {a: 1, b: [2, 3]}},
    {custom: {b: [2, 3], a: 1}, id: "pbjorklund.omaip"}), true);
assert.equal(state.sameEntry(merged, {...merged, addresses: "changed"}), false);
assert.equal(state.sameEntry({custom: [2, 3]}, {custom: [3, 2]}), false);
assert.equal(state.sameEntry({custom: null}, {custom: {}}), false);
assert.equal(state.sameEntry({custom: 1}, {custom: "1"}), false);
assert.equal(state.sameEntry({id: "pbjorklund.omaip"}, {...draft, id: "pbjorklund.omaip"}), false);
console.log("Widget state checks passed.");
