# Health Tools UI

Health Tools UI 是 [XiaoPb/health_tools](https://github.com/XiaoPb/health_tools) 的
Windows 桌面界面。应用使用 PySide6、QML 和 PyHuskarUI，完整呈现 13 个业务命令，
并提供任务队列、结果预览、独立全局配置页和傻瓜化规则生成中心。

## 开发环境

项目固定使用 uv 管理的官方 CPython 3.12.12，避免 Conda Python、外部 Qt 与 PyPI
PySide6 wheel 混装。首次使用先安装解释器；该操作不会修改系统 `PATH`：

```powershell
uv python install 3.12.12
```

所有项目命令通过隔离脚本运行。脚本只清理当前子进程中的 Conda/Qt 路径；检测到旧
`.venv` 使用其他解释器时，会将其重建为项目专用环境：

```powershell
.\scripts\project-uv.ps1 sync-local
.\scripts\project-uv.ps1 run health-tools-ui
```

`sync-local` 使用清华 PyPI 镜像安装本地依赖，随后恢复官方 PyPI 锁文件，确保
CI 和发布构建不依赖区域镜像。日常 `run` 不会隐式重新同步；依赖变化后再次执行：

```powershell
.\scripts\project-uv.ps1 sync-local
```

运行测试：

```powershell
.\scripts\project-uv.ps1 run pytest
.\scripts\project-uv.ps1 run ruff check .
```

## 功能

- 覆盖 parse、plot、classify、convert、info、validate、split、process、factory、
  config、evaluate、offline 和 check。
- 顺序任务队列、结构化进度、协作取消、部分结果、重试和本地任务历史。
- Parse 可从 LOG 自动识别组件、标记、数据语法和字段数，并排除截断/线程插入行。
- Convert 可从 CSV 与目标芯片生成初始映射；Chip 支持时间、帧、ACC、算法、参考、
  AGC、Ipd、Rawdata 和自定义范围列模板。
- Classify 支持路径关键词与 CSV 数值区间组合；Evaluate 从样本表头选择参考列、
  算法列、指标和阈值。
- 规则库、结构化表单、公共 API 校验与保存；键位树和 YAML 仅作为高级编辑入口。
- 全局配置独立管理规则目录、Offline 目录、扫描结果、默认版本和高级 YAML。
- 中文/英文界面、浅色/深色主题。
- Windows 安装包与便携 ZIP 发布流程。

外部 `TEE_Algorithm.exe` 不随应用分发。应用会先搜索安装目录的 `offline/`，找不到时
提示用户选择算法目录。离线任务在独立进程运行，其余任务通过工作线程直接调用
`health_tools.api`；取消离线任务时 API 会终止本次任务启动的算法进程。

普通任务和规则预览显示结构化进度。部分文件失败时任务标记为“部分成功”，已完成输出
继续保留；协作取消会保留 API 返回的部分结果，不执行事务回滚。

发布产物使用版本化文件名：`health-tools-ui-<version>-windows-x64.zip` 和
`health-tools-ui-setup-<version>.exe`。

## 许可证

本项目使用 MIT 许可证。PyHuskarUI 使用 Apache-2.0，ghealth-tools 使用 MIT。
