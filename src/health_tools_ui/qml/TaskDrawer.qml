import QtQuick
import QtQuick.Layouts
import HuskarUI.Basic

HusDrawer {
    id: root
    title: appModel.texts.tasks
    drawerSize: 520
    contentDelegate: Item {
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                HusText {
                    text: appModel.running
                          ? (appModel.locale === "zh_CN" ? "正在运行" : "Running")
                          : (appModel.locale === "zh_CN" ? "队列空闲" : "Queue idle")
                    font.weight: Font.DemiBold
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

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 8
                model: appModel.jobs
                delegate: Rectangle {
                    required property var modelData
                    width: ListView.view.width
                    height: 112
                    radius: 6
                    color: HusTheme.Primary.colorBgLayout
                    border.color: HusTheme.Primary.colorBorder

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        RowLayout {
                            Layout.fillWidth: true
                            HusText { text: modelData.command; font.weight: Font.DemiBold }
                            HusTag {
                                text: modelData.status.toUpperCase()
                                presetColor: modelData.status === "succeeded" ? "green"
                                           : modelData.status === "failed" ? "red"
                                           : modelData.status === "running" ? "blue" : "default"
                            }
                            Item { Layout.fillWidth: true }
                            HusText {
                                text: modelData.createdAt
                                color: HusTheme.Primary.colorTextSecondary
                                font.pixelSize: 11
                            }
                        }
                        HusText {
                            Layout.fillWidth: true
                            text: modelData.outputPath || modelData.argv.join(" ")
                            color: HusTheme.Primary.colorTextSecondary
                            elide: Text.ElideMiddle
                        }
                        RowLayout {
                            Item { Layout.fillWidth: true }
                            HusButton {
                                text: appModel.locale === "zh_CN" ? "恢复参数" : "Restore"
                                onClicked: appModel.restoreJob(modelData.id)
                            }
                            HusButton {
                                text: appModel.locale === "zh_CN" ? "查看日志" : "View log"
                                onClicked: {
                                    appModel.showJobLog(modelData.id);
                                    root.close();
                                }
                            }
                            HusButton {
                                text: appModel.locale === "zh_CN" ? "预览结果" : "Preview"
                                enabled: modelData.outputPath !== ""
                                onClicked: {
                                    appModel.showJobResult(modelData.id);
                                    root.close();
                                }
                            }
                            HusButton {
                                text: appModel.locale === "zh_CN" ? "打开输出" : "Open output"
                                enabled: modelData.outputPath !== ""
                                onClicked: appModel.openJobOutput(modelData.id)
                            }
                            HusButton {
                                text: appModel.locale === "zh_CN" ? "重试" : "Retry"
                                onClicked: appModel.retryJob(modelData.id)
                            }
                        }
                    }
                }
            }
        }
    }
}
