import QtQuick
import QtQuick.Layouts
import HuskarUI.Basic

Item {
    id: root
    required property var field
    implicitHeight: Math.max(52, editorLoader.implicitHeight)
    Layout.fillWidth: true

    RowLayout {
        anchors.fill: parent
        spacing: 12

        ColumnLayout {
            Layout.preferredWidth: 210
            Layout.alignment: Qt.AlignTop
            spacing: 2
            HusText {
                text: root.field.label + (root.field.required ? " *" : "")
                font.weight: Font.Medium
            }
            HusText {
                Layout.fillWidth: true
                text: root.field.help
                color: HusTheme.Primary.colorTextSecondary
                font.pixelSize: 11
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
        }

        Loader {
            id: editorLoader
            Layout.fillWidth: true
            sourceComponent: root.field.kind === "boolean" ? booleanEditor
                           : root.field.name === "plot_type" ? segmentedEditor
                           : root.field.kind === "choice" ? choiceEditor
                           : root.field.kind === "multi_choice" ? multiChoiceEditor
                           : root.field.kind === "integer" || root.field.kind === "number" ? numberEditor
                           : root.field.kind === "path" ? pathEditor
                           : textEditor
        }
    }

    Component {
        id: textEditor
        HusInput {
            anchors.left: parent ? parent.left : undefined
            anchors.right: parent ? parent.right : undefined
            text: {
                appModel.valuesRevision;
                const value = appModel.valuesForUi[root.field.name];
                if (Array.isArray(value)) return value.join(", ");
                return value === undefined || value === null ? "" : String(value);
            }
            placeholderText: root.field.default === null || root.field.default === undefined
                             ? "" : String(root.field.default)
            onEditingFinished: appModel.setValue(root.field.name, text)
        }
    }

    Component {
        id: segmentedEditor
        HusSegmented {
            id: segmentedControl
            width: editorLoader.width
            block: true
            options: root.field.choices
            property bool syncingIndex: false
            function syncIndex() {
                let nextIndex = 0;
                appModel.valuesRevision;
                const current = appModel.valuesForUi[root.field.name];
                for (let index = 0; index < root.field.choices.length; index++) {
                    if (root.field.choices[index].value === current) {
                        nextIndex = index;
                        break;
                    }
                }
                syncingIndex = true;
                currentIndex = nextIndex;
                syncingIndex = false;
            }
            Component.onCompleted: Qt.callLater(syncIndex)
            Connections {
                target: appModel
                function onValuesChanged() { Qt.callLater(segmentedControl.syncIndex); }
            }
            onCurrentIndexChanged: {
                const value = String(currentValue);
                const current = String(appModel.valuesForUi[root.field.name]);
                if (!syncingIndex && currentIndex >= 0 && value !== current) {
                    appModel.setStringValue(String(root.field.name), value);
                }
            }
        }
    }

    Component {
        id: booleanEditor
        HusSwitch {
            checked: {
                appModel.valuesRevision;
                return Boolean(appModel.valuesForUi[root.field.name]);
            }
            checkedText: appModel.locale === "zh_CN" ? "是" : "On"
            uncheckedText: appModel.locale === "zh_CN" ? "否" : "Off"
            onToggled: appModel.setValue(root.field.name, checked)
        }
    }

    Component {
        id: choiceEditor
        RowLayout {
            width: editorLoader.width
            HusSelect {
                Layout.fillWidth: true
                Layout.minimumWidth: 280
                model: root.field.choices
                textRole: "label"
                valueRole: "value"
                showToolTip: true
                currentIndex: {
                    appModel.valuesRevision;
                    const current = appModel.valuesForUi[root.field.name];
                    for (let index = 0; index < root.field.choices.length; index++) {
                        if (root.field.choices[index].value === current) return index;
                    }
                    return -1;
                }
                onActivated: appModel.setValue(root.field.name, currentValue)
            }
            HusIconButton {
                visible: Boolean(root.field.allow_browse)
                iconSource: HusIcon.FolderOpenOutlined
                contentDescription: appModel.locale === "zh_CN" ? "浏览其他 YAML" : "Browse another YAML"
                onClicked: appModel.browseDynamicField(root.field.name)
            }
        }
    }

    Component {
        id: multiChoiceEditor
        RowLayout {
            width: editorLoader.width
            HusMultiSelect {
                id: multiSelect
                Layout.fillWidth: true
                Layout.minimumWidth: 280
                options: root.field.choices
                textRole: "label"
                valueRole: "value"
                defaultSelectedKeys: {
                    appModel.valuesRevision;
                    const value = appModel.valuesForUi[root.field.name];
                    return Array.isArray(value) ? value : [];
                }
                function syncValue() { appModel.setValue(root.field.name, selectedKeys); }
                function reconcileOptions() {
                    const allowed = root.field.choices.map(item => item.value);
                    if (selectedKeys.some(key => allowed.indexOf(key) < 0)) clearTag();
                }
                onOptionsChanged: Qt.callLater(reconcileOptions)
                onSelect: Qt.callLater(syncValue)
                onDeselect: Qt.callLater(syncValue)
            }
            HusIconButton {
                visible: Boolean(root.field.allow_browse)
                iconSource: HusIcon.FolderOpenOutlined
                contentDescription: appModel.locale === "zh_CN" ? "浏览其他 YAML" : "Browse another YAML"
                onClicked: appModel.browseDynamicField(root.field.name)
            }
        }
    }

    Component {
        id: numberEditor
        HusInputNumber {
            width: Math.min(editorLoader.width, 460)
            precision: root.field.kind === "integer" ? 0 : 4
            value: {
                appModel.valuesRevision;
                const current = appModel.valuesForUi[root.field.name];
                const numeric = Number(current);
                return current === "" || current === null || current === undefined
                       || !Number.isFinite(numeric) ? 0 : numeric;
            }
            onValueModified: {
                if (Number.isFinite(value)) {
                    appModel.setNumericValue(root.field.name, value);
                } else {
                    appModel.refreshValues();
                }
            }
        }
    }

    Component {
        id: pathEditor
        RowLayout {
            width: editorLoader.width
            spacing: 6
            HusInput {
                Layout.fillWidth: true
                text: {
                    appModel.valuesRevision;
                    const value = appModel.valuesForUi[root.field.name];
                    return value === undefined || value === null ? "" : String(value);
                }
                placeholderText: root.field.path_mode === "directory" ? "C:/data" : "C:/data/file.csv"
                onEditingFinished: appModel.setValue(root.field.name, text)
            }
            HusIconButton {
                visible: root.field.path_mode !== "directory"
                iconSource: HusIcon.FileOutlined
                contentDescription: appModel.locale === "zh_CN" ? "选择文件" : "Select file"
                onClicked: appModel.chooseFile(root.field.name, root.field.path_mode === "save")
            }
            HusIconButton {
                visible: root.field.path_mode === "directory" || root.field.path_mode === "any"
                iconSource: HusIcon.FolderOpenOutlined
                contentDescription: appModel.locale === "zh_CN" ? "选择目录" : "Select directory"
                onClicked: appModel.chooseDirectory(root.field.name)
            }
        }
    }
}
