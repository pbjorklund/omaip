import QtQuick
import QtQuick.Window
import qs.Commons
import qs.Ui
import "State.js" as State

Item {
    id: root
    required property var hostWidget
    required property Item anchorItem
    property bool editing: false
    property string saveError: ""
    readonly property var draft: ({
        mode: mode.value, addresses: addresses.text, endpoint: endpoint.text, family: family.value,
        timeoutSeconds: numberValue(timeout), intervalSeconds: numberValue(interval)
    })
    readonly property string validationError: State.validateDraft(draft)

    function numberValue(control) {
        var input = control.field.contentItem;
        if (!input.acceptableInput) return NaN;
        try {
            return control.field.valueFromText(input.text, control.field.locale);
        } catch (error) {
            return NaN;
        }
    }
    function resetNumber(control, value) {
        control.value = typeof value === "number" && Number.isInteger(value) ? value : 0;
        control.field.value = control.value;
        control.field.contentItem.text = control.field.textFromValue(control.value, control.field.locale);
        control.field.contentItem.text = Qt.binding(function() { return control.field.displayText; });
    }
    function ensureFocusVisible(item) {
        if (!item) return;
        var ancestor = item;
        while (ancestor && ancestor !== scroll.contentItem) ancestor = ancestor.parent;
        if (!ancestor) return;
        var top = item.mapToItem(scroll.contentItem, 0, 0).y;
        var margin = Style.spacing.md;
        if (top < scroll.contentY + margin) scroll.contentY = Math.max(0, top - margin);
        else if (top + item.height > scroll.contentY + scroll.height - margin)
            scroll.contentY = Math.min(Math.max(0, scroll.contentHeight - scroll.height),
                                       top + item.height - scroll.height + margin);
    }
    onEditingChanged: scroll.contentY = 0

    function startSettings() {
        var values = State.draft(hostWidget.settings);
        mode.value = values.mode;
        addresses.text = values.addresses;
        endpoint.text = values.endpoint;
        family.value = values.family;
        resetNumber(timeout, values.timeoutSeconds);
        resetNumber(interval, values.intervalSeconds);
        saveError = "";
        editing = true;
        Qt.callLater(function() { if (root.editing) addresses.forceActiveFocus(); });
    }
    function cancelSettings() {
        mode.close();
        family.close();
        editing = false;
        saveError = "";
        Qt.callLater(function() { if (root.hostWidget.opened) refresh.forceActiveFocus(); });
    }
    function saveSettings() {
        saveError = hostWidget.saveDraft(draft);
        if (!saveError) cancelSettings();
    }

    KeyboardPanel {
        id: panel
        anchorItem: root.anchorItem
        bar: root.hostWidget.bar
        owner: root.hostWidget
        open: root.hostWidget.opened
        focusTarget: root.editing ? addresses : refresh
        contentWidth: panel.fittedContentWidth(Style.space(420))
        contentHeight: panel.fittedContentHeight(root.editing ? form.implicitHeight : statusColumn.implicitHeight)

        FocusScope {
            id: focusScope
            anchors.fill: parent
            Connections {
                target: focusScope.Window.window
                function onActiveFocusItemChanged() {
                    Qt.callLater(function() {
                        if (focusScope.Window.window)
                            root.ensureFocusVisible(focusScope.Window.window.activeFocusItem);
                    });
                }
            }
            Keys.priority: Keys.AfterItem
            Keys.onEscapePressed: function(event) {
                if (root.editing) root.cancelSettings();
                else root.hostWidget.close();
                event.accepted = true;
            }

            Flickable {
                id: scroll
                objectName: "omaipScroll"
                anchors.fill: parent
                clip: true
                contentWidth: width
                contentHeight: root.editing ? form.implicitHeight : statusColumn.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height

                Column {
                    id: statusColumn
                    width: parent.width
                    visible: !root.editing
                    spacing: Style.spacing.md

                    Text {
                        width: parent.width
                        textFormat: Text.PlainText
                        text: "External IP: " + (root.hostWidget.status.ip || "unknown")
                        wrapMode: Text.Wrap
                        color: Color.foreground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.body
                        font.bold: true
                    }
                    Text {
                        width: parent.width
                        textFormat: Text.PlainText
                        text: "Policy: " + State.draft(root.hostWidget.settings).mode
                              + "\nResult: " + root.hostWidget.status.state + "\n" + root.hostWidget.status.message
                              + "\nChecked: " + (root.hostWidget.status.checkedAt
                                  ? new Date(root.hostWidget.status.checkedAt * 1000).toLocaleString() : "not available")
                        wrapMode: Text.Wrap
                        color: Color.foreground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.body
                    }
                    Flow {
                        width: parent.width
                        spacing: Style.spacing.md
                        Button {
                            id: refresh
                            objectName: "omaipRefresh"
                            text: "Refresh"
                            focusable: true
                            onClicked: root.hostWidget.refresh()
                        }
                        Button {
                            objectName: "omaipSettings"
                            text: "Settings"
                            focusable: true
                            onClicked: root.startSettings()
                        }
                    }
                }

                Column {
                    id: form
                    width: parent.width
                    visible: root.editing
                    spacing: Style.spacing.md

                    Dropdown {
                        id: mode
                        objectName: "omaipMode"
                        width: parent.width
                        label: "Policy mode"
                        options: ["whitelist", "blacklist"]
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.Wrap
                        text: "IP addresses or CIDRs (comma-separated)"
                        textFormat: Text.PlainText
                        color: Color.foreground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.bodySmall
                    }
                    TextField {
                        id: addresses
                        objectName: "omaipAddresses"
                        width: parent.width
                        Accessible.name: "IP addresses or CIDRs"
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.Wrap
                        text: "HTTPS endpoint"
                        textFormat: Text.PlainText
                        color: Color.foreground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.bodySmall
                    }
                    TextField {
                        id: endpoint
                        objectName: "omaipEndpoint"
                        width: parent.width
                        Accessible.name: "HTTPS endpoint"
                    }
                    Dropdown {
                        id: family
                        objectName: "omaipFamily"
                        width: parent.width
                        label: "Address family"
                        options: [{value: "auto", label: "Auto"}, {value: "ipv4", label: "IPv4"}, {value: "ipv6", label: "IPv6"}]
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.Wrap
                        text: "Timeout (1-30 seconds)"
                        textFormat: Text.PlainText
                        color: Color.foreground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.bodySmall
                    }
                    NumberField {
                        id: timeout
                        objectName: "omaipTimeout"
                        width: parent.width
                        fieldWidth: Math.min(width, Style.spacing.numberFieldWidth)
                        from: 0
                        to: 86400
                        field.Accessible.name: "Timeout (1-30 seconds)"
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.Wrap
                        text: "Poll interval (15-3600 seconds)"
                        textFormat: Text.PlainText
                        color: Color.foreground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.bodySmall
                    }
                    NumberField {
                        id: interval
                        objectName: "omaipInterval"
                        width: parent.width
                        fieldWidth: Math.min(width, Style.spacing.numberFieldWidth)
                        from: 0
                        to: 86400
                        field.Accessible.name: "Poll interval (15-3600 seconds)"
                    }
                    Text {
                        objectName: "omaipValidation"
                        width: parent.width
                        textFormat: Text.PlainText
                        text: root.validationError || root.saveError || "IP addresses and CIDRs are validated on the next check."
                        wrapMode: Text.Wrap
                        color: Color.foreground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.bodySmall
                    }
                    Text {
                        width: parent.width
                        textFormat: Text.PlainText
                        text: "Omarchy saves settings to shell.json; disk writes are not confirmed here."
                        wrapMode: Text.Wrap
                        color: Color.foreground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.bodySmall
                    }
                    Flow {
                        width: parent.width
                        spacing: Style.spacing.md
                        Button {
                            objectName: "omaipSave"
                            text: "Save"
                            focusable: true
                            enabled: !root.validationError
                            onClicked: root.saveSettings()
                        }
                        Button {
                            objectName: "omaipCancel"
                            text: "Cancel"
                            focusable: true
                            onClicked: root.cancelSettings()
                        }
                    }
                }
            }
        }
    }
}
