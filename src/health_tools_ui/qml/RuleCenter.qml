import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import HuskarUI.Basic

Item {
    id: root
    property string selectedPointer: ""

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                HusText {
                    text: ruleModel.path === "" ? (appModel.locale === "zh_CN" ? "未保存规则" : "Unsaved rule") : ruleModel.path
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    elide: Text.ElideMiddle
                }
                HusText {
                    text: ruleModel.kind + " · " + ruleModel.status
                    color: HusTheme.Primary.colorTextSecondary
                }
            }
            HusSelect {
                width: 150
                model: ruleModel.kinds.map(kind => ({ label: kind, value: kind }))
                textRole: "label"
                valueRole: "value"
                currentIndex: ruleModel.kinds.indexOf(ruleModel.kind)
                onActivated: ruleModel.newDocument(currentValue)
            }
            HusIconButton { text: appModel.texts.open; iconSource: HusIcon.FolderOpenOutlined; onClicked: ruleModel.openDialog() }
            HusIconButton { text: appModel.texts.validate; iconSource: HusIcon.CheckCircleOutlined; onClicked: ruleModel.validate() }
            HusIconButton { type: HusButton.Type_Primary; text: appModel.texts.save; iconSource: HusIcon.SaveOutlined; onClicked: ruleModel.save() }
        }

        HusTabView {
            id: tabs
            Layout.fillWidth: true
            Layout.fillHeight: true
            tabType: HusTabView.Type_Card
            initModel: [
                { key: "visual", title: appModel.texts.visual },
                { key: "source", title: appModel.texts.source },
                { key: "preview", title: appModel.texts.preview }
            ]
            contentDelegate: Loader {
                sourceComponent: index === 0 ? visualEditor : index === 1 ? sourceEditor : previewEditor
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: ruleModel.issues.length > 0 ? 76 : 42
            radius: 5
            color: ruleModel.issues.length > 0 ? "#18d4380d" : "#1852c41a"
            border.color: ruleModel.issues.length > 0 ? "#d4380d" : "#52c41a"
            HusText {
                anchors.fill: parent
                anchors.margins: 10
                text: ruleModel.issues.length === 0
                      ? (appModel.locale === "zh_CN" ? "验证通过" : "Validation passed")
                      : ruleModel.issues.map(item => "• " + (appModel.locale === "zh_CN" ? item.message_zh : item.message_en)).join("\n")
                wrapMode: Text.Wrap
                elide: Text.ElideRight
            }
        }
    }

    Component {
        id: visualEditor
        Item {
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    HusInput { id: parentPointer; Layout.preferredWidth: 220; placeholderText: "Parent pointer, e.g. /csv" }
                    HusInput { id: childKey; Layout.preferredWidth: 180; placeholderText: "Key (mapping only)" }
                    HusInput { id: childValue; Layout.fillWidth: true; placeholderText: "YAML value, e.g. [] or 25" }
                    HusIconButton {
                        text: appModel.texts.add
                        iconSource: HusIcon.PlusOutlined
                        onClicked: ruleModel.addChild(parentPointer.text, childKey.text, childValue.text)
                    }
                }

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 2
                    model: ruleModel.entries
                    delegate: Rectangle {
                        required property var modelData
                        width: ListView.view.width
                        height: 42
                        color: index % 2 === 0 ? HusTheme.Primary.colorBgLayout : "transparent"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8 + modelData.depth * 20
                            anchors.rightMargin: 8
                            HusText {
                                Layout.preferredWidth: 220
                                text: (modelData.kind === "mapping" ? "▾ " : modelData.kind === "list" ? "▿ " : "") + modelData.key
                                font.weight: modelData.kind === "scalar" ? Font.Normal : Font.DemiBold
                                elide: Text.ElideRight
                            }
                            HusInput {
                                Layout.fillWidth: true
                                visible: modelData.editable
                                text: modelData.value
                                onEditingFinished: ruleModel.setVisualValue(modelData.pointer, text)
                            }
                            HusText {
                                Layout.fillWidth: true
                                visible: !modelData.editable
                                text: modelData.value
                                color: HusTheme.Primary.colorTextSecondary
                            }
                            HusIconButton {
                                iconSource: HusIcon.DeleteOutlined
                                contentDescription: appModel.texts.remove
                                onClicked: ruleModel.removeEntry(modelData.pointer)
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: sourceEditor
        Item {
            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 0

                Rectangle {
                    Layout.preferredWidth: 46
                    Layout.fillHeight: true
                    color: HusTheme.Primary.colorBgLayout
                    HusText {
                        anchors.fill: parent
                        anchors.topMargin: 7
                        anchors.rightMargin: 8
                        horizontalAlignment: Text.AlignRight
                        text: {
                            let lines = [];
                            for (let line = 1; line <= sourceArea.lineCount; line++) lines.push(line);
                            return lines.join("\n");
                        }
                        color: HusTheme.Primary.colorTextSecondary
                        font.family: "Consolas"
                    }
                }

                HusTextArea {
                    id: sourceArea
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    text: ruleModel.source
                    textArea.font.family: "Consolas"
                    textArea.wrapMode: TextEdit.NoWrap
                    onEditingFinished: ruleModel.setSource(text)
                }
            }
        }
    }

    Component {
        id: previewEditor
        Item {
            HusTextArea {
                anchors.fill: parent
                anchors.margins: 8
                readOnly: true
                text: ruleModel.source
                textArea.font.family: "Consolas"
                textArea.wrapMode: TextEdit.NoWrap
            }
        }
    }
}
