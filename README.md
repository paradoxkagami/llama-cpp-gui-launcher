# Llama.cpp Server GUI 启动器

一个基于 Python tkinter 的 **llama-server.exe** 图形界面启动器，零依赖，开箱即用。

## 功能特性

- **11 个参数分类 Tab** — 模型加载、上下文推理、GPU 性能、采样参数、KV 缓存、RoPE/YaRN、服务器设置、多模态、日志、投机解码/MTP、附加参数
- **GPU 检测与选择** — 一键检测可用 GPU 设备，支持下拉选择指定 GPU
- **投机解码/MTP 支持** — 支持 draft-mtp（内置 MTP）、draft-simple（独立 draft 模型）、draft-eagle3、ngram 等多种推测解码
- **模型文件/文件夹选择** — 浏览选择 .gguf 模型文件，或选择文件夹后从下拉列表快速切换
- **设置方案管理** — 命名保存、加载、另存为、删除，支持多套配置切换
- **导出/导入** — 设置方案导出为 JSON 文件，可从外部 JSON 导入
- **参数悬浮提示** — 鼠标移到任意参数上显示中文说明
- **命令预览** — 实时显示完整命令行，可一键复制
- **启动/停止** — 在新控制台窗口启动 llama-server，可随时停止
- **打开 WebUI** — 启动后一键打开浏览器访问

## 快速开始

### 1. 前置条件

- 已下载 [llama.cpp](https://github.com/ggml-org/llama.cpp/releases) 的 Windows CUDA 预编译包（如 `llama-bXXXX-bin-win-cuda-12.4-x64.zip`）
- 已下载对应的 CUDA 运行时 DLL 包（`cudart-llama-bin-win-cuda-12.4-x64.zip`），解压到同一目录
- 系统已安装 Python 3.8+（[下载地址](https://www.python.org/downloads/)）

### 2. 安装

将本启动器的两个文件解压到 llama-server.exe 所在目录：

```
llama-bXXXX-bin-win-cuda-12.4-x64/
├── llama-server.exe          ← llama.cpp 主程序
├── ggml-cuda.dll             ← CUDA 后端
├── cudart64_12.dll           ← CUDA 运行时
├── cublas64_12.dll           ← cuBLAS
├── cublasLt64_12.dll         ← cuBLAS Light
├── llama_launcher_gui.py     ← 启动器主程序（本项目）
└── 启动.bat                   ← 双击启动（本项）
```

### 3. 运行

双击 `启动.bat` 即可打开 GUI 界面。

### 4. 基本使用

1. **选择模型** — 在「模型加载」Tab 中点击「浏览」选择 .gguf 模型文件
2. **检测 GPU** — 在「GPU 性能」Tab 中点击「检测」按钮，自动识别 GPU 并填入设备名
3. **设置 GPU 层数** — 确认「GPU 层数」设为 999（全部加载到显存）
4. **启动服务** — 点击底部「启动服务器」按钮
5. **打开 WebUI** — 点击「打开 WebUI」在浏览器中进行对话

## 参数说明

启动器涵盖了 llama-server 的 200+ 参数，按功能分为 10 个 Tab：

| Tab | 说明 |
|---|---|
| 模型加载 | 模型路径、mmap、mlock、LoRA、NUMA 等 |
| 上下文推理 | 上下文长度、批大小、Flash Attention、连续批处理等 |
| GPU 性能 | GPU 层数、设备选择、线程数、分割模式等 |
| 采样参数 | 温度、Top-K/P、Min-P、Mirostat、重复惩罚等 |
| KV 缓存 | K/V 缓存类型、碎片整理 |
| RoPE YaRN | RoPE 缩放、YaRN 上下文扩展 |
| 服务器设置 | 监听地址/端口、API 密钥、SSL、WebUI、聊天模板等 |
| 多模态 | 多模态投影文件、图像输入 |
| 日志 | 日志文件、日志级别、彩色日志等 |
| 附加参数 | 自由输入额外命令行参数 |

每个参数都有悬浮提示，鼠标移上去即可查看中文说明。

## 设置方案

- **保存** — 将当前所有参数保存为命名方案，存储在 `launcher_settings/` 目录
- **加载** — 从下拉列表选择已保存的方案，一键恢复所有参数
- **导出** — 将当前方案导出为独立 JSON 文件，方便备份或分享
- **导入** — 从外部 JSON 文件导入设置方案

## 系统要求

- Windows 10/11 (64-bit)
- Python 3.8+（需包含 tkinter，官方安装包默认包含）
- llama.cpp 预编译包（CUDA 12.4 或 CPU 版本）

## 技术细节

- **零依赖** — 仅使用 Python 内置库（tkinter, json, os, subprocess, webbrowser, glob）
- **单文件** — 所有代码在 `llama_launcher_gui.py` 一个文件中
- **参数参考** — 基于 llama.cpp 官方 GitHub 文档

## 许可证

MIT License

## 致谢

- [llama.cpp](https://github.com/ggml-org/llama.cpp) — Georgi Gerganov 及贡献者
