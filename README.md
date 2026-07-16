# Health Tools UI

Health Tools UI 是 [XiaoPb/health_tools](https://github.com/XiaoPb/health_tools) 的
Windows 桌面界面。应用使用 PySide6、QML 和 PyHuskarUI，完整呈现 13 个业务命令，
并提供任务队列、结果预览以及可视化 YAML 规则编辑。

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

命令行 worker 可独立验证：

```powershell
.\scripts\project-uv.ps1 run python -m health_tools_ui --worker "[\"info\", \"sample.csv\"]"
```

## 功能

- 覆盖 parse、plot、classify、convert、info、validate、split、process、factory、
  config、evaluate、offline 和 check。
- 顺序任务队列、实时日志、取消、重试和本地任务历史。
- chip、parse、classify、convert、evaluate 与全局配置的 YAML 可视化编辑。
- 中文/英文界面、浅色/深色主题。
- Windows 安装包与便携 ZIP 发布流程。

外部 `TEE_Algorithm.exe` 不随应用分发。应用会先搜索安装目录的 `offline/`，找不到时
提示用户选择算法目录。

## 许可证

本项目使用 MIT 许可证。PyHuskarUI 使用 Apache-2.0，ghealth-tools 使用 MIT。
