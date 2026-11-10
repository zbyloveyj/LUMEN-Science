# LUMEN Science 0.2.2 — Windows desktop preview

这版改进了本机启动、退出和覆盖升级。Windows 默认端口被占用时会自动选择可用端口。同一数据目录的多个启动请求会复用一个服务。窗口加载失败时可从提示切换到浏览器，也可以直接从开始菜单打开 **LUMEN Science (Browser)**。

覆盖安装前，请在工作台侧栏选择 **退出工作台**。项目、设置和运行记录保存在独立的数据目录。发布验收会用 0.2.1 创建并运行项目，然后覆盖安装新版并重新读取项目和运行记录。

开源、本地优先的 AI 科研工作台：项目、对话、多语言计算、数据探索、文献元数据、结果记录与 SSH/SFTP。

## 下载与使用

- **Windows 10/11 x64 安装版**：下载 `windows-x64-setup.exe`，双击安装。
- **Windows 便携版**：下载 `windows-x64-portable.zip`，完整解压，打开 `LUMENScience.exe`。系统需有 WebView2 Runtime。
- **macOS/Linux/开发者**：下载 source.zip 或克隆仓库，按 README 安装 Python 依赖并运行。

Windows 包包含 Python、pandas、NumPy、SciPy、Matplotlib、openpyxl、Jupyter 内核及 SSH 依赖。R、C/C++、Java、Node.js 等仍需安装对应工具。在线 AI 需配置自己的模型接口和密钥，离线数据分析不需要密钥。

项目和设置默认在 `%LOCALAPPDATA%\LUMENScience`；升级/卸载保留资料。便携包指程序无需安装，数据仍在用户目录。当前使用手动下载安装包升级。

## 验证与边界

发布流程在完成源码测试、无系统 Python 的打包运行检查、安装后运行检查及卸载保留文件检查后上传资产。发布资产中的 smoke JSON 和 SHA256SUMS.txt 可供核对。自动检查不代表所有图形交互、真实模型和实验室服务器已验收。

此版未做商业代码签名，Windows 可能提示发布者未验证。处于早期预览，不承诺科研结果正确，也没有多人实时协作、远程持久 Notebook 或应用内自动更新。欢迎用合成或可公开数据试用并提交可复现问题。
