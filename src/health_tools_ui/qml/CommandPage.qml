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
                    model: appModel.currentFields.filter(field => !field.advanced)
                    delegate: FieldEditor {
                        required property var modelData
                        field: modelData
                        visible: !field.advanced || root.showAdvanced
                        Layout.fillWidth: true
                        Layout.preferredHeight: visible ? implicitHeight : 0
                    }
                }

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
                        spacing: 8
                        RowLayout {
                            Layout.fillWidth: true
                            HusText { text: "算法版本"; font.weight: Font.DemiBold }
                            HusTag {
                                text: appModel.offlineCatalogStatus
                                presetColor: appModel.offlineCatalogState === "available" ? "green"
                                           : appModel.offlineCatalogState === "error" ? "red" : "orange"
                            }
                            Item { Layout.fillWidth: true }
                            HusIconButton {
                                iconSource: HusIcon.FolderOpenOutlined
                                contentDescription: "选择离线算法目录"
                                onClicked: appModel.chooseOfflinePath()
                            }
                            HusIconButton {
                                iconSource: HusIcon.ReloadOutlined
                                contentDescription: "重新扫描"
                                onClicked: appModel.rescanOffline()
                            }
                        }
                        HusText {
                            Layout.fillWidth: true
                            text: appModel.offlinePath || "未选择目录"
                            color: HusTheme.Primary.colorTextSecondary
                            elide: Text.ElideMiddle
                        }
                        HusSegmented {
                            Layout.minimumWidth: 320
                            options: [
                                { label: "默认版本", value: "default" },
                                { label: "指定版本", value: "selected" },
                                { label: "全部版本", value: "all" }
                            ]
                            currentIndex: ["default", "selected", "all"].indexOf(appModel.offlineVersionMode)
                            onCurrentIndexChanged: {
                                if (currentIndex >= 0) appModel.setOfflineVersionMode(currentValue);
                            }
                        }
                        HusMultiSelect {
                            id: offlineVersions
                            Layout.fillWidth: true
                            Layout.minimumWidth: 360
                            visible: appModel.offlineVersionMode === "selected"
                            enabled: appModel.offlineVersionChoices.length > 0
                            options: appModel.offlineVersionChoices
                            textRole: "label"
                            valueRole: "value"
                            defaultSelectedKeys: appModel.offlineSelectedVersions
                            placeholderText: "选择一个或多个版本"
                            function syncVersions() { appModel.setOfflineVersions(selectedKeys); }
                            function reconcileOptions() {
                                const allowed = appModel.offlineVersionChoices.map(item => item.value);
                                if (selectedKeys.some(key => allowed.indexOf(key) < 0)) {
                                    clearTag();
                                    appModel.setOfflineVersions([]);
                                }
                            }
                            onOptionsChanged: Qt.callLater(reconcileOptions)
                            onSelect: Qt.callLater(syncVersions)
                            onDeselect: Qt.callLater(syncVersions)
                        }
                        Repeater {
                            model: appModel.offlineVersionChoices
                            delegate: RowLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                HusText { Layout.fillWidth: true; text: modelData.label }
                                HusTag {
                                    text: modelData.executableAvailable ? "EXE 可用" : "EXE 缺失"
                                    presetColor: modelData.executableAvailable ? "green" : "red"
                                }
                            }
                        }
                    }
                }

                Repeater {
                    model: root.showAdvanced
                           ? appModel.currentFields.filter(field => field.advanced) : []
                    delegate: FieldEditor {
                        required property var modelData
                        field: modelData
                        Layout.fillWidth: true
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
