import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import HuskarUI.Basic

Item {
    id: root
    objectName: "ruleCenter"
    property string pendingSaveName: ""
    property string pendingDiscardAction: ""
    property string pendingDiscardPayload: ""
    property string workspaceMode: "library"

    Connections {
        target: ruleModel
        function onSaveNameRequested() { saveNameModal.open(); }
        function onSaveConflict(path) { overwriteModal.description = path; overwriteModal.open(); }
        function onExternalConflict(path) {
            externalConflictModal.description = path;
            externalConflictModal.open();
        }
        function onDiscardConfirmationRequested(action, payload) {
            root.pendingDiscardAction = action;
            root.pendingDiscardPayload = payload;
            discardModal.open();
        }
    }

    ColumnLayout {
        visible: root.workspaceMode === "library"
        anchors.fill: parent
        anchors.margins: 18
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            HusText { text: "规则库"; font.pixelSize: 20; font.weight: Font.DemiBold }
            Item { Layout.fillWidth: true }
            HusSelect {
                id: newRuleKind
                Layout.preferredWidth: 150
                model: ruleModel.kinds.map(kind => ({ label: kind, value: kind }))
                textRole: "label"
                valueRole: "value"
                currentIndex: 0
            }
            HusIconButton {
                text: "新建规则"
                type: HusButton.Type_Primary
                iconSource: HusIcon.PlusOutlined
                onClicked: {
                    generatorModel.setKind(newRuleKind.currentValue);
                    root.workspaceMode = "generator";
                }
            }
            HusIconButton {
                iconSource: HusIcon.ReloadOutlined
                contentDescription: "刷新规则库"
                onClicked: ruleModel.refreshCatalog()
            }
        }

        HusTableView {
            id: ruleLibrary
            Layout.fillWidth: true
            Layout.fillHeight: true
            initModel: ruleModel.catalogEntries
            columns: [
                { title: "", dataIndex: "selection", selectionType: "radio", width: 48 },
                { title: "类型", dataIndex: "type", width: 110 },
                { title: "名称", dataIndex: "name", width: 260 },
                { title: "来源", dataIndex: "sourceLabel", width: 100 },
                { title: "覆盖状态", dataIndex: "overrideLabel", width: 130 },
                { title: "权限", dataIndex: "writableLabel", width: 90 },
                { title: "路径", dataIndex: "path", width: 420 }
            ]
        }

        RowLayout {
            Layout.fillWidth: true
            HusText {
                Layout.fillWidth: true
                text: ruleModel.catalogEntries.length + " 个规则"
                color: HusTheme.Primary.colorTextSecondary
            }
            HusIconButton {
                text: "打开选中规则"
                type: HusButton.Type_Primary
                iconSource: HusIcon.EditOutlined
                enabled: ruleLibrary.checkedKeys.length > 0
                onClicked: {
                    root.workspaceMode = "editor";
                    ruleModel.requestOpenPath(ruleLibrary.checkedKeys[0]);
                }
            }
        }
    }

    RuleGenerator {
        anchors.fill: parent
        visible: root.workspaceMode === "generator"
        onBackRequested: root.workspaceMode = "library"
        onEditAdvanced: function(kind, name, source) {
            ruleModel.loadDraft(kind, name, source);
            root.workspaceMode = "editor";
        }
        onSavedRule: function(path) {
            ruleModel.openPath(path);
            root.workspaceMode = "editor";
        }
    }

    ColumnLayout {
        visible: root.workspaceMode === "editor"
        anchors.fill: parent
        anchors.margins: 18
        spacing: 10

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6
            RowLayout {
                Layout.fillWidth: true
                HusIconButton {
                    iconSource: HusIcon.AppstoreOutlined
                    contentDescription: "返回规则库"
                    onClicked: {
                        if (ruleModel.dirty) discardLibraryModal.open();
                        else root.workspaceMode = "library";
                    }
                }
                HusText {
                    Layout.fillWidth: true
                    text: ruleModel.path === "" ? (appModel.locale === "zh_CN" ? "未保存规则" : "Unsaved rule") : ruleModel.path
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    elide: Text.ElideMiddle
                }
            }
            RowLayout {
                Layout.fillWidth: true
                HusSelect {
                    visible: ruleModel.kind !== "config"
                    Layout.minimumWidth: 150
                    Layout.preferredWidth: 170
                    model: ruleModel.kinds.map(kind => ({ label: kind, value: kind }))
                    textRole: "label"
                    valueRole: "value"
                    currentIndex: ruleModel.kinds.indexOf(ruleModel.kind)
                    onActivated: ruleModel.requestNewDocument(currentValue)
                }
                HusSelect {
                    Layout.minimumWidth: 280
                    Layout.preferredWidth: 360
                    visible: ruleModel.availableRules.length > 0
                    model: ruleModel.availableRules
                    textRole: "label"
                    valueRole: "path"
                    currentIndex: {
                        for (let index = 0; index < ruleModel.availableRules.length; index++) {
                            if (ruleModel.availableRules[index].path === ruleModel.path) return index;
                        }
                        return -1;
                    }
                    placeholderText: appModel.locale === "zh_CN" ? "打开规则库文件" : "Open library rule"
                    onActivated: ruleModel.requestOpenPath(currentValue)
                }
                Item { Layout.fillWidth: true }
                HusIconButton {
                    visible: ruleModel.kind === "config"
                    iconSource: HusIcon.ReloadOutlined
                    contentDescription: appModel.locale === "zh_CN" ? "重新加载配置" : "Reload config"
                    onClicked: ruleModel.requestOpenConfig()
                }
                HusIconButton {
                    visible: ruleModel.kind !== "config"
                    text: appModel.texts.open
                    iconSource: HusIcon.FolderOpenOutlined
                    onClicked: ruleModel.openDialog()
                }
                HusIconButton {
                    visible: ruleModel.kind === "parse" || ruleModel.kind === "convert"
                    text: appModel.locale === "zh_CN" ? "推断列名" : "Infer columns"
                    iconSource: HusIcon.TableOutlined
                    onClicked: ruleModel.inferCsvColumns()
                }
                HusIconButton { text: appModel.texts.validate; iconSource: HusIcon.CheckCircleOutlined; onClicked: ruleModel.validate() }
                HusIconButton { type: HusButton.Type_Primary; text: appModel.texts.save; iconSource: HusIcon.SaveOutlined; onClicked: ruleModel.save() }
                HusText {
                    Layout.minimumWidth: 180
                    Layout.preferredWidth: 260
                    horizontalAlignment: Text.AlignRight
                    text: ruleModel.kind + (ruleModel.dirty ? " · *" : "") + " · " + ruleModel.status
                    color: HusTheme.Primary.colorTextSecondary
                    elide: Text.ElideLeft
                }
            }
        }

        HusTabView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            tabType: HusTabView.Type_Card
            initModel: [
                { key: "form", title: "结构化表单" },
                { key: "visual", title: "高级结构" },
                { key: "source", title: "高级 YAML" },
                { key: "preview", title: appModel.texts.preview }
            ]
            contentDelegate: Loader {
                sourceComponent: index === 0 ? formEditor
                               : index === 1 ? visualEditor
                               : index === 2 ? sourceEditor : previewEditor
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
        id: formEditor
        ScrollView {
            clip: true
            ColumnLayout {
                width: parent.width
                spacing: 8
                Repeater {
                    model: ruleModel.formFields
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: 54
                        HusText { Layout.preferredWidth: 190; text: modelData.label; font.weight: Font.Medium }
                        HusSwitch {
                            visible: !modelData.container && modelData.valueType === "boolean"
                            checked: Boolean(modelData.rawValue)
                            onToggled: {
                                if (checked !== Boolean(modelData.rawValue)) {
                                    ruleModel.setVisualValue(modelData.pointer, checked ? "true" : "false");
                                }
                            }
                        }
                        HusInputNumber {
                            visible: !modelData.container && modelData.valueType === "number"
                            Layout.preferredWidth: 320
                            value: Number(modelData.rawValue)
                            onValueModified: {
                                if (value !== Number(modelData.rawValue)) {
                                    ruleModel.setVisualNumber(modelData.pointer, value);
                                }
                            }
                        }
                        HusInput {
                            visible: !modelData.container && modelData.valueType === "text"
                            Layout.fillWidth: true
                            text: String(modelData.rawValue === null ? "" : modelData.rawValue)
                            onEditingFinished: ruleModel.setVisualValue(modelData.pointer, text)
                        }
                        HusText {
                            visible: modelData.container
                            Layout.fillWidth: true
                            text: modelData.value + " · 请在规则生成中心或高级结构中调整"
                            color: HusTheme.Primary.colorTextSecondary
                        }
                        HusTag { visible: modelData.unsupported; text: "未知字段 · 原样保留"; presetColor: "orange" }
                    }
                }
                Item { Layout.fillHeight: true }
            }
        }
    }

    Component {
        id: visualEditor
        Item {
            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 10

                Rectangle {
                    Layout.preferredWidth: Math.max(330, parent.width * 0.43)
                    Layout.fillHeight: true
                    color: HusTheme.Primary.colorBgLayout
                    border.color: HusTheme.Primary.colorBorder
                    radius: 6

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        RowLayout {
                            Layout.fillWidth: true
                            HusText { text: appModel.locale === "zh_CN" ? "键位树" : "Key tree"; font.weight: Font.DemiBold }
                            Item { Layout.fillWidth: true }
                            HusIconButton {
                                iconSource: HusIcon.PlusSquareOutlined
                                contentDescription: appModel.locale === "zh_CN" ? "全部展开" : "Expand all"
                                onClicked: { ruleModel.setAllExpanded(true); ruleTree.expandAll(); }
                            }
                            HusIconButton {
                                iconSource: HusIcon.MinusSquareOutlined
                                contentDescription: appModel.locale === "zh_CN" ? "全部折叠" : "Collapse all"
                                onClicked: { ruleModel.setAllExpanded(false); ruleTree.collapseAll(); }
                            }
                        }
                        HusTreeView {
                            id: ruleTree
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            blockNode: true
                            showLine: true
                            checkable: false
                            contentDescription: appModel.locale === "zh_CN" ? "规则键位树" : "Rule key tree"
                            initModel: ruleModel.tree
                            onInitModelChanged: {
                                selectedKey = ruleModel.selectedPointer;
                                Qt.callLater(function() { expandForKeys(ruleModel.expandedPointers); });
                            }
                            onSelectedKeyChanged: {
                                if (selectedKey !== ruleModel.selectedPointer) {
                                    ruleModel.selectNode(selectedKey);
                                }
                            }
                            switcherDelegate: HusIconButton {
                                padding: 0
                                leftPadding: 0
                                rightPadding: 0
                                colorBorder: "transparent"
                                iconSource: isExpanded ? HusIcon.MinusSquareOutlined
                                                       : HusIcon.PlusSquareOutlined
                                onClicked: {
                                    ruleModel.setNodeExpanded(treeData.key, !isExpanded);
                                    ruleTree.treeView.toggleExpanded(row);
                                }
                            }
                            nodeContentDelegate: Item {
                                implicitWidth: Math.max(120, ruleTree.width - depth * ruleTree.indent - 42)
                                implicitHeight: 30
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 4
                                    color: isSelected ? HusTheme.Primary.colorFillSecondary : "transparent"
                                }
                                HusText {
                                    anchors.fill: parent
                                    leftPadding: 6
                                    rightPadding: 6
                                    text: treeData.title
                                    font.weight: treeData.kind === "scalar" ? Font.Normal : Font.DemiBold
                                    verticalAlignment: Text.AlignVCenter
                                    elide: Text.ElideMiddle
                                }
                                TapHandler {
                                    onTapped: ruleTree.selectedKey = treeData.key
                                }
                            }
                            Connections {
                                target: ruleModel
                                function onNodeDataChanged(pointer, data) {
                                    const path = ruleModel.treePath(pointer);
                                    if (path.length > 0) ruleTree.setNodeData(ruleTree.index(path), data);
                                }
                                function onDocumentReset() {
                                    Qt.callLater(function() {
                                        ruleTree.selectedKey = ruleModel.selectedPointer;
                                        ruleTree.expandForKeys(ruleModel.expandedPointers);
                                    });
                                }
                                function onSelectionChanged() {
                                    if (ruleTree.selectedKey !== ruleModel.selectedPointer) {
                                        ruleTree.selectedKey = ruleModel.selectedPointer;
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: HusTheme.Primary.colorBgContainer
                    border.color: HusTheme.Primary.colorBorder
                    radius: 6

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 10
                        HusText {
                            Layout.fillWidth: true
                            text: ruleModel.selectedNode.key + " · " + ruleModel.selectedNode.kind
                            font.pixelSize: 16
                            font.weight: Font.DemiBold
                            elide: Text.ElideMiddle
                        }
                        HusText {
                            Layout.fillWidth: true
                            text: ruleModel.selectedNode.pointer || "/"
                            color: HusTheme.Primary.colorTextSecondary
                            elide: Text.ElideMiddle
                        }

                        Loader {
                            Layout.fillWidth: true
                            sourceComponent: ruleModel.selectedNode.editable ? scalarEditor : containerEditor
                        }

                        HusDivider { Layout.fillWidth: true }
                        RowLayout {
                            Layout.fillWidth: true
                            HusIconButton {
                                enabled: ruleModel.selectedPointer !== ""
                                iconSource: HusIcon.ArrowUpOutlined
                                contentDescription: appModel.locale === "zh_CN" ? "上移" : "Move up"
                                onClicked: ruleModel.moveEntry(ruleModel.selectedPointer, -1)
                            }
                            HusIconButton {
                                enabled: ruleModel.selectedPointer !== ""
                                iconSource: HusIcon.ArrowDownOutlined
                                contentDescription: appModel.locale === "zh_CN" ? "下移" : "Move down"
                                onClicked: ruleModel.moveEntry(ruleModel.selectedPointer, 1)
                            }
                            Item { Layout.fillWidth: true }
                            HusIconButton {
                                enabled: ruleModel.selectedPointer !== ""
                                iconSource: HusIcon.DeleteOutlined
                                contentDescription: appModel.texts.remove
                                onClicked: {
                                    ruleModel.removeEntry(ruleModel.selectedPointer);
                                    ruleModel.selectNode("");
                                }
                            }
                        }
                        Item { Layout.fillHeight: true }
                    }
                }
            }
        }
    }

    Component {
        id: scalarEditor
        ColumnLayout {
            HusSwitch {
                visible: ruleModel.selectedNode.valueType === "boolean"
                checked: Boolean(ruleModel.selectedNode.rawValue)
                checkedText: appModel.locale === "zh_CN" ? "是" : "On"
                uncheckedText: appModel.locale === "zh_CN" ? "否" : "Off"
                onToggled: ruleModel.setVisualValue(ruleModel.selectedPointer, checked ? "true" : "false")
            }
            HusInputNumber {
                visible: ruleModel.selectedNode.valueType === "number"
                Layout.fillWidth: true
                precision: Number.isInteger(Number(ruleModel.selectedNode.rawValue)) ? 0 : 4
                value: {
                    const numeric = Number(ruleModel.selectedNode.rawValue);
                    return Number.isFinite(numeric) ? numeric : 0;
                }
                onValueModified: {
                    if (Number.isFinite(value)) {
                        ruleModel.setVisualNumber(ruleModel.selectedPointer, value);
                    } else {
                        ruleModel.refreshDocument();
                    }
                }
            }
            HusInput {
                visible: ruleModel.selectedNode.valueType === "text"
                Layout.fillWidth: true
                text: String(ruleModel.selectedNode.rawValue ?? "")
                onEditingFinished: ruleModel.setVisualValue(ruleModel.selectedPointer, text)
            }
        }
    }

    Component {
        id: containerEditor
        ColumnLayout {
            HusText {
                text: ruleModel.canAddListItem
                      ? (appModel.locale === "zh_CN" ? "添加一个预置列表项" : "Add a templated list item")
                      : (appModel.locale === "zh_CN" ? "选择当前位置支持的键位" : "Choose a supported key")
                color: HusTheme.Primary.colorTextSecondary
            }
            RowLayout {
                Layout.fillWidth: true
                visible: !ruleModel.canAddListItem
                HusSelect {
                    id: supportedKey
                    Layout.fillWidth: true
                    model: ruleModel.availableKeys
                    textRole: "label"
                    valueRole: "value"
                    placeholderText: appModel.locale === "zh_CN" ? "支持的键位" : "Supported keys"
                }
                HusIconButton {
                    type: HusButton.Type_Primary
                    iconSource: HusIcon.PlusOutlined
                    enabled: supportedKey.currentIndex >= 0
                    onClicked: ruleModel.addSuggested(supportedKey.currentValue)
                }
            }
            HusIconButton {
                visible: ruleModel.canAddListItem
                text: appModel.locale === "zh_CN" ? "添加列表项" : "Add list item"
                iconSource: HusIcon.PlusOutlined
                type: HusButton.Type_Primary
                onClicked: ruleModel.addListItem()
            }
            HusCollapse {
                Layout.fillWidth: true
                initModel: [{ key: "custom", title: appModel.locale === "zh_CN" ? "高级：自定义键" : "Advanced: custom key" }]
                contentDelegate: RowLayout {
                    HusInput { id: customKey; Layout.preferredWidth: 150; placeholderText: "key" }
                    HusInput { id: customValue; Layout.fillWidth: true; placeholderText: "YAML value" }
                    HusIconButton {
                        iconSource: HusIcon.PlusOutlined
                        onClicked: ruleModel.addCustom(customKey.text, customValue.text)
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

    HusModal {
        id: discardLibraryModal
        title: "放弃未保存修改？"
        description: "返回规则库会丢失当前尚未保存的修改。"
        confirmText: "放弃修改"
        cancelText: "继续编辑"
        onConfirm: {
            close();
            root.workspaceMode = "library";
        }
        onCancel: close()
    }

    HusModal {
        id: saveNameModal
        title: appModel.locale === "zh_CN" ? "保存到规则库" : "Save to rule library"
        confirmText: appModel.texts.save
        cancelText: appModel.texts.cancel
        bodyDelegate: HusInput {
            id: saveNameInput
            width: 360
            placeholderText: ruleModel.kind + "_custom"
        }
        onConfirm: {
            root.pendingSaveName = saveNameInput.text;
            ruleModel.saveToLibrary(root.pendingSaveName, false);
            close();
        }
        onCancel: close()
    }

    HusModal {
        id: overwriteModal
        title: appModel.locale === "zh_CN" ? "规则已存在" : "Rule already exists"
        description: ""
        confirmText: appModel.locale === "zh_CN" ? "覆盖" : "Overwrite"
        cancelText: appModel.texts.cancel
        onConfirm: { ruleModel.saveToLibrary(root.pendingSaveName, true); close(); }
        onCancel: close()
    }

    HusModal {
        id: discardModal
        title: appModel.locale === "zh_CN" ? "放弃未保存修改？" : "Discard unsaved changes?"
        description: appModel.locale === "zh_CN"
                     ? "当前规则包含未保存修改，继续后无法恢复。"
                     : "The current rule has unsaved changes that cannot be recovered."
        confirmText: appModel.locale === "zh_CN" ? "放弃并继续" : "Discard"
        cancelText: appModel.texts.cancel
        onConfirm: {
            ruleModel.confirmDiscard(root.pendingDiscardAction, root.pendingDiscardPayload);
            close();
        }
        onCancel: close()
    }

    HusModal {
        id: externalConflictModal
        title: appModel.locale === "zh_CN" ? "文件已在外部修改" : "File changed externally"
        description: ""
        confirmText: appModel.locale === "zh_CN" ? "重新加载" : "Reload"
        cancelText: appModel.texts.cancel
        onConfirm: {
            ruleModel.reloadExternal();
            close();
        }
        onCancel: close()
    }
}
