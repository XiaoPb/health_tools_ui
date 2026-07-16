import QtQuick
import QtQuick.Layouts
import HuskarUI.Basic

Item {
    ColumnLayout {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 28
        spacing: 20

        HusText {
            text: appModel.locale === "zh_CN" ? "应用设置" : "Application settings"
            font.pixelSize: 22
            font.weight: Font.DemiBold
        }

        RowLayout {
            HusText { Layout.preferredWidth: 180; text: appModel.locale === "zh_CN" ? "界面语言" : "Language" }
            HusSelect {
                width: 280
                model: [
                    { label: "简体中文", value: "zh_CN" },
                    { label: "English", value: "en" }
                ]
                textRole: "label"
                valueRole: "value"
                currentIndex: appModel.locale === "zh_CN" ? 0 : 1
                onActivated: appModel.setLocale(currentValue)
            }
        }

        RowLayout {
            Layout.fillWidth: true
            HusText { Layout.preferredWidth: 180; text: appModel.locale === "zh_CN" ? "离线算法目录" : "Offline tools" }
            HusInput {
                Layout.fillWidth: true
                text: appModel.offlinePath
                placeholderText: "<install>/offline"
                onEditingFinished: appModel.setOfflinePath(text)
            }
            HusIconButton {
                iconSource: HusIcon.FolderOpenOutlined
                contentDescription: appModel.locale === "zh_CN" ? "选择目录" : "Select directory"
                onClicked: appModel.chooseOfflinePath()
            }
        }

        RowLayout {
            HusText { Layout.preferredWidth: 180; text: appModel.locale === "zh_CN" ? "深色主题" : "Dark theme" }
            HusSwitch {
                checked: appModel.darkMode
                onToggled: appModel.setDarkMode(checked)
            }
        }

        RowLayout {
            HusText { Layout.preferredWidth: 180; text: appModel.locale === "zh_CN" ? "日志级别" : "Log level" }
            HusSelect {
                width: 280
                model: [
                    { label: "Debug", value: "debug" },
                    { label: "Info", value: "info" },
                    { label: "Warning", value: "warning" },
                    { label: "Error", value: "error" }
                ]
                textRole: "label"
                valueRole: "value"
                currentIndex: ["debug", "info", "warning", "error"].indexOf(appModel.logLevel)
                onActivated: appModel.setLogLevel(currentValue)
            }
        }

        HusDivider { Layout.fillWidth: true }

        HusText {
            Layout.fillWidth: true
            text: appModel.locale === "zh_CN"
                  ? "任务历史和界面设置仅保存在本机，不会复制输入健康数据。"
                  : "Task history and UI settings stay on this computer. Input health data is never copied."
            color: HusTheme.Primary.colorTextSecondary
            wrapMode: Text.Wrap
        }
    }
}
