import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "State.js" as State

BarWidget {
    id: root
    moduleName: "pbjorklund.omaip"

    property var result: State.unknown("Waiting for an IP check.")
    property string launchedSettings: ""
    property bool queued: false
    property bool opened: false
    readonly property int pollSeconds: State.interval(settings)
    readonly property string requestJson: State.request(settings)
    readonly property var status: State.display(result, clock.date.getTime() / 1000, pollSeconds)

    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    function open() { opened = true; }
    function close() {
        popup.cancelSettings();
        opened = false;
    }
    function toggle() { opened ? close() : open(); }
    function openSettings() {
        open();
        popup.startSettings();
    }
    function saveDraft(draft) {
        var error = State.validateDraft(draft);
        if (error) return error;
        if (!bar || !bar.shell || typeof bar.shell.updateEntryInline !== "function")
            return "Settings cannot be saved: this shell has no inline settings API.";
        var entry = State.mergeDraft(settings, draft, moduleName);
        if (State.sameEntry(settings, entry)) return "";
        try {
            if (bar.shell.updateEntryInline(moduleName, entry) !== true)
                return "Omarchy did not accept the changed settings. Your draft is still open.";
        } catch (error) {
            return "Settings could not be saved by the shell. Try again.";
        }
        settings = entry;
        return "";
    }

    function refresh() {
        result = State.unknown("Checking external IP...");
        if (!pollSeconds) return;
        if (checker.running) {
            queued = true;
            return;
        }
        queued = false;
        launchedSettings = requestJson;
        checker.command = ["python3", decodeURIComponent(Qt.resolvedUrl("checker.py").toString().replace(/^file:\/\//, "")),
                           "--settings", launchedSettings];
        checker.running = true;
    }

    onSettingsChanged: {
        result = State.unknown("Settings changed. Waiting for a fresh check.");
        Qt.callLater(root.refresh);
    }
    Component.onCompleted: Qt.callLater(root.refresh)

    SystemClock {
        id: clock
        precision: SystemClock.Seconds
    }

    Timer {
        interval: Math.max(15, root.pollSeconds) * 1000
        running: root.pollSeconds > 0
        repeat: true
        onTriggered: {
            if (!checker.running) root.refresh();
        }
    }

    Process {
        id: checker
        stdout: StdioCollector {
            onStreamFinished: {
                if (!root.queued && root.launchedSettings === root.requestJson)
                    root.result = State.parse(text, Date.now() / 1000);
            }
        }
        onExited: function(exitCode, exitStatus) {
            if (root.queued) Qt.callLater(root.refresh);
            else if (exitCode !== 0 || exitStatus !== 0)
                root.result = State.unknown("Checker process failed. Check Python and curl.");
        }
    }

    Popup {
        id: popup
        objectName: "omaipPopup"
        hostWidget: root
        anchorItem: button
    }

    BarIconButton {
        id: button
        objectName: "omaipThumb"
        anchors.fill: parent
        bar: root.bar
        // Nerd Font outlines, rather than emoji, keep the foreground tint.
        text: root.status.state === "ok" ? "\uf087" : root.status.state === "bad" ? "\uf088" : "?"
        foreground: root.status.state === "bad" ? "#ff5555" : (root.bar ? root.bar.barForeground : Color.foreground)
        tooltipText: "Exit IP: " + (root.status.ip || "unknown") + "\n" + root.status.message
                     + (root.status.checkedAt ? "\nChecked: " + new Date(root.status.checkedAt * 1000).toLocaleTimeString() : "")
                     + "\nClick for status and settings"
        onPressed: function(mouseButton) {
            if (mouseButton === Qt.LeftButton) root.toggle();
            else root.refresh();
        }
    }
}
