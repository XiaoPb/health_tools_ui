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
                           : root.field.kind === "choice" ? choiceEditor
                           : root.field.kind === "path" ? pathEditor
                           : textEditor
        }
    }

    Component {
        id: textEditor
        HusInput {
            width: editorLoader.width
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
        HusSelect {
            width: Math.min(editorLoader.width, 460)
            model: root.field.choices
            textRole: "label"
            valueRole: "value"
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
                iconSource: HusIcon.FileOutlined
                contentDescription: appModel.locale === "zh_CN" ? "选择文件" : "Select file"
                onClicked: appModel.chooseFile(root.field.name, root.field.path_mode === "save")
            }
            HusIconButton {
                iconSource: HusIcon.FolderOpenOutlined
                contentDescription: appModel.locale === "zh_CN" ? "选择目录" : "Select directory"
                onClicked: appModel.chooseDirectory(root.field.name)
            }
        }
    }
}
