import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import HuskarUI.Basic

Item {
    id: root
    objectName: "ruleGenerator"
    signal backRequested()
    signal editAdvanced(string kind, string name, string source)
    signal savedRule(string path)

    Connections {
        target: generatorModel
        function onWarningConfirmationRequested() { warningModal.open(); }
        function onDraftSaved(path) {
            root.savedRule(path);
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            HusIconButton { iconSource: HusIcon.ArrowLeftOutlined; contentDescription: "返回规则库"; onClicked: root.backRequested() }
            HusText { text: "规则生成中心"; font.pixelSize: 20; font.weight: Font.DemiBold }
            HusSegmented {
                Layout.fillWidth: true
                Layout.maximumWidth: 650
                options: generatorModel.kinds
                currentIndex: generatorModel.kinds.findIndex(item => item.value === generatorModel.kind)
                onCurrentIndexChanged: {
                    if (currentIndex >= 0 && currentValue !== generatorModel.kind) generatorModel.setKind(currentValue);
                }
            }
            Item { Layout.fillWidth: true }
            HusTag { text: generatorModel.busy ? "处理中" : "可编辑"; presetColor: generatorModel.busy ? "blue" : "green" }
        }

        RowLayout {
            Layout.fillWidth: true
            HusInput {
                Layout.fillWidth: true
                text: generatorModel.samplePath
                placeholderText: generatorModel.kind === "parse" ? "选择 LOG 文件" : "选择 CSV 样本"
                onEditingFinished: if (text !== generatorModel.samplePath) generatorModel.loadSample(text)
            }
            HusIconButton { text: "选择样本"; iconSource: HusIcon.FolderOpenOutlined; onClicked: generatorModel.chooseSample() }
            HusButton { visible: generatorModel.busy; text: "取消"; onClicked: generatorModel.cancel() }
        }

        HusProgress {
            visible: generatorModel.busy && generatorModel.progress.total >= 0
            Layout.fillWidth: true
            percent: generatorModel.progress.total > 0
                     ? generatorModel.progress.completed * 100 / generatorModel.progress.total : 0
            formatter: () => generatorModel.progress.message
        }
        HusSpin {
            visible: generatorModel.busy && generatorModel.progress.total < 0
            tip: generatorModel.progress.message || "正在分析样本"
        }

        HusTabView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            tabType: HusTabView.Type_Card
            initModel: [
                { key: "configure", title: "1. 配置" },
                { key: "sample", title: "2. 样本预览" },
                { key: "rule", title: "3. 规则预览" }
            ]
            contentDelegate: Loader {
                sourceComponent: index === 0 ? configurePanel : index === 1 ? samplePanel : rulePanel
            }
        }

        RowLayout {
            Layout.fillWidth: true
            HusText {
                Layout.fillWidth: true
                text: generatorModel.status
                color: HusTheme.Primary.colorTextSecondary
                elide: Text.ElideMiddle
            }
            HusInput { id: draftName; Layout.preferredWidth: 230; text: generatorModel.draftName; placeholderText: "规则文件名.yaml" }
            HusIconButton { text: "生成草稿"; iconSource: HusIcon.BuildOutlined; type: HusButton.Type_Primary; onClicked: generatorModel.generate(draftName.text) }
            HusIconButton { text: "运行预览"; iconSource: HusIcon.PlayCircleOutlined; enabled: !generatorModel.busy; onClicked: generatorModel.preview() }
            HusIconButton {
                text: "高级编辑"
                iconSource: HusIcon.CodeOutlined
                enabled: generatorModel.draftSource !== ""
                onClicked: root.editAdvanced(generatorModel.kind, generatorModel.draftName, generatorModel.draftSource)
            }
            HusIconButton { text: "保存规则"; iconSource: HusIcon.SaveOutlined; type: HusButton.Type_Primary; onClicked: generatorModel.saveDraft(false) }
        }
    }

    Component {
        id: configurePanel
        Loader {
            sourceComponent: generatorModel.kind === "parse" ? parsePanel
                           : generatorModel.kind === "convert" ? convertPanel
                           : generatorModel.kind === "chip" ? chipPanel
                           : generatorModel.kind === "classify" ? classifyPanel
                           : evaluatePanel
        }
    }

    Component {
        id: parsePanel
        ColumnLayout {
            HusText { text: "按组件、标记、语法和字段数分组；异常残行不会参与生成。"; color: HusTheme.Primary.colorTextSecondary }
            HusTableView {
                id: parseGroups
                Layout.fillWidth: true
                Layout.fillHeight: true
                initModel: generatorModel.logCandidates
                defaultCheckedKeys: generatorModel.selectedLogGroups
                columns: [
                    { title: "", dataIndex: "selection", selectionType: "checkbox", width: 48 },
                    { title: "组件", dataIndex: "component", width: 160 },
                    { title: "标记", dataIndex: "marker", width: 120 },
                    { title: "语法", dataIndex: "grammar", width: 120 },
                    { title: "字段", dataIndex: "fieldCount", width: 80 },
                    { title: "有效行", dataIndex: "count", width: 100 },
                    { title: "异常", dataIndex: "anomalyCount", width: 80 },
                    { title: "样本", dataIndex: "sample", width: 520 }
                ]
                onCheckedKeysChanged: generatorModel.setSelectedLogGroups(checkedKeys)
            }
            RowLayout {
                Layout.fillWidth: true
                property int rowIndex: parseGroups.checkedKeys.length > 0
                                       ? generatorModel.logCandidates.findIndex(item => item.key === parseGroups.checkedKeys[0]) : -1
                HusText { text: "选中组列名" }
                HusInput {
                    id: parseColumns
                    Layout.fillWidth: true
                    enabled: parent.rowIndex >= 0
                    text: parent.rowIndex >= 0 ? generatorModel.logCandidates[parent.rowIndex].columns.join(", ") : ""
                    onEditingFinished: if (parent.rowIndex >= 0) generatorModel.updateLogColumns(generatorModel.logCandidates[parent.rowIndex].key, text)
                }
            }
        }
    }

    Component {
        id: convertPanel
        ColumnLayout {
            RowLayout {
                Layout.fillWidth: true
                HusText { text: "目标芯片" }
                HusSelect {
                    id: convertChip
                    Layout.preferredWidth: 260
                    model: generatorModel.chipChoices
                    textRole: "label"
                    valueRole: "value"
                    currentIndex: generatorModel.chipChoices.findIndex(item => item.value === generatorModel.targetChip)
                    onActivated: generatorModel.setTargetChip(currentValue)
                }
                HusText { text: "先由公共 API 生成初始映射，再在下表调整。"; color: HusTheme.Primary.colorTextSecondary }
            }
            HusTableView {
                id: mappingTable
                Layout.fillWidth: true
                Layout.fillHeight: true
                initModel: generatorModel.mappings
                columns: [
                    { title: "", dataIndex: "selection", selectionType: "radio", width: 48 },
                    { title: "源列", dataIndex: "source", width: 300 },
                    { title: "目标列", dataIndex: "target", width: 300 },
                    { title: "状态", dataIndex: "status", width: 140 }
                ]
            }
            RowLayout {
                Layout.fillWidth: true
                property int rowIndex: mappingTable.checkedKeys.length > 0
                                       ? generatorModel.mappings.findIndex(item => item.key === mappingTable.checkedKeys[0]) : -1
                HusText { text: "调整选中行" }
                HusSelect {
                    Layout.fillWidth: true
                    enabled: parent.rowIndex >= 0
                    model: generatorModel.targetColumns
                    textRole: "label"
                    valueRole: "value"
                    currentIndex: parent.rowIndex >= 0
                                  ? generatorModel.targetColumns.findIndex(item => item.value === generatorModel.mappings[parent.rowIndex].target) : -1
                    onActivated: generatorModel.updateMapping(parent.rowIndex, currentValue, mappingEnabled.checked)
                }
                HusSwitch {
                    id: mappingEnabled
                    enabled: parent.rowIndex >= 0
                    checked: parent.rowIndex >= 0 ? generatorModel.mappings[parent.rowIndex].enabled : false
                    checkedText: "启用"
                    uncheckedText: "忽略"
                    onToggled: if (parent.rowIndex >= 0) generatorModel.updateMapping(parent.rowIndex, generatorModel.mappings[parent.rowIndex].target, checked)
                }
            }
        }
    }

    Component {
        id: chipPanel
        ColumnLayout {
            RowLayout {
                Layout.fillWidth: true
                HusSelect { id: chipTemplate; Layout.preferredWidth: 220; model: generatorModel.chipTemplates; textRole: "name"; valueRole: "name"; placeholderText: "常用列模板" }
                HusIconButton { text: "添加模板"; iconSource: HusIcon.PlusOutlined; enabled: chipTemplate.currentIndex >= 0; onClicked: generatorModel.addChipTemplate(chipTemplate.currentValue) }
                HusInput { id: customColumn; Layout.fillWidth: true; placeholderText: "自定义列名，例如 Temperature" }
                HusIconButton { text: "添加列"; iconSource: HusIcon.PlusOutlined; onClicked: { generatorModel.addCustomColumn(customColumn.text, "data"); customColumn.text = ""; } }
            }
            RowLayout {
                Layout.fillWidth: true
                HusInput { id: rangeName; Layout.preferredWidth: 150; placeholderText: "列组名称" }
                HusInput { id: rangePrefix; Layout.fillWidth: true; placeholderText: "范围列前缀，例如 CH" }
                HusInputNumber { id: rangeStart; Layout.preferredWidth: 110; precision: 0; value: 0 }
                HusText { text: "至" }
                HusInputNumber { id: rangeEnd; Layout.preferredWidth: 110; precision: 0; value: 15 }
                HusIconButton { text: "添加范围"; iconSource: HusIcon.PlusOutlined; onClicked: generatorModel.addColumnRange(rangeName.text, rangePrefix.text, rangeStart.value, rangeEnd.value, "data") }
            }
            HusTableView {
                id: chipColumns
                Layout.fillWidth: true
                Layout.fillHeight: true
                initModel: generatorModel.chipGroups
                columns: [
                    { title: "", dataIndex: "selection", selectionType: "radio", width: 48 },
                    { title: "列组", dataIndex: "name", width: 180 },
                    { title: "列定义", dataIndex: "display", width: 430 },
                    { title: "数量", dataIndex: "count", width: 80 },
                    { title: "角色", dataIndex: "role", width: 140 }
                ]
            }
            RowLayout {
                Layout.fillWidth: true
                property int rowIndex: chipColumns.checkedKeys.length > 0
                                       ? generatorModel.chipGroups.findIndex(item => item.key === chipColumns.checkedKeys[0]) : -1
                HusSelect {
                    id: chipRole
                    Layout.preferredWidth: 220
                    enabled: parent.rowIndex >= 0
                    model: ["data", "time", "frame", "acc", "algorithm", "reference", "agc", "ipd", "factory"]
                    currentIndex: parent.rowIndex >= 0 ? model.indexOf(generatorModel.chipGroups[parent.rowIndex].role) : 0
                    onActivated: generatorModel.setChipGroupRole(parent.rowIndex, currentValue)
                }
                Item { Layout.fillWidth: true }
                HusIconButton { iconSource: HusIcon.ArrowUpOutlined; contentDescription: "上移"; enabled: parent.rowIndex > 0; onClicked: generatorModel.moveChipGroup(parent.rowIndex, -1) }
                HusIconButton { iconSource: HusIcon.ArrowDownOutlined; contentDescription: "下移"; enabled: parent.rowIndex >= 0 && parent.rowIndex < generatorModel.chipGroups.length - 1; onClicked: generatorModel.moveChipGroup(parent.rowIndex, 1) }
                HusIconButton { iconSource: HusIcon.DeleteOutlined; contentDescription: "删除"; enabled: parent.rowIndex >= 0; onClicked: generatorModel.removeChipGroup(parent.rowIndex) }
            }
        }
    }

    Component {
        id: classifyPanel
        ScrollView {
            clip: true
            ColumnLayout {
                width: parent.width
                spacing: 12
                HusText { text: "路径/文件名关键词"; font.weight: Font.DemiBold }
                RowLayout {
                    Layout.fillWidth: true
                    HusInput { id: keywordCategory; Layout.preferredWidth: 180; placeholderText: "分类名，例如 sit" }
                    HusInput { id: keywordWords; Layout.fillWidth: true; placeholderText: "关键词，逗号分隔，例如 静坐,sitting" }
                    HusIconButton { iconSource: HusIcon.PlusOutlined; text: "添加"; onClicked: generatorModel.addKeyword(keywordCategory.text, keywordWords.text) }
                }
                Repeater {
                    model: generatorModel.keywordRows
                    delegate: RowLayout {
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        HusText { Layout.fillWidth: true; text: modelData.category + "  ←  " + modelData.words.join(", ") }
                        HusIconButton { iconSource: HusIcon.DeleteOutlined; contentDescription: "删除关键词组"; onClicked: generatorModel.removeKeyword(index) }
                    }
                }
                HusDivider { Layout.fillWidth: true }
                HusText { text: "CSV 数值区间（可与关键词组合）"; font.weight: Font.DemiBold }
                RowLayout {
                    Layout.fillWidth: true
                    HusSelect { id: classifyColumn; Layout.preferredWidth: 240; model: generatorModel.columns; textRole: "label"; valueRole: "value"; placeholderText: "数值列" }
                    HusInput { id: intervalLabel; Layout.preferredWidth: 150; placeholderText: "区间名" }
                    HusInputNumber { id: intervalMin; Layout.preferredWidth: 130; precision: 2; value: 90 }
                    HusText { text: "≤ 值 <" }
                    HusInputNumber { id: intervalMax; Layout.preferredWidth: 130; precision: 2; value: 95 }
                    HusIconButton {
                        iconSource: HusIcon.PlusOutlined
                        onClicked: {
                            generatorModel.setClassifyColumn(classifyColumn.currentValue);
                            generatorModel.addInterval(intervalLabel.text, intervalMin.value, intervalMax.value);
                        }
                    }
                }
                Repeater {
                    model: generatorModel.intervalRows
                    delegate: RowLayout {
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        HusText { Layout.fillWidth: true; text: modelData.label + ": " + modelData.minimum + " ≤ 值 < " + modelData.maximum }
                        HusIconButton { iconSource: HusIcon.DeleteOutlined; contentDescription: "删除区间"; onClicked: generatorModel.removeInterval(index) }
                    }
                }
            }
        }
    }

    Component {
        id: evaluatePanel
        ColumnLayout {
            spacing: 12
            HusSegmented {
                id: evalType
                options: [{ label: "心率 HR", value: "hr" }, { label: "血氧 SpO2", value: "spo2" }]
                currentIndex: generatorModel.evalType === "spo2" ? 1 : 0
            }
            RowLayout {
                Layout.fillWidth: true
                HusText { text: "参考列"; Layout.preferredWidth: 90 }
                HusSelect { id: evalRef; Layout.fillWidth: true; model: generatorModel.columns; textRole: "label"; valueRole: "value"; currentIndex: generatorModel.columns.findIndex(item => item.value === generatorModel.refColumn) }
            }
            RowLayout {
                Layout.fillWidth: true
                HusText { text: "算法输出列"; Layout.preferredWidth: 90 }
                HusSelect { id: evalPred; Layout.fillWidth: true; model: generatorModel.columns; textRole: "label"; valueRole: "value"; currentIndex: generatorModel.columns.findIndex(item => item.value === generatorModel.predColumn) }
            }
            RowLayout {
                HusText { text: "采样率"; Layout.preferredWidth: 90 }
                HusInputNumber { id: evalRate; value: generatorModel.sampleRate; precision: 0 }
                HusIconButton { text: "应用"; type: HusButton.Type_Primary; onClicked: generatorModel.setEvaluateOptions(evalType.currentValue, evalRef.currentValue, evalPred.currentValue, evalRate.value) }
            }
            RowLayout {
                Layout.fillWidth: true
                HusText { text: "评估指标"; Layout.preferredWidth: 90 }
                HusMultiSelect {
                    id: evalMethods
                    Layout.fillWidth: true
                    options: generatorModel.evalMethodChoices
                    textRole: "label"
                    valueRole: "value"
                    defaultSelectedKeys: generatorModel.selectedEvalMethods
                    function syncMethods() { generatorModel.setEvalMethods(selectedKeys); }
                    onSelect: Qt.callLater(syncMethods)
                    onDeselect: Qt.callLater(syncMethods)
                }
            }
            RowLayout {
                HusText { text: "差值阈值"; Layout.preferredWidth: 90 }
                HusInputNumber { id: evalDiff; value: generatorModel.diffThreshold; precision: 2 }
                HusText { text: "静止分钟" }
                HusInputNumber { id: evalStale; value: generatorModel.staleMinutes; precision: 2 }
                HusIconButton { text: "应用阈值"; onClicked: generatorModel.setEvalThresholds(evalDiff.value, evalStale.value) }
            }
            HusText { text: "场景关键词可在数据分类页添加；评估规则会按目录和文件名复用。"; color: HusTheme.Primary.colorTextSecondary }
            Item { Layout.fillHeight: true }
        }
    }

    Component {
        id: samplePanel
        ColumnLayout {
            HusText {
                text: generatorModel.csvProfile.columns
                      ? "编码 " + generatorModel.csvProfile.encoding + " · 分隔符 " + generatorModel.csvProfile.delimiter
                        + " · 表头第 " + generatorModel.csvProfile.headerRow + " 行 · " + generatorModel.csvProfile.columns.length + " 列"
                      : generatorModel.logCandidates.length + " 个日志候选组"
                color: HusTheme.Primary.colorTextSecondary
            }
            HusTableView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: generatorModel.csvProfile.preview !== undefined
                initModel: generatorModel.csvProfile.preview
                           ? generatorModel.csvProfile.preview.map((row, index) => ({ key: String(index), row: row.join(" | ") })) : []
                columns: [{ title: "样本数据", dataIndex: "row", width: 1000 }]
            }
        }
    }

    Component {
        id: rulePanel
        ColumnLayout {
            Repeater {
                model: generatorModel.diagnostics
                delegate: HusText {
                    required property var modelData
                    Layout.fillWidth: true
                    text: (modelData.severity === "error" ? "错误：" : "需确认：") + modelData.message
                    color: modelData.severity === "error" ? "#cf1322" : "#d46b08"
                    wrapMode: Text.Wrap
                }
            }
            HusTextArea {
                Layout.fillWidth: true
                Layout.fillHeight: true
                readOnly: true
                text: generatorModel.draftSource
                textArea.font.family: "Consolas"
                textArea.wrapMode: TextEdit.NoWrap
            }
        }
    }

    HusModal {
        id: warningModal
        title: "确认保存带警告的规则"
        description: generatorModel.diagnostics.filter(item => item.severity === "warning").map(item => "• " + item.message).join("\n")
        confirmText: "确认保存"
        cancelText: "继续调整"
        onConfirm: { close(); generatorModel.saveDraft(true); }
        onCancel: close()
    }
}
