import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import HuskarUI.Basic

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            HusText { text: "全局配置"; font.pixelSize: 22; font.weight: Font.DemiBold }
            Item { Layout.fillWidth: true }
            HusText { text: configModel.dirty ? "有未保存修改" : configModel.status; color: HusTheme.Primary.colorTextSecondary }
            HusIconButton { iconSource: HusIcon.ReloadOutlined; contentDescription: "重新加载"; onClicked: configModel.reload() }
            HusIconButton { text: "保存"; type: HusButton.Type_Primary; iconSource: HusIcon.SaveOutlined; onClicked: configModel.save() }
        }

        HusTabView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            tabType: HusTabView.Type_Card
            initModel: [
                { key: "paths", title: "目录与版本" },
                { key: "yaml", title: "高级 YAML" }
            ]
            contentDelegate: Loader { sourceComponent: index === 0 ? pathsPanel : yamlPanel }
        }
    }

    Component {
        id: pathsPanel
        ScrollView {
            clip: true
            ColumnLayout {
                width: parent.width
                spacing: 12
                RowLayout {
                    Layout.fillWidth: true
                    HusText { Layout.preferredWidth: 130; text: "用户规则目录" }
                    HusInput {
                        Layout.fillWidth: true
                        text: configModel.rulesDir
                        onEditingFinished: configModel.setValue("rules_dir", text)
                    }
                    HusIconButton { iconSource: HusIcon.FolderOpenOutlined; contentDescription: "选择规则目录"; onClicked: configModel.chooseRulesDir() }
                }
                RowLayout {
                    Layout.fillWidth: true
                    HusText { Layout.preferredWidth: 130; text: "离线算法目录" }
                    HusInput {
                        Layout.fillWidth: true
                        text: configModel.offlinePath
                        onEditingFinished: configModel.setValue("offline_tools_path", text)
                    }
                    HusIconButton { iconSource: HusIcon.FolderOpenOutlined; contentDescription: "选择离线目录"; onClicked: configModel.chooseOfflinePath() }
                    HusIconButton { text: "扫描"; iconSource: HusIcon.ReloadOutlined; onClicked: configModel.scanOffline() }
                }
                HusDivider { Layout.fillWidth: true }
                HusText { text: "发现的算法版本"; font.pixelSize: 16; font.weight: Font.DemiBold }
                HusTableView {
                    id: versionTable
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(220, root.height - 270)
                    initModel: configModel.offlineVersions
                    columns: [
                        { title: "", dataIndex: "selection", selectionType: "radio", width: 48 },
                        { title: "芯片", dataIndex: "chip", width: 150 },
                        { title: "分类", dataIndex: "category", width: 180 },
                        { title: "版本", dataIndex: "version", width: 260 },
                        { title: "默认", dataIndex: "defaultLabel", width: 100 }
                    ]
                }
                RowLayout {
                    Layout.fillWidth: true
                    HusText { Layout.fillWidth: true; text: configModel.offlineVersions.length + " 个版本"; color: HusTheme.Primary.colorTextSecondary }
                    HusIconButton {
                        text: "设为默认"
                        iconSource: HusIcon.CheckCircleOutlined
                        enabled: versionTable.checkedKeys.length > 0
                        onClicked: {
                            const parts = versionTable.checkedKeys[0].split(":");
                            configModel.setOfflineDefault(parts.shift(), parts.join(":"));
                        }
                    }
                }
            }
        }
    }

    Component {
        id: yamlPanel
        HusTextArea {
            anchors.fill: parent
            anchors.margins: 8
            text: configModel.source
            textArea.font.family: "Consolas"
            textArea.wrapMode: TextEdit.NoWrap
            onEditingFinished: configModel.setSource(text)
        }
    }
}
