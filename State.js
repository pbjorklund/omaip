function interval(settings) {
    var value = settings.intervalSeconds === undefined ? 60 : settings.intervalSeconds;
    return typeof value === "number" && Number.isInteger(value) && value >= 15 && value <= 3600 ? value : 0;
}

function request(settings) {
    var keys = ["mode", "addresses", "endpoint", "family", "timeoutSeconds"];
    var result = {};
    keys.forEach(function(key) {
        if (settings[key] !== undefined) result[key] = settings[key];
    });
    return JSON.stringify(result);
}

function draft(settings) {
    var defaults = {mode: "whitelist", addresses: "", endpoint: "https://api.ipify.org",
                    family: "auto", timeoutSeconds: 8, intervalSeconds: 60};
    var result = {};
    Object.keys(defaults).forEach(function(key) {
        result[key] = settings[key] === undefined ? defaults[key] : settings[key];
    });
    return result;
}

function validateDraft(values) {
    if (["whitelist", "blacklist"].indexOf(values.mode) < 0)
        return "Choose whitelist or blacklist.";
    if (typeof values.addresses !== "string" || !values.addresses.trim() ||
        values.addresses.split(",").some(function(item) { return !item.trim(); }))
        return "Enter at least one IP address or CIDR, separated by commas.";
    if (["auto", "ipv4", "ipv6"].indexOf(values.family) < 0)
        return "Choose auto, IPv4, or IPv6.";
    if (typeof values.endpoint !== "string" ||
        !/^https:\/\/(\[[0-9a-fA-F:]+\]|[a-zA-Z0-9.-]+)(:[0-9]+)?([/?][^#]*)?$/.test(values.endpoint) ||
        /[\s\\{}\x00-\x20\x7f-\uffff]/.test(values.endpoint))
        return "Enter an HTTPS URL without credentials or a fragment.";
    var port = values.endpoint.match(/^https:\/\/(?:\[[^\]]+\]|[^/:]+):([0-9]+)/);
    if (port && (Number(port[1]) < 1 || Number(port[1]) > 65535))
        return "Endpoint port must be from 1 to 65535.";
    if (typeof values.timeoutSeconds !== "number" || !Number.isInteger(values.timeoutSeconds) ||
        values.timeoutSeconds < 1 || values.timeoutSeconds > 30)
        return "Timeout must be an integer from 1 to 30 seconds.";
    if (!interval(values)) return "Poll interval must be an integer from 15 to 3600 seconds.";
    return "";
}

function mergeDraft(settings, values, moduleName) {
    var entry = {};
    Object.keys(settings).forEach(function(key) { entry[key] = settings[key]; });
    if (entry.id === undefined) entry.id = moduleName;
    Object.keys(draft({})).forEach(function(key) { entry[key] = values[key]; });
    return entry;
}

function sameEntry(left, right) {
    if (left === right) return true;
    if (!left || !right || typeof left !== "object" || typeof right !== "object" ||
        Array.isArray(left) !== Array.isArray(right)) return false;
    var leftKeys = Object.keys(left).sort();
    var rightKeys = Object.keys(right).sort();
    return leftKeys.length === rightKeys.length && leftKeys.every(function(key, index) {
        return key === rightKeys[index] && sameEntry(left[key], right[key]);
    });
}

function unknown(message) {
    return {state: "unknown", ip: "", message: message, checkedAt: 0};
}

function parse(text, now) {
    try {
        var result = JSON.parse(text);
        if (["ok", "bad", "unknown"].indexOf(result.state) < 0 ||
            typeof result.ip !== "string" || typeof result.message !== "string" ||
            !Number.isInteger(result.checkedAt) || result.checkedAt <= 0 ||
            result.checkedAt > now + 5 || result.message.length > 256 ||
            result.ip.length > 45 || (result.state !== "unknown" && !result.ip))
            return unknown("Invalid checker result.");
        return result;
    } catch (error) {
        return unknown("Checker did not return a result.");
    }
}

function display(result, now, seconds) {
    if (!seconds) return unknown("Set intervalSeconds to an integer from 15 to 3600.");
    if (result.checkedAt && (now < result.checkedAt - 5 || now - result.checkedAt > seconds + 35))
        return unknown("IP result expired. Use Refresh to check again.");
    return result;
}
