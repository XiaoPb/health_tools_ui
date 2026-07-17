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

                Rectangle {
                    visible: appModel.currentCommand.name === "offline"
                    Layout.fillWidth: true
                    Layout.preferredHeight: visible ? offlineColumn.implicitHeight + 24 : 0
                    radius: 6
                    color: HusTheme.Primary.colorBgLayout
                    border.color: HusTheme.Primary.colorBorder

                    ColumnLayout {
                        id: offlineColumn
                        anchors.fill: parent
                        anchors.margins: 12
                        HusText {
                            text: appModel.locale === "zh_CN" ? "算法版本" : "Algorithm versions"
                            font.weight: Font.DemiBold
                        }
                        HusSegmented {
                            Layout.minimumWidth: 320
                            options: [
                                { label: appModel.locale === "zh_CN" ? "默认版本" : "Default", value: "default" },
                                { label: appModel.locale === "zh_CN" ? "指定版本" : "Selected", value: "selected" },
                                { label: appModel.locale === "zh_CN" ? "全部版本" : "All", value: "all" }
                            ]
                            currentIndex: ["default", "selected", "all"].indexOf(appModel.offlineVersionMode)
                            onCurrentIndexChanged: {
                                if (currentIndex >= 0) appModel.setOfflineVersionMode(currentValue);
                            }
                        }
                        HusMultiSelect {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 360
                            visible: appModel.offlineVersionMode === "selected"
                            enabled: appModel.offlineVersionChoices.length > 0
                            options: appModel.offlineVersionChoices
                            textRole: "label"
                            valueRole: "value"
                            defaultSelectedKeys: appModel.offlineSelectedVersions
                            placeholderText: appModel.locale === "zh_CN" ? "选择一个或多个版本" : "Select one or more versions"
                            function syncVersions() { appModel.setOfflineVersions(selectedKeys); }
                            onSelect: Qt.callLater(syncVersions)
                            onDeselect: Qt.callLater(syncVersions)
                        }
                        HusText {
                            Layout.fillWidth: true
                            visible: appModel.offlineVersionMode === "selected"
                                     && appModel.offlineVersionChoices.length === 0
                            text: appModel.locale === "zh_CN"
                                  ? "未发现算法版本。请在设置中选择离线算法目录，或执行配置扫描。"
                                  : "No algorithm versions found. Select the offline tools directory in Settings or scan the configuration."
                            color: HusTheme.Primary.colorTextSecondary
                            wrapMode: Text.Wrap
                        }
                    }
                }

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
                    HusSpin {
                        visible: appModel.running && appModel.currentProgress.total < 0
                        sizeHint: "small"
                        tip: appModel.currentProgress.message || appModel.currentProgress.stage
                    }
                    HusProgress {
                        visible: appModel.running && appModel.currentProgress.total >= 0
                        Layout.fillWidth: true
                        percent: Math.max(0, appModel.currentProgress.percent)
                        status: HusProgress.Status_Active
                        formatter: () => appModel.currentProgress.message || appModel.currentProgress.stage
                    }
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
