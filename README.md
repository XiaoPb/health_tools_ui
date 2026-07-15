# Health Tools UI

Health Tools UI 是 [XiaoPb/health_tools](https://github.com/XiaoPb/health_tools) 的
Windows 桌面界面。应用使用 PySide6、QML 和 PyHuskarUI，完整呈现 13 个业务命令，
并提供任务队列、结果预览以及可视化 YAML 规则编辑。

## 开发环境

```powershell
uv sync --group dev
uv run health-tools-ui
```

运行测试：

```powershell
uv run pytest
uv run ruff check .
```

命令行 worker 可独立验证：

```powershell
uv run python -m health_tools_ui --worker "[\"info\", \"sample.csv\"]"
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

