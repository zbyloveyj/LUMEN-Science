# LUMEN Science 0.2.4 — 编辑保护与交互修复

- 修复必填项为空时无法取消新建弹窗的问题。
- 修复取消切换项目或会话时，下拉选择与实际内容不一致的问题。
- 报告离开页面、切换报告或导出项目前自动保存；保存失败时不继续切换。
- 报告未打开时禁用编辑，显示修改及保存状态。
- Ctrl/Cmd+S 保存当前 Notebook、报告或设置；Notebook 导出前先保存编辑代码。
- 保存模型设置前校验基础地址，拒绝无效地址时保留旧配置和密钥。
- 增加真实桌面交互检查脚本 scripts/smoke_ui.py。

延续 0.2.3 的窗口状态记忆和设置布局改进。覆盖安装前请退出工作台，当前仍为桌面预览版。

## 下载与使用

- **Windows 10/11 x64 安装版**：下载 `windows-x64-setup.exe`，双击安装。
- **Windows 便携版**：下载 `windows-x64-portable.zip`，完整解压，打开 `LUMENScience.exe`。系统需有 WebView2 Runtime。
- **macOS/Linux/开发者**：下载 source.zip 或克隆仓库，按 README 安装 Python 依赖并运行。

Windows 包包含 Python、pandas、NumPy、SciPy、Matplotlib、openpyxl、Jupyter 内核及 SSH 依赖。R、C/C++、Java、Node.js 等仍需安装对应工具。在线 AI 需配置自己的模型接口和密钥，离线数据分析不需要密钥。

项目和设置默认在 `%LOCALAPPDATA%\LUMENScience`；升级/卸载保留资料。便携包指程序无需安装，数据仍在用户目录。当前使用手动下载安装包升级。

## 验证与边界

发布流程在完成源码测试、无系统 Python 的打包运行检查、安装后运行检查及卸载保留文件检查后上传资产。发布资产中的 smoke JSON 和 SHA256SUMS.txt 可供核对。自动检查不代表所有图形交互、真实模型和实验室服务器已验收。

此版未做商业代码签名，Windows 可能提示发布者未验证。处于早期预览，不承诺科研结果正确，也没有多人实时协作、远程持久 Notebook 或应用内自动更新。欢迎用合成或可公开数据试用并提交可复现问题。
