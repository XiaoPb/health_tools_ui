import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import HuskarUI.Basic

Item {
    id: root
    property var result: appModel.currentResult

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        HusText {
            visible: root.result.kind !== "none"
            text: root.result.title || ""
            font.weight: Font.DemiBold
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.result.kind === "csv"
            clip: true

            Column {
                spacing: 1
                Row {
                    Repeater {
                        model: root.result.columns || []
                        delegate: Rectangle {
                            required property var modelData
                            width: 150
                            height: 34
                            color: HusTheme.Primary.colorFillSecondary
                            HusText {
                                anchors.fill: parent
                                anchors.margins: 7
                                text: modelData
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
                Repeater {
                    model: root.result.rows || []
                    delegate: Row {
                        required property var modelData
                        Repeater {
                            model: parent.modelData
                            delegate: Rectangle {
                                required property var modelData
                                width: 150
                                height: 32
                                color: index % 2 === 0 ? HusTheme.Primary.colorBgLayout : "transparent"
                                HusText {
                                    anchors.fill: parent
                                    anchors.margins: 7
                                    text: modelData
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }
            }
        }

        GridView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.result.kind === "images"
            model: root.result.items || []
            cellWidth: 260
            cellHeight: 190
            clip: true
            delegate: Item {
                required property var modelData
                width: 250
                height: 180
                Image {
                    anchors.fill: parent
                    anchors.margins: 5
                    source: modelData
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                }
            }
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.result.kind === "files"
            model: root.result.items || []
            clip: true
            delegate: HusText {
                required property var modelData
                width: ListView.view.width
                height: 28
                text: modelData
                elide: Text.ElideMiddle
            }
        }

        HusEmpty {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: ["none", "missing", "error"].indexOf(root.result.kind) >= 0
            description: root.result.kind === "missing"
                         ? (appModel.locale === "zh_CN" ? "输出尚不存在" : "Output does not exist yet")
                         : (appModel.locale === "zh_CN" ? "暂无结果预览" : "No result preview")
        }
    }
}
