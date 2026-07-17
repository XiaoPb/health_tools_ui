import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import HuskarUI.Basic

Item {
    id: root
    property var result: appModel.currentResult
    property bool hasApiItems: (root.result.apiItems || []).length > 0

    Component {
        id: textCell
        HusText {
            text: String(cellData === undefined || cellData === null ? "" : cellData)
            elide: Text.ElideMiddle
            verticalAlignment: Text.AlignVCenter
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            HusText {
                text: root.result.title || root.result.apiKind || ""
                font.weight: Font.DemiBold
            }
            Repeater {
                model: Object.keys(root.result.summary || {})
                delegate: HusTag {
                    required property var modelData
                    text: modelData.toUpperCase() + ": " + root.result.summary[modelData]
                    presetColor: modelData === "fail" && root.result.summary[modelData] > 0 ? "red"
                               : modelData === "warn" && root.result.summary[modelData] > 0 ? "orange"
                               : "default"
                }
            }
            Item { Layout.fillWidth: true }
        }

        HusTableView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.hasApiItems
            alternatingRow: true
            showRowHeader: false
            columns: [
                { title: "Status", dataIndex: "status", delegate: textCell, width: 80 },
                { title: "Input", dataIndex: "input", delegate: textCell, width: 240 },
                { title: "Output", dataIndex: "output", delegate: textCell, width: 240 },
                { title: "Reason", dataIndex: "reason", delegate: textCell, width: 160 },
                { title: "Rows", dataIndex: "rows", delegate: textCell, width: 70 }
            ]
            initModel: root.result.apiItems || []
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !root.hasApiItems && root.result.kind === "csv"
            clip: true
            Column {
                spacing: 1
                Row {
                    Repeater {
                        model: root.result.columns || []
                        delegate: Rectangle {
                            required property var modelData
                            width: 150; height: 34
                            color: HusTheme.Primary.colorFillSecondary
                            HusText { anchors.fill: parent; anchors.margins: 7; text: modelData; font.weight: Font.DemiBold; elide: Text.ElideRight }
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
                                width: 150; height: 32
                                color: index % 2 === 0 ? HusTheme.Primary.colorBgLayout : "transparent"
                                HusText { anchors.fill: parent; anchors.margins: 7; text: modelData; elide: Text.ElideRight }
                            }
                        }
                    }
                }
            }
        }

        GridView {
            Layout.fillWidth: true; Layout.fillHeight: true
            visible: !root.hasApiItems && root.result.kind === "images"
            model: root.result.items || []; cellWidth: 260; cellHeight: 190; clip: true
            delegate: Item {
                required property var modelData
                width: 250; height: 180
                Image { anchors.fill: parent; anchors.margins: 5; source: modelData; fillMode: Image.PreserveAspectFit; asynchronous: true }
            }
        }

        ListView {
            Layout.fillWidth: true; Layout.fillHeight: true
            visible: !root.hasApiItems && root.result.kind === "files"
            model: root.result.items || []; clip: true
            delegate: HusText {
                required property var modelData
                width: ListView.view.width; height: 28; text: modelData; elide: Text.ElideMiddle
            }
        }

        HusTextArea {
            Layout.fillWidth: true; Layout.fillHeight: true
            visible: !root.hasApiItems && root.result.kind === "api"
            readOnly: true
            text: JSON.stringify(root.result.apiResult || {}, null, 2)
            textArea.font.family: "Consolas"
        }

        HusEmpty {
            Layout.fillWidth: true; Layout.fillHeight: true
            visible: !root.hasApiItems && ["none", "missing", "error"].indexOf(root.result.kind) >= 0
            description: root.result.kind === "missing"
                         ? (appModel.locale === "zh_CN" ? "输出尚不存在" : "Output does not exist yet")
                         : (appModel.locale === "zh_CN" ? "暂无结果预览" : "No result preview")
        }
    }
}
