import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import HuskarUI.Basic

HusWindow {
    id: window
    width: 1440
    height: 900
    minimumWidth: 1100
    minimumHeight: 700
    visible: true
    title: appModel.texts.appTitle

    property string currentPage: "command"

    function menuModel() {
        return [
            {
                key: "data",
                label: appModel.locale === "zh_CN" ? "数据处理" : "Data processing",
                type: "group",
                menuChildren: [
                    { key: "cmd:parse", label: "Parse · 日志解析" },
                    { key: "cmd:convert", label: "Convert · 格式转换" },
                    { key: "cmd:classify", label: "Classify · 数据分类" },
                    { key: "cmd:split", label: "Split · 数据分割" },
                    { key: "cmd:process", label: "Process · 批量处理" }
                ]
            },
            {
                key: "analysis",
                label: appModel.locale === "zh_CN" ? "分析评估" : "Analysis",
                type: "group",
                menuChildren: [
                    { key: "cmd:plot", label: "Plot · 数据绘图" },
                    { key: "cmd:factory", label: "Factory · 产测计算" },
                    { key: "cmd:evaluate", label: "Evaluate · 指标评估" },
                    { key: "cmd:info", label: "Info · 文件信息" }
                ]
            },
            {
                key: "quality",
                label: appModel.locale === "zh_CN" ? "质量与离线" : "Quality & offline",
                type: "group",
                menuChildren: [
                    { key: "cmd:check", label: "Check · 数据检查" },
                    { key: "cmd:validate", label: "Validate · 规则验证" },
                    { key: "cmd:offline", label: "Offline · 离线跑库" }
                ]
            }
        ]
    }

    Component.onCompleted: {
        HusTheme.darkMode = appModel.darkMode ? HusTheme.Dark : HusTheme.Light;
    }

    Connections {
        target: appModel
        function onDangerousConfirmationRequested() { dangerModal.open(); }
        function onSettingsChanged() {
            HusTheme.darkMode = appModel.darkMode ? HusTheme.Dark : HusTheme.Light;
        }
        function onLocaleChanged() {
            mainMenu.clear();
            const model = window.menuModel();
            for (let index = 0; index < model.length; index++) mainMenu.append(model[index]);
        }
        function onCurrentCommandChanged() {
            mainMenu.gotoMenu("cmd:" + appModel.currentCommand.name);
        }
    }

    Rectangle {
        id: background
        anchors.fill: parent
        anchors.topMargin: window.captionBar.height
        color: HusTheme.Primary.colorBgBase

        RowLayout {
            anchors.fill: parent
            spacing: 0

            Rectangle {
                Layout.preferredWidth: 244
                Layout.fillHeight: true
                color: HusTheme.Primary.colorBgLayout

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 10

                    HusText {
                        Layout.fillWidth: true
                        text: "GHealth Studio"
                        font.pixelSize: 18
                        font.weight: Font.DemiBold
                    }

                    HusInput {
                        id: commandSearch
                        Layout.fillWidth: true
                        placeholderText: appModel.locale === "zh_CN" ? "搜索命令" : "Search commands"
                        iconSource: HusIcon.SearchOutlined
                        onAccepted: {
                            if (appModel.selectBySearch(text)) {
                                window.currentPage = "command";
                                text = "";
                            }
                        }
                    }

                    HusMenu {
                        id: mainMenu
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        defaultMenuWidth: 220
                        defaultSelectedKeys: ["cmd:parse"]
                        initModel: window.menuModel()
                        showEdge: false
                        showToolTip: true
                        onClickMenu: function(deep, key, keyPath, data) {
                            if (key.indexOf("cmd:") === 0) {
                                appModel.selectCommand(key.substring(4));
                                window.currentPage = "command";
                            } else if (key === "rules") {
                                window.currentPage = "rules";
                            } else if (key === "settings") {
                                window.currentPage = "settings";
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        HusButton {
                            Layout.fillWidth: true
                            text: appModel.texts.rules
                            onClicked: window.currentPage = "rules"
                        }
                        HusButton {
                            Layout.fillWidth: true
                            text: "Config · " + (appModel.locale === "zh_CN" ? "全局配置" : "Global config")
                            onClicked: {
                                ruleModel.requestOpenConfig();
                                window.currentPage = "rules";
                            }
                        }
                        HusButton {
                            Layout.fillWidth: true
                            text: appModel.texts.settings
                            onClicked: window.currentPage = "settings"
                        }
                    }

                    HusDivider { Layout.fillWidth: true }

                    RowLayout {
                        Layout.fillWidth: true
                        HusTag {
                            text: appModel.running ? "RUNNING" : "READY"
                            presetColor: appModel.running ? "blue" : "green"
                        }
                        Item { Layout.fillWidth: true }
                        HusIconButton {
                            iconSource: HusIcon.UnorderedListOutlined
                            contentDescription: appModel.texts.tasks
                            onClicked: taskDrawer.open()
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: HusTheme.Primary.colorBgBase

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 58
                        color: HusTheme.Primary.colorBgContainer

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 20
                            anchors.rightMargin: 20
                            HusText {
                                text: window.currentPage === "rules"
                                      ? appModel.texts.rules
                                      : window.currentPage === "settings"
                                        ? appModel.texts.settings
                                        : appModel.currentCommand.title
                                font.pixelSize: 18
                                font.weight: Font.DemiBold
                            }
                            Item { Layout.fillWidth: true }
                            HusText {
                                text: appModel.status
                                color: HusTheme.Primary.colorTextSecondary
                                elide: Text.ElideRight
                                Layout.maximumWidth: 460
                            }
                            HusIconButton {
                                text: appModel.texts.tasks + " (" + appModel.jobs.length + ")"
                                iconSource: HusIcon.UnorderedListOutlined
                                onClicked: taskDrawer.open()
                            }
                        }
                    }

                    HusDivider { Layout.fillWidth: true }

                    Loader {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        sourceComponent: window.currentPage === "rules" ? rulePage
                                       : window.currentPage === "settings" ? settingsPage
                                       : commandPage
                    }
                }
            }
        }
    }

    Component { id: commandPage; CommandPage { } }
    Component { id: rulePage; RuleCenter { } }
    Component { id: settingsPage; SettingsPage { } }

    TaskDrawer { id: taskDrawer }

    HusModal {
        id: dangerModal
        title: appModel.texts.dangerTitle
        description: appModel.texts.dangerBody
        confirmText: appModel.texts.confirm
        cancelText: appModel.texts.cancel
        onConfirm: {
            close();
            appModel.runCurrent(true);
            taskDrawer.open();
        }
        onCancel: close()
    }
}
