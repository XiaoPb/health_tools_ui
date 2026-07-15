import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import HuskarUI.Basic

Item {
    id: root
    property bool showAdvanced: false

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                HusText {
                    text: appModel.currentCommand.title
                    font.pixelSize: 22
                    font.weight: Font.DemiBold
                }
                HusText {
                    Layout.fillWidth: true
                    text: appModel.currentCommand.help
                    color: HusTheme.Primary.colorTextSecondary
                    wrapMode: Text.Wrap
                }
            }
            HusSwitch {
                checked: root.showAdvanced
                checkedText: appModel.texts.advanced
                uncheckedText: appModel.texts.basic
                onToggled: root.showAdvanced = checked
            }
            HusIconButton {
                type: HusButton.Type_Primary
                text: appModel.texts.run
                iconSource: HusIcon.PlayCircleOutlined
                onClicked: appModel.runCurrent(false)
            }
        }

        HusDivider { Layout.fillWidth: true }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ColumnLayout {
                width: root.width - 46
                spacing: 8

                Repeater {
                    model: appModel.currentFields
                    delegate: FieldEditor {
                        required property var modelData
                        field: modelData
                        visible: !field.advanced || root.showAdvanced
                        Layout.fillWidth: true
                        Layout.preferredHeight: visible ? implicitHeight : 0
                    }
                }

                Item { Layout.fillWidth: true; Layout.preferredHeight: 20 }
            }
        }

        HusTabView {
            Layout.fillWidth: true
            Layout.preferredHeight: 210
            tabType: HusTabView.Type_Card
            initModel: [
                { key: "log", title: appModel.texts.log },
                { key: "result", title: appModel.locale === "zh_CN" ? "结果预览" : "Result preview" }
            ]
            contentDelegate: Loader {
                sourceComponent: index === 0 ? logPanel : resultPanel
            }
        }
    }

    Component {
        id: logPanel
        Item {
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                RowLayout {
                    Layout.fillWidth: true
                    Item { Layout.fillWidth: true }
                    HusButton {
                        visible: appModel.running
                        text: appModel.texts.cancel
                        type: HusButton.Type_Outlined
                        colorText: "#cf1322"
                        colorBorder: "#cf1322"
                        onClicked: appModel.cancelCurrent()
                    }
                }
                HusTextArea {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    readOnly: true
                    text: appModel.currentLog
                    textArea.font.family: "Consolas"
                    textArea.wrapMode: TextEdit.NoWrap
                    onTextChanged: scrollToEnd()
                }
            }
        }
    }

    Component { id: resultPanel; ResultPreview { } }
}
