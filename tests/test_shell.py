"""Offline widget wiring test using installed Omarchy controls."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--desktop", action="store_true",
                        help="Show a temporary test bar and the real native popup")
    args = parser.parse_args()
    host = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")) / "shell"
    if not shutil.which("quickshell") or not (host / "Ui").is_dir():
        parser.error("Install Omarchy's Quickshell shell to run this test")
    with tempfile.TemporaryDirectory(prefix="omaip-test-") as name:
        directory = Path(name)
        for filename in ["Widget.qml", "Popup.qml", "State.js"]:
            shutil.copy2(ROOT / filename, directory / filename)
        (directory / "Commons").symlink_to(host / "Commons", target_is_directory=True)
        if args.desktop:
            (directory / "Ui").symlink_to(host / "Ui", target_is_directory=True)
        else:
            shutil.copytree(host / "Ui", directory / "Ui")
            # Only layer-shell window mapping is replaced, controls remain native.
            (directory / "Ui" / "KeyboardPanel.qml").write_text('''import QtQuick
Item {
    required property Item anchorItem
    required property QtObject bar
    property var owner
    property bool open: false
    property Item focusTarget
    property int contentWidth: 420
    property int contentHeight: 600
    width: contentWidth
    height: contentHeight
    visible: open
    function fittedContentWidth(value) { return value; }
    function fittedContentHeight(value) { return Math.min(240, value + 24); }
    onOpenChanged: if (open && focusTarget) focusTarget.forceActiveFocus()
}
''')
        (directory / "checker.py").write_text('''import json, sys, time
settings = json.loads(sys.argv[2])
print(json.dumps({"state": "ok", "ip": settings["addresses"],
                  "message": "Offline fixture", "checkedAt": int(time.time())}))
''')
        qml = '''import QtQuick
import QtQuick.Window
import Quickshell
import qs.Ui
ShellRoot {
    id: test
    property real stage: 0
    property int ticks: 0
    property var saved: null
    property int saves: 0
    property bool refuseSave: false
    function check(value, message) {
        if (!value) { console.error("OMAIP FAIL: " + message); Qt.exit(1); }
    }
    function find(object, name, seen) {
        if (!object || seen.indexOf(object) >= 0) return null;
        seen.push(object);
        if (object.objectName === name) return object;
        for (var key of ["children", "data", "contentItem"]) {
            var list = object[key];
            if (!list) continue;
            if (list.length === undefined) list = [list];
            for (var i = 0; i < list.length; i++) {
                var found = find(list[i], name, seen);
                if (found) return found;
            }
        }
        return null;
    }
    function control(name) {
        var item = find(widget, name, []);
        check(!!item, "Missing control " + name);
        return item;
    }
    QtObject {
        id: persistence
        function updateEntryInline(id, entry) {
            test.check(id === "pbjorklund.omaip", "Wrong settings target");
            if (test.refuseSave) return false;
            test.saved = entry;
            test.saves++;
            return true;
        }
    }
    PluginBarApi {
        id: barApi
        pluginId: "pbjorklund.omaip"
        moduleName: pluginId
        barForeground: "#eeeeee"
        barSize: 32
        fontFamily: "sans-serif"
        shell: persistence
        _requestPopout: function(owner) { barApi.activePopout = owner; }
        _releasePopout: function(owner) { barApi.activePopout = null; }
    }
    PanelWindow {
        implicitWidth: 160
        implicitHeight: 32
        anchors.top: true
        anchors.left: true
        visible: true
        Widget {
            id: widget
            bar: barApi
            settings: ({id: "pbjorklund.omaip", addresses: "8.8.8.8", custom: "keep"})
        }
    }
    Timer {
        interval: 50
        running: true
        repeat: true
        onTriggered: {
            if (++test.ticks > 160) { test.check(false, "Timed out at stage " + test.stage); return; }
            if (test.stage === 0) {
                if (widget.status.state !== "ok") return;
                test.control("omaipThumb").triggerPress(Qt.LeftButton);
                test.check(widget.opened, "Click did not open status");
                test.stage++;
            } else if (test.stage === 1) {
                test.control("omaipSettings").clicked();
                var popup = test.control("omaipPopup");
                test.check(popup.editing, "Settings did not open");
                test.control("omaipAddresses").text = "";
                test.check(!!popup.validationError && !test.control("omaipSave").enabled, "Empty policy accepted");
                test.control("omaipAddresses").text = "1.1.1.1";
                test.control("omaipTimeout").field.contentItem.text = "20";
                test.control("omaipCancel").clicked();
                test.check(widget.settings.addresses === "8.8.8.8" && test.saves === 0, "Cancel saved draft");
                test.control("omaipSettings").clicked();
                test.check(test.control("omaipAddresses").text === "8.8.8.8", "Cancelled draft retained");
                test.check(popup.draft.timeoutSeconds === 8, "Cancelled numeric draft retained");
                test.control("omaipInterval").field.locale = Qt.locale("en_US");
                test.control("omaipInterval").field.contentItem.text = "3,600";
                test.check(popup.draft.intervalSeconds === 3600 && !popup.validationError, "Localized number rejected");
                test.control("omaipAddresses").text = "1.1.1.1";
                test.control("omaipMode").value = "blacklist";
                test.refuseSave = true;
                test.control("omaipSave").clicked();
                test.check(popup.editing && !!popup.saveError && widget.settings.addresses === "8.8.8.8", "Refused save lost draft");
                test.refuseSave = false;
                test.control("omaipSave").clicked();
                test.check(test.saves === 1 && test.saved.custom === "keep" && test.saved.id === "pbjorklund.omaip", "Save dropped fields");
                test.check(!popup.editing && widget.settings.mode === "blacklist" && test.saved.intervalSeconds === 3600, "Save did not update settings");
                test.control("omaipSettings").clicked();
                test.control("omaipSave").clicked();
                test.check(test.saves === 1 && !popup.editing, "Unchanged save wrote settings");
                test.control("omaipSettings").clicked();
                test.control("omaipSave").forceActiveFocus();
                test.stage = 1.5;
            } else if (test.stage === 1.5) {
                var scroll = test.control("omaipScroll");
                var save = test.control("omaipSave");
                if (!save.activeFocus) { save.forceActiveFocus(); return; }
                var top = save.mapToItem(scroll.contentItem, 0, 0).y;
                test.check(top >= scroll.contentY && top + save.height <= scroll.contentY + scroll.height, "Focused Save is clipped");
                test.control("omaipCancel").clicked();
                test.stage = 2;
            } else if (test.stage === 2) {
                if (widget.status.ip !== "1.1.1.1") return;
                test.control("omaipRefresh").clicked();
                test.check(widget.status.state === "unknown", "Refresh retained success");
                test.stage++;
            } else if (test.stage === 3) {
                if (widget.status.state !== "ok") return;
                widget.openSettings();
                barApi.shell = null;
                test.control("omaipAddresses").text = "9.9.9.9";
                test.control("omaipSave").clicked();
                test.check(!!test.control("omaipPopup").saveError && widget.settings.addresses === "1.1.1.1", "Missing API silently saved");
                widget.close();
                test.check(!widget.opened && !test.control("omaipPopup").editing, "Close retained editor");
                console.log("OMAIP SHELL PASS");
                Qt.quit();
            }
        }
    }
}
'''
        if not args.desktop:
            qml = qml.replace("    PanelWindow {", "    Window {").replace("        anchors.top: true\n        anchors.left: true\n", "").replace("implicitWidth: 160", "width: 160").replace("implicitHeight: 32", "height: 32")
        (directory / "shell.qml").write_text(qml)
        env = os.environ.copy()
        if not args.desktop:
            env.update(QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        completed = subprocess.run(["quickshell", "--no-color", "-p", str(directory)],
                                   env=env, capture_output=True, text=True, timeout=15)
        output = completed.stdout + completed.stderr
        if completed.returncode or "OMAIP SHELL PASS" not in output or "TypeError:" in output or "ReferenceError:" in output or "Binding loop" in output:
            raise SystemExit(output)
        print("Native popup controls, validation, cancel, save, refresh, and missing API checks passed.")


if __name__ == "__main__":
    main()
