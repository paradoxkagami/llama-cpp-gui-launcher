#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Llama.cpp Server GUI 启动器
零依赖，仅使用 Python 内置库（tkinter）
放置在 llama-server.exe 同目录下双击 启动.bat 即可运行
"""

import os
import sys
import json
import glob
import subprocess
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from datetime import datetime


# ============================================================
# 1. Tooltip 悬浮提示类
# ============================================================

class Tooltip:
    """鼠标悬浮在控件上时显示提示文字"""

    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tipwindow = None
        self.id = None
        widget.bind('<Enter>', self._enter, add='+')
        widget.bind('<Leave>', self._leave, add='+')
        widget.bind('<ButtonPress>', self._leave, add='+')

    def _enter(self, event=None):
        self._cancel()
        self.id = self.widget.after(self.delay, self._show)

    def _leave(self, event=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self.id is not None:
            self.widget.after_cancel(self.id)
            self.id = None

    def _show(self):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f'+{x}+{y}')
        # 尝试置顶
        try:
            tw.attributes('-topmost', True)
        except Exception:
            pass
        label = tk.Label(
            tw, text=self.text, justify=tk.LEFT,
            background='#FFFFE0', foreground='#333333',
            relief=tk.SOLID, borderwidth=1,
            font=('Microsoft YaHei UI', 9),
            padx=8, pady=5, wraplength=400
        )
        label.pack()

    def _hide(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


# ============================================================
# 2. 参数定义（按 Tab 分组）
# ============================================================
# 每个参数:
#   arg:      命令行参数名
#   label:    中文显示名
#   type:     entry / checkbox / combobox / spinbox / file / dir
#   default:  默认值
#   tooltip:  中文说明
#   choices:  下拉选项 (combobox)
#   min_val:  最小值 (spinbox)
#   max_val:  最大值 (spinbox)
#   no_arg:   checkbox 为 False 时使用的反向参数 (如 --no-mmap)
#   filetypes: 文件类型过滤器 (file)

PARAM_DEFINITIONS = {
    "模型加载": [
        {
            "arg": "--model", "label": "模型文件", "type": "file",
            "default": "", "filetypes": [("GGUF 模型", "*.gguf"), ("所有文件", "*.*")],
            "tooltip": "模型文件路径（.gguf 格式）。必填项，点击「浏览」选择 .gguf 模型文件。"
        },
        {
            "arg": "--model-dir", "label": "模型文件夹", "type": "dir",
            "default": "", "gui_only": True,
            "tooltip": "模型所在文件夹。选择后可在上方下拉列表中快速切换该文件夹下的 .gguf 文件。此参数仅用于 GUI 浏览，不会传递给 llama-server。"
        },
        {
            "arg": "--alias", "label": "模型别名", "type": "entry",
            "default": "",
            "tooltip": "模型别名，用于 API 返回的 model 字段。逗号分隔可设置多个别名。"
        },
        {
            "arg": "--mmap", "label": "内存映射 (mmap)", "type": "checkbox",
            "default": True, "no_arg": "--no-mmap",
            "tooltip": "是否使用内存映射加载模型。启用可加快加载速度并减少内存占用；禁用则完全加载到内存，加载慢但可能减少 pageout。默认启用。"
        },
        {
            "arg": "--mlock", "label": "锁定内存 (mlock)", "type": "checkbox",
            "default": False,
            "tooltip": "强制模型常驻物理内存，禁止系统 swap 或压缩。可防止模型被换出到磁盘导致推理变慢，但会锁定较多内存。"
        },
        {
            "arg": "--check-tensors", "label": "检查张量", "type": "checkbox",
            "default": False,
            "tooltip": "加载时检查模型张量数据是否包含无效值（NaN/Inf）。启用会增加加载时间。"
        },
        {
            "arg": "--override-kv", "label": "覆盖元数据", "type": "entry",
            "default": "",
            "tooltip": "覆盖模型元数据键值对。格式：KEY=TYPE:VALUE，多个用逗号分隔。\n例：tokenizer.ggml.add_bos_token=bool:false"
        },
        {
            "arg": "--lora", "label": "LoRA 适配器", "type": "file",
            "default": "", "filetypes": [("LoRA 文件", "*.bin *.safetensors"), ("所有文件", "*.*")],
            "tooltip": "LoRA 适配器文件路径，逗号分隔可加载多个。加载后自动应用。"
        },
        {
            "arg": "--lora-scaled", "label": "带缩放 LoRA", "type": "entry",
            "default": "",
            "tooltip": "带自定义缩放系数的 LoRA。格式：FNAME:SCALE,...\n例：lora.bin:0.5,other.bin:1.2"
        },
        {
            "arg": "--control-vector", "label": "控制向量", "type": "file",
            "default": "", "filetypes": [("控制向量", "*.bin"), ("所有文件", "*.*")],
            "tooltip": "添加控制向量文件，用于控制生成风格。逗号分隔可加载多个。"
        },
        {
            "arg": "--numa", "label": "NUMA 优化", "type": "combobox",
            "default": "", "choices": ["", "distribute", "isolate", "numactl"],
            "tooltip": "NUMA 优化策略。\n• distribute: 分配到所有 NUMA 节点\n• isolate: 隔离到单个节点\n• numactl: 使用 numactl 分配\n留空则不启用。"
        },
        {
            "arg": "--direct-io", "label": "DirectIO", "type": "checkbox",
            "default": False, "no_arg": "--no-direct-io",
            "tooltip": "是否使用 DirectIO 加载模型文件（若系统支持）。可绕过系统缓存直接读取磁盘。"
        },
    ],

    "上下文推理": [
        {
            "arg": "--ctx-size", "label": "上下文长度", "type": "spinbox",
            "default": 4096, "min_val": 0, "max_val": 1048576,
            "tooltip": "提示上下文大小（token 数）。0 表示从模型元数据读取。越大可处理越长的对话，但占用更多内存/显存。常用：2048/4096/8192/32768。"
        },
        {
            "arg": "--predict", "label": "预测 token 数", "type": "spinbox",
            "default": -1, "min_val": -2, "max_val": 1048576,
            "tooltip": "生成的最大 token 数。\n• -1 = 无限（直到 EOS）\n• -2 = 填满上下文\n• N = 最多生成 N 个 token"
        },
        {
            "arg": "--batch-size", "label": "批大小 (batch)", "type": "spinbox",
            "default": 2048, "min_val": 1, "max_val": 1048576,
            "tooltip": "prompt 处理时的逻辑最大批大小。影响 prompt 处理速度和内存占用。"
        },
        {
            "arg": "--ubatch-size", "label": "物理批大小 (ubatch)", "type": "spinbox",
            "default": 512, "min_val": 1, "max_val": 1048576,
            "tooltip": "物理最大批大小，影响 GPU 上的单次计算量。通常小于等于 batch-size。"
        },
        {
            "arg": "--keep", "label": "保留 token 数", "type": "spinbox",
            "default": 0, "min_val": -1, "max_val": 1048576,
            "tooltip": "从初始 prompt 中保留的 token 数，不会被上下文移位删除。-1 = 保留全部。"
        },
        {
            "arg": "--parallel", "label": "并行序列数", "type": "spinbox",
            "default": 1, "min_val": 1, "max_val": 256,
            "tooltip": "并行解码的序列数（slot 数）。server 模式下 -1 为自动。增加可同时处理更多请求但占用更多资源。"
        },
        {
            "arg": "--cont-batching", "label": "连续批处理", "type": "checkbox",
            "default": True, "no_arg": "--no-cont-batching",
            "tooltip": "启用连续批处理（动态批处理），可在生成过程中插入新请求，提高吞吐量。默认启用。"
        },
        {
            "arg": "--context-shift", "label": "上下文移位", "type": "checkbox",
            "default": False, "no_arg": "--no-context-shift",
            "tooltip": "无限文本生成时是否使用上下文移位。启用后当上下文满时自动移除旧 token 而非停止生成。"
        },
        {
            "arg": "--flash-attn", "label": "Flash Attention", "type": "combobox",
            "default": "auto", "choices": ["auto", "on", "off"],
            "tooltip": "Flash Attention 模式。\n• auto: 自动检测\n• on: 强制启用（节省显存）\n• off: 禁用"
        },
        {
            "arg": "--cache-prompt", "label": "Prompt 缓存", "type": "checkbox",
            "default": True, "no_arg": "--no-cache-prompt",
            "tooltip": "启用 prompt 缓存，可加速重复请求的响应。默认启用。"
        },
        {
            "arg": "--cache-reuse", "label": "缓存复用块", "type": "spinbox",
            "default": 0, "min_val": 0, "max_val": 1048576,
            "tooltip": "通过 KV shifting 复用缓存的最小块大小。0 = 禁用。需先启用 prompt 缓存。"
        },
        {
            "arg": "--warmup", "label": "预热", "type": "checkbox",
            "default": True, "no_arg": "--no-warmup",
            "tooltip": "启动时执行空运行预热，首次推理更快。默认启用。"
        },
        {
            "arg": "--swa-full", "label": "全尺寸 SWA 缓存", "type": "checkbox",
            "default": False,
            "tooltip": "使用全尺寸 SWA（滑动窗口注意力）缓存。适用于支持 SWA 的模型。"
        },
    ],

    "GPU性能": [
        {
            "arg": "--n-gpu-layers", "label": "GPU 层数", "type": "entry",
            "default": "999",
            "tooltip": "存入 VRAM 的最大层数。\n• 0 = 仅 CPU\n• 999 / all = 全部加载到 GPU\n• auto = 自动\n• N = 加载 N 层到 GPU"
        },
        {
            "arg": "--split-mode", "label": "多 GPU 分割模式", "type": "combobox",
            "default": "layer", "choices": ["layer", "row", "tensor", "none"],
            "tooltip": "多 GPU 分割模式。\n• layer: 按层分割（流水线）\n• row: 按行分割权重（并行）\n• tensor: 张量分割（实验性）\n• none: 单卡"
        },
        {
            "arg": "--main-gpu", "label": "主 GPU 索引", "type": "spinbox",
            "default": 0, "min_val": 0, "max_val": 15,
            "tooltip": "主 GPU 索引。split-mode=none 时用于加载模型，row 时用于中间结果和 KV 缓存。"
        },
        {
            "arg": "--tensor-split", "label": "GPU offload 比例", "type": "entry",
            "default": "",
            "tooltip": "各 GPU 的 offload 比例，逗号分隔。例：3,1 表示 GPU0 分 75%、GPU1 分 25%。"
        },
        {
            "arg": "--device", "label": "GPU 设备", "type": "combobox",
            "default": "", "choices": ["", "CUDA0", "CUDA1", "CUDA0,CUDA1", "none"],
            "tooltip": "指定用于 offload 的 GPU 设备，逗号分隔可多选。\n• CUDA0: 第一个 GPU\n• CUDA1: 第二个 GPU\n• none: 不使用 GPU（仅 CPU）\n留空 = 自动选择。点击「检测」按钮可自动检测可用设备。"
        },
        {
            "arg": "--kv-offload", "label": "KV 缓存 offload", "type": "checkbox",
            "default": True, "no_arg": "--no-kv-offload",
            "tooltip": "是否将 KV 缓存 offload 到 GPU。启用可加速推理但占用更多显存。默认启用。"
        },
        {
            "arg": "--threads", "label": "生成线程数", "type": "spinbox",
            "default": 8, "min_val": -1, "max_val": 256,
            "tooltip": "生成阶段使用的 CPU 线程数。-1 = 自动。建议设置为物理核心数。"
        },
        {
            "arg": "--threads-batch", "label": "批处理线程数", "type": "spinbox",
            "default": 8, "min_val": -1, "max_val": 256,
            "tooltip": "批处理/prompt 处理阶段的线程数。通常与生成线程数相同。"
        },
        {
            "arg": "--threads-http", "label": "HTTP 线程数", "type": "spinbox",
            "default": -1, "min_val": -1, "max_val": 256,
            "tooltip": "HTTP 请求处理线程数。-1 = 自动。仅 server 模式。"
        },
        {
            "arg": "--prio", "label": "进程优先级", "type": "combobox",
            "default": "0", "choices": ["-1", "0", "1", "2", "3"],
            "tooltip": "进程/线程优先级。\n• -1: 低\n• 0: 正常\n• 1: 中\n• 2: 高\n• 3: 实时"
        },
        {
            "arg": "--poll", "label": "轮询级别", "type": "spinbox",
            "default": 50, "min_val": 0, "max_val": 100,
            "tooltip": "等待工作的轮询级别（0-100）。0 = 不轮询（省电但延迟高），100 = 全速轮询（低延迟但耗电）。"
        },
        {
            "arg": "--cpu-moe", "label": "MoE 保留 CPU", "type": "checkbox",
            "default": False,
            "tooltip": "将所有 MoE（混合专家）权重保留在 CPU，仅 attention 等加载到 GPU。可节省显存。"
        },
        {
            "arg": "--op-offload", "label": "操作 offload", "type": "checkbox",
            "default": True, "no_arg": "--no-op-offload",
            "tooltip": "是否将 host 张量操作 offload 到设备。默认启用。"
        },
        {
            "arg": "--override-tensor", "label": "张量覆盖", "type": "entry",
            "default": "",
            "tooltip": "覆盖张量 buffer 类型。格式：pattern=buffer_type,...\n例：blk.0.=CUDA0"
        },
    ],

    "采样参数": [
        {
            "arg": "--seed", "label": "随机种子", "type": "spinbox",
            "default": -1, "min_val": -1, "max_val": 2147483647,
            "tooltip": "随机数种子。-1 = 随机。设置固定种子可复现结果。"
        },
        {
            "arg": "--temp", "label": "温度 (temperature)", "type": "entry",
            "default": "0.8",
            "tooltip": "采样温度，控制生成随机性。越高越随机（如 1.0+），越低越确定（如 0.1）。0 = 贪婪采样。"
        },
        {
            "arg": "--top-k", "label": "Top-K", "type": "spinbox",
            "default": 40, "min_val": 0, "max_val": 2147483647,
            "tooltip": "Top-K 采样，只从概率最高的 K 个 token 中采样。0 = 禁用。常用值 40。"
        },
        {
            "arg": "--top-p", "label": "Top-P", "type": "entry",
            "default": "0.95",
            "tooltip": "Top-P（核采样），从累积概率达到 P 的 token 集合中采样。1.0 = 禁用。常用值 0.9-0.95。"
        },
        {
            "arg": "--min-p", "label": "Min-P", "type": "entry",
            "default": "0.05",
            "tooltip": "Min-P 采样，只保留概率大于最高概率 × Min-P 的 token。0.0 = 禁用。可过滤低质量 token。"
        },
        {
            "arg": "--typical", "label": "典型采样 (typical-p)", "type": "entry",
            "default": "1.0",
            "tooltip": "局部典型采样参数 p。1.0 = 禁用。可减少重复和退化文本。"
        },
        {
            "arg": "--repeat-penalty", "label": "重复惩罚", "type": "entry",
            "default": "1.0",
            "tooltip": "重复序列惩罚因子。>1 惩罚重复，<1 鼓励重复。1.0 = 禁用。常用 1.1-1.3。"
        },
        {
            "arg": "--repeat-last-n", "label": "惩罚窗口", "type": "spinbox",
            "default": 64, "min_val": -1, "max_val": 1048576,
            "tooltip": "重复惩罚考虑的最近 n 个 token。0 = 禁用，-1 = 使用整个上下文。"
        },
        {
            "arg": "--presence-penalty", "label": "存在惩罚", "type": "entry",
            "default": "0.0",
            "tooltip": "重复 alpha 存在惩罚。出现过的 token 概率降低固定值。0.0 = 禁用。"
        },
        {
            "arg": "--frequency-penalty", "label": "频率惩罚", "type": "entry",
            "default": "0.0",
            "tooltip": "重复 alpha 频率惩罚。按出现次数降低概率。0.0 = 禁用。"
        },
        {
            "arg": "--mirostat", "label": "Mirostat 模式", "type": "combobox",
            "default": "0", "choices": ["0", "1", "2"],
            "tooltip": "Mirostat 采样模式。\n• 0: 禁用\n• 1: Mirostat 1.0\n• 2: Mirostat 2.0\n启用时忽略 Top-K/Top-P/Typical。"
        },
        {
            "arg": "--mirostat-lr", "label": "Mirostat 学习率", "type": "entry",
            "default": "0.1",
            "tooltip": "Mirostat 学习率（eta）。控制熵调整速度。常用 0.1。"
        },
        {
            "arg": "--mirostat-ent", "label": "Mirostat 目标熵", "type": "entry",
            "default": "5.0",
            "tooltip": "Mirostat 目标熵（tau）。控制生成多样性。常用 5.0。"
        },
        {
            "arg": "--samplers", "label": "采样器顺序", "type": "entry",
            "default": "",
            "tooltip": "生成时使用的采样器及顺序，分号分隔。\n默认：penalties;dry;top_n_sigma;top_k;typ_p;top_p;min_p;xtc;temperature\n留空使用默认。"
        },
        {
            "arg": "--xtc-probability", "label": "XTC 概率", "type": "entry",
            "default": "0.0",
            "tooltip": "XTC（排除顶部选择）概率。0.0 = 禁用。可增加生成多样性。"
        },
        {
            "arg": "--xtc-threshold", "label": "XTC 阈值", "type": "entry",
            "default": "0.1",
            "tooltip": "XTC 阈值。1.0 = 禁用。只有当次高 token 概率超过此阈值时才触发 XTC。"
        },
        {
            "arg": "--ignore-eos", "label": "忽略 EOS", "type": "checkbox",
            "default": False,
            "tooltip": "忽略 EOS（结束符）token，生成不会自动停止。用于测试或需要固定长度输出时。"
        },
    ],

    "KV缓存": [
        {
            "arg": "--cache-type-k", "label": "K 缓存类型", "type": "combobox",
            "default": "f16", "choices": ["f32", "f16", "bf16", "q8_0", "q4_0", "q4_1", "iq4_nl", "q5_0", "q5_1"],
            "tooltip": "K 缓存数据类型。f16 为默认（精度与速度平衡）。q8_0/q4_0 等量化类型可节省显存但降低精度。"
        },
        {
            "arg": "--cache-type-v", "label": "V 缓存类型", "type": "combobox",
            "default": "f16", "choices": ["f32", "f16", "bf16", "q8_0", "q4_0", "q4_1", "iq4_nl", "q5_0", "q5_1"],
            "tooltip": "V 缓存数据类型。同 K 缓存。量化类型可节省显存但可能影响质量。"
        },
        {
            "arg": "--defrag-thold", "label": "碎片整理阈值", "type": "entry",
            "default": "0.1",
            "tooltip": "KV 缓存碎片整理阈值。碎片超过此比例时触发整理。<0 = 禁用。已弃用，建议使用 --cache-reuse 代替。"
        },
    ],

    "RoPE YaRN": [
        {
            "arg": "--rope-scaling", "label": "RoPE 缩放方法", "type": "combobox",
            "default": "linear", "choices": ["none", "linear", "yarn"],
            "tooltip": "RoPE 频率缩放方法，用于扩展上下文长度。\n• none: 不缩放\n• linear: 线性缩放\n• yarn: YaRN 缩放"
        },
        {
            "arg": "--rope-scale", "label": "RoPE 缩放因子", "type": "entry",
            "default": "",
            "tooltip": "RoPE 上下文缩放因子，按 N 倍扩展上下文。例：2.0 将 4K 上下文扩展到 8K。"
        },
        {
            "arg": "--rope-freq-base", "label": "RoPE 基础频率", "type": "entry",
            "default": "",
            "tooltip": "RoPE 基础频率（NTK 感知缩放使用）。留空则从模型读取。"
        },
        {
            "arg": "--rope-freq-scale", "label": "RoPE 频率缩放", "type": "entry",
            "default": "",
            "tooltip": "RoPE 频率缩放因子，按 1/N 扩展上下文。"
        },
        {
            "arg": "--yarn-orig-ctx", "label": "YaRN 原始上下文", "type": "spinbox",
            "default": 0, "min_val": 0, "max_val": 1048576,
            "tooltip": "YaRN 原始上下文大小。0 = 从模型训练上下文读取。"
        },
        {
            "arg": "--yarn-ext-factor", "label": "YaRN 外推因子", "type": "entry",
            "default": "-1.0",
            "tooltip": "YaRN 外推混合因子。-1 = 自动。0.0 = 完全插值。"
        },
        {
            "arg": "--yarn-attn-factor", "label": "YaRN 注意力因子", "type": "entry",
            "default": "-1.0",
            "tooltip": "YaRN 注意力幅度缩放因子。-1 = 自动。"
        },
    ],

    "服务器设置": [
        {
            "arg": "--host", "label": "监听地址", "type": "entry",
            "default": "127.0.0.1",
            "tooltip": "服务器监听 IP 地址。\n• 127.0.0.1: 仅本机访问\n• 0.0.0.0: 允许外部访问（注意安全）"
        },
        {
            "arg": "--port", "label": "监听端口", "type": "spinbox",
            "default": 8080, "min_val": 1, "max_val": 65535,
            "tooltip": "服务器监听端口。确保端口未被占用。常用 8080。"
        },
        {
            "arg": "--path", "label": "静态文件路径", "type": "dir",
            "default": "",
            "tooltip": "静态文件服务路径。设置后可通过 HTTP 访问该目录下的文件。"
        },
        {
            "arg": "--api-key", "label": "API 密钥", "type": "entry",
            "default": "",
            "tooltip": "API 鉴权密钥。逗号分隔可设置多个。设置后请求需携带 Authorization: Bearer <key>。"
        },
        {
            "arg": "--api-key-file", "label": "API 密钥文件", "type": "file",
            "default": "", "filetypes": [("文本文件", "*.txt"), ("所有文件", "*.*")],
            "tooltip": "含 API 密钥的文件，每行一个，# 开头为注释。"
        },
        {
            "arg": "--ssl-key-file", "label": "SSL 私钥", "type": "file",
            "default": "", "filetypes": [("PEM 文件", "*.pem"), ("所有文件", "*.*")],
            "tooltip": "PEM 编码的 SSL 私钥文件。启用 HTTPS。"
        },
        {
            "arg": "--ssl-cert-file", "label": "SSL 证书", "type": "file",
            "default": "", "filetypes": [("PEM 文件", "*.pem"), ("所有文件", "*.*")],
            "tooltip": "PEM 编码的 SSL 证书文件。启用 HTTPS。"
        },
        {
            "arg": "--timeout", "label": "超时秒数", "type": "spinbox",
            "default": 3600, "min_val": 1, "max_val": 86400,
            "tooltip": "服务器读/写超时时间（秒）。"
        },
        {
            "arg": "--reuse-port", "label": "端口复用", "type": "checkbox",
            "default": False,
            "tooltip": "允许多个 socket 绑定同一端口。用于多实例负载均衡。"
        },
        {
            "arg": "--webui", "label": "Web UI", "type": "checkbox",
            "default": True, "no_arg": "--no-webui",
            "tooltip": "启用内置 Web UI。可通过浏览器访问 http://host:port 进行对话。默认启用。"
        },
        {
            "arg": "--embeddings", "label": "嵌入模式", "type": "checkbox",
            "default": False,
            "tooltip": "仅支持 embedding 用例。仅用于专用嵌入模型（如 bge、e5）。"
        },
        {
            "arg": "--metrics", "label": "Prometheus 指标", "type": "checkbox",
            "default": False,
            "tooltip": "启用 Prometheus 兼容的 /metrics 端点，用于监控。"
        },
        {
            "arg": "--slots", "label": "Slot 监控", "type": "checkbox",
            "default": True, "no_arg": "--no-slots",
            "tooltip": "暴露 /slots 端点用于监控 slot 状态。默认启用。"
        },
        {
            "arg": "--props", "label": "属性修改端点", "type": "checkbox",
            "default": False,
            "tooltip": "允许通过 POST /props 修改全局属性。注意安全风险。"
        },
        {
            "arg": "--chat-template", "label": "聊天模板", "type": "combobox",
            "default": "", "choices": ["", "llama3", "chatml", "mistral-v3", "phi3", "phi4", "gemma", "deepseek", "deepseek2", "deepseek3", "qwen", "vicuna", "zephyr"],
            "tooltip": "自定义聊天模板。留空使用模型内置模板。内置模板：llama3, chatml, mistral-v3, phi3, gemma, qwen 等。"
        },
        {
            "arg": "--jinja", "label": "Jinja 模板引擎", "type": "checkbox",
            "default": True, "no_arg": "--no-jinja",
            "tooltip": "使用 Jinja 模板引擎解析聊天模板。默认启用。"
        },
        {
            "arg": "--reasoning-format", "label": "思维格式", "type": "combobox",
            "default": "auto", "choices": ["auto", "none", "deepseek", "deepseek-legacy"],
            "tooltip": "思维标签处理方式。\n• auto: 自动检测\n• none: 不解析\n• deepseek: 放入 reasoning_content\n• deepseek-legacy: 保留 <think> 标签"
        },
        {
            "arg": "--reasoning-budget", "label": "思考预算", "type": "spinbox",
            "default": -1, "min_val": -1, "max_val": 1048576,
            "tooltip": "思考 token 预算。-1 = 无限制，0 = 立即结束，N>0 = 最多 N 个思考 token。"
        },
        {
            "arg": "--sse-ping-interval", "label": "SSE ping 间隔", "type": "spinbox",
            "default": 30, "min_val": -1, "max_val": 3600,
            "tooltip": "SSE（Server-Sent Events）ping 间隔秒数。-1 = 禁用。"
        },
        {
            "arg": "--sleep-idle-seconds", "label": "空闲休眠", "type": "spinbox",
            "default": -1, "min_val": -1, "max_val": 86400,
            "tooltip": "空闲多少秒后服务器休眠。-1 = 禁用。可省电。"
        },
    ],

    "多模态": [
        {
            "arg": "--mmproj", "label": "多模态投影文件", "type": "file",
            "default": "", "filetypes": [("GGUF 文件", "*.gguf"), ("所有文件", "*.*")],
            "tooltip": "多模态投影文件路径（mmproj）。用于视觉/多模态模型。使用 -hf 下载模型时可省略。"
        },
        {
            "arg": "--mmproj-offload", "label": "投影 GPU offload", "type": "checkbox",
            "default": True, "no_arg": "--no-mmproj-offload",
            "tooltip": "是否对多模态投影启用 GPU offload。默认启用。"
        },
        {
            "arg": "--image", "label": "图像文件", "type": "file",
            "default": "", "filetypes": [("图像文件", "*.jpg *.jpeg *.png *.bmp *.webp"), ("所有文件", "*.*")],
            "tooltip": "输入图像文件路径，逗号分隔多个。仅多模态模型使用。"
        },
        {
            "arg": "--image-min-tokens", "label": "图像最小 token", "type": "spinbox",
            "default": 0, "min_val": 0, "max_val": 1048576,
            "tooltip": "每张图像最小 token 数。0 = 从模型读取。仅动态分辨率视觉模型。"
        },
        {
            "arg": "--image-max-tokens", "label": "图像最大 token", "type": "spinbox",
            "default": 0, "min_val": 0, "max_val": 1048576,
            "tooltip": "每张图像最大 token 数。0 = 从模型读取。仅动态分辨率视觉模型。"
        },
    ],

    "日志": [
        {
            "arg": "--log-file", "label": "日志文件", "type": "file",
            "default": "", "filetypes": [("日志文件", "*.log *.txt"), ("所有文件", "*.*")],
            "tooltip": "将日志输出到指定文件。留空则输出到控制台。"
        },
        {
            "arg": "--log-colors", "label": "彩色日志", "type": "combobox",
            "default": "auto", "choices": ["auto", "on", "off"],
            "tooltip": "彩色日志输出。auto = 终端时启用。"
        },
        {
            "arg": "--verbose", "label": "详尽日志", "type": "checkbox",
            "default": False,
            "tooltip": "输出详尽日志（所有消息），用于调试。"
        },
        {
            "arg": "--log-verbosity", "label": "日志级别", "type": "combobox",
            "default": "3", "choices": ["0", "1", "2", "3", "4", "5"],
            "tooltip": "日志阈值。\n• 0: generic\n• 1: error\n• 2: warning\n• 3: info（默认）\n• 4: trace\n• 5: debug"
        },
        {
            "arg": "--log-prefix", "label": "日志前缀", "type": "checkbox",
            "default": True, "no_arg": "--no-log-prefix",
            "tooltip": "日志消息添加前缀（如时间戳、级别）。"
        },
        {
            "arg": "--log-timestamps", "label": "日志时间戳", "type": "checkbox",
            "default": True, "no_arg": "--no-log-timestamps",
            "tooltip": "日志消息添加时间戳。"
        },
        {
            "arg": "--log-disable", "label": "禁用日志", "type": "checkbox",
            "default": False,
            "tooltip": "完全禁用日志输出。"
        },
    ],

    "投机解码MTP": [
        {
            "arg": "--spec-type", "label": "投机解码类型", "type": "combobox",
            "default": "none",
            "choices": ["none", "draft-simple", "draft-eagle3", "draft-mtp", "ngram-simple", "ngram-map-k", "ngram-map-k4v", "ngram-mod", "ngram-cache"],
            "tooltip": "投机解码类型。MTP 模型选择 draft-mtp。\n• none: 禁用\n• draft-simple: 简单 draft 模型\n• draft-eagle3: EAGLE3\n• draft-mtp: 多 Token 预测（MTP），需 MTP 专用 GGUF\n• ngram-*: 基于 n-gram 的推测解码\n可逗号分隔组合多个，如 draft-mtp,ngram-mod"
        },
        {
            "arg": "--spec-default", "label": "默认配置", "type": "checkbox",
            "default": False,
            "tooltip": "启用默认投机解码配置，自动设置推荐参数。"
        },
        {
            "arg": "--spec-draft-n-max", "label": "MTP 预测数", "type": "spinbox",
            "default": 3, "min_val": 1, "max_val": 10,
            "tooltip": "每次最多预测的 token 数（MTP 核心参数）。\n• 2: 稳定，82% 接受率\n• 3: 更高吞吐，72% 接受率\n推荐 MTP 模型设为 2 或 3。"
        },
        {
            "arg": "--spec-draft-n-min", "label": "最小草稿数", "type": "spinbox",
            "default": 0, "min_val": 0, "max_val": 10,
            "tooltip": "投机解码最小草稿 token 数。0 = 自动。"
        },
        {
            "arg": "--spec-draft-p-min", "label": "最小概率阈值", "type": "entry",
            "default": "0.00",
            "tooltip": "投机解码最小概率阈值（greedy 模式）。0.00 = 禁用。MTP 模型建议设为 0.75 可显著改善效果。"
        },
        {
            "arg": "--spec-draft-p-split", "label": "Split 概率", "type": "entry",
            "default": "0.10",
            "tooltip": "投机解码分割概率。0.10 = 10% 概率使用 split 验证。"
        },
        {
            "arg": "--spec-draft-model", "label": "Draft 模型路径", "type": "file",
            "default": "", "filetypes": [("GGUF 模型", "*.gguf"), ("所有文件", "*.*")],
            "tooltip": "独立 draft 模型文件路径。MTP 模型不需要（权重已在主 GGUF 内）。仅 draft-simple/draft-eagle3 需要。"
        },
        {
            "arg": "--spec-draft-ngl", "label": "Draft GPU 层数", "type": "entry",
            "default": "auto",
            "tooltip": "draft 模型卸载到 GPU 的层数。auto = 自动。MTP 的 draft 头通常很少层，auto 即可。"
        },
        {
            "arg": "--spec-draft-device", "label": "Draft 设备", "type": "entry",
            "default": "",
            "tooltip": "draft 模型使用的设备。留空 = 与主模型相同。例：CUDA0。"
        },
        {
            "arg": "--spec-draft-threads", "label": "Draft 线程数", "type": "spinbox",
            "default": -1, "min_val": -1, "max_val": 256,
            "tooltip": "draft 模型生成线程数。-1 = 与主模型相同。"
        },
        {
            "arg": "--spec-draft-type-k", "label": "Draft K 缓存类型", "type": "combobox",
            "default": "f16", "choices": ["f32", "f16", "bf16", "q8_0", "q4_0", "q4_1", "iq4_nl", "q5_0", "q5_1"],
            "tooltip": "draft 模型 K 缓存数据类型。f16 为默认。"
        },
        {
            "arg": "--spec-draft-type-v", "label": "Draft V 缓存类型", "type": "combobox",
            "default": "f16", "choices": ["f32", "f16", "bf16", "q8_0", "q4_0", "q4_1", "iq4_nl", "q5_0", "q5_1"],
            "tooltip": "draft 模型 V 缓存数据类型。f16 为默认。"
        },
        {
            "arg": "--spec-draft-backend-sampling", "label": "Draft 后端采样", "type": "checkbox",
            "default": True, "no_arg": "--no-spec-draft-backend-sampling",
            "tooltip": "将 draft 采样卸载到后端。默认启用。"
        },
    ],
}


# ============================================================
# 3. SettingsManager 设置方案管理
# ============================================================

class SettingsManager:
    """管理设置方案的加载、保存、导出、导入"""

    def __init__(self, settings_dir=None):
        if settings_dir is None:
            settings_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "launcher_settings"
            )
        self.settings_dir = settings_dir
        os.makedirs(self.settings_dir, exist_ok=True)

    def _safe_name(self, name):
        """将方案名转为安全的文件名"""
        safe = "".join(c for c in name if c not in r'\/:*?"<>|')
        return safe.strip() or "unnamed"

    def _filepath(self, name):
        return os.path.join(self.settings_dir, self._safe_name(name) + ".json")

    def list_profiles(self):
        """列出所有已保存的设置方案名"""
        profiles = []
        if os.path.isdir(self.settings_dir):
            for f in os.listdir(self.settings_dir):
                if f.endswith(".json"):
                    profiles.append(f[:-5])
        return sorted(profiles)

    def load(self, name):
        """加载指定名称的设置方案"""
        filepath = self._filepath(name)
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(f"加载设置方案失败: {e}")

    def save(self, name, data):
        """保存设置方案到 JSON 文件"""
        filepath = self._filepath(name)
        data["name"] = name
        data["modified"] = datetime.now().isoformat()
        if "created" not in data:
            data["created"] = data["modified"]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def delete(self, name):
        """删除指定设置方案"""
        filepath = self._filepath(name)
        if os.path.exists(filepath):
            os.remove(filepath)

    def exists(self, name):
        return os.path.exists(self._filepath(name))

    def export(self, filepath, data):
        """导出设置到外部 JSON 文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def import_profile(self, filepath):
        """从外部 JSON 文件导入设置"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


# ============================================================
# 4. CommandBuilder 命令构建器
# ============================================================

class CommandBuilder:
    """从参数字典构建命令行字符串"""

    # 需要引号包裹的参数（路径类）
    PATH_ARGS = {"--model", "--lora", "--control-vector", "--mmproj", "--image",
                 "--api-key-file", "--ssl-key-file", "--ssl-cert-file",
                 "--log-file", "--path", "--chat-template-file"}

    @staticmethod
    def build(exe_path, params, param_defs, extra_args=""):
        """
        构建完整命令行字符串
        params: {arg_key: value} 字典，arg_key 不含 -- 前缀
        param_defs: 参数定义列表（扁平化）
        extra_args: 附加参数字符串
        """
        parts = [f'"{exe_path}"']

        # 建立查找表
        defs_by_arg = {}
        for tab_params in param_defs.values():
            for p in tab_params:
                defs_by_arg[p["arg"]] = p

        for arg, definition in defs_by_arg.items():
            # 跳过 GUI 专用参数
            if definition.get("gui_only"):
                continue
            key = arg.lstrip("-").replace("-", "_")
            if key not in params:
                continue
            value = params[key]
            ptype = definition["type"]
            default = definition.get("default")

            if ptype == "checkbox":
                if value:  # True
                    parts.append(arg)
                elif definition.get("no_arg"):
                    parts.append(definition["no_arg"])
                # False 且无 no_arg 则不输出
            elif ptype in ("entry", "spinbox", "combobox"):
                if value is None or str(value).strip() == "":
                    continue
                val_str = str(value).strip()
                if arg in CommandBuilder.PATH_ARGS or (" " in val_str or "\\" in val_str):
                    parts.append(f'{arg} "{val_str}"')
                else:
                    parts.append(f'{arg} {val_str}')
            elif ptype in ("file", "dir"):
                if value and str(value).strip():
                    parts.append(f'{arg} "{str(value).strip()}"')

        # 附加参数
        if extra_args and extra_args.strip():
            parts.append(extra_args.strip())

        return " ".join(parts)

    @staticmethod
    def flatten_defs(param_defs):
        """将分 Tab 的参数定义扁平化为列表"""
        result = []
        for tab_params in param_defs.values():
            result.extend(tab_params)
        return result


# ============================================================
# 5. ScrollableFrame 可滚动框架
# ============================================================

class ScrollableFrame(ttk.Frame):
    """带滚动条的框架"""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable = ttk.Frame(self.canvas)

        self.scrollable.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # 自适应宽度
        self.scrollable.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # 鼠标滚轮
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event=None):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# ============================================================
# 6. LauncherApp 主窗口
# ============================================================

class LauncherApp:
    """主 GUI 应用"""

    def __init__(self, root):
        self.root = root
        self.root.title("Llama.cpp Server 启动器")
        self.root.geometry("960x720")
        self.root.minsize(800, 600)

        # 脚本所在目录
        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        # 自动检测 llama-server.exe
        self.exe_path = self._detect_exe()

        # 设置管理器
        self.settings_mgr = SettingsManager()

        # 子进程
        self.process = None

        # 控件字典：{param_key: widget}
        self.widgets = {}
        # 模型下拉框特殊处理
        self.model_combo = None
        self.model_dir_entry = None

        # 当前方案名
        self.current_profile = tk.StringVar(value="Default")

        # 构建 UI
        self._build_ui()

        # 加载 Default 方案（如存在）
        self._load_on_startup()

        # 窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _detect_exe(self):
        """自动检测 llama-server.exe"""
        exe_name = "llama-server.exe"
        # 1. 脚本同目录
        path = os.path.join(self.script_dir, exe_name)
        if os.path.exists(path):
            return path
        # 2. 让用户选择
        path = filedialog.askopenfilename(
            title="选择 llama-server.exe",
            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")],
            initialdir=self.script_dir
        )
        return path if path else ""

    def _build_ui(self):
        """构建完整 UI"""
        # ---- 顶部：设置方案管理栏 ----
        top_frame = ttk.Frame(self.root, padding=(10, 5))
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="设置方案:").pack(side=tk.LEFT, padx=(0, 5))

        self.profile_combo = ttk.Combobox(
            top_frame, textvariable=self.current_profile,
            values=self.settings_mgr.list_profiles(), state="readonly", width=20
        )
        self.profile_combo.pack(side=tk.LEFT, padx=2)
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_selected)

        ttk.Button(top_frame, text="加载", command=self._load_profile, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="保存", command=self._save_profile, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="另存为", command=self._save_as_profile, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="删除", command=self._delete_profile, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="导出...", command=self._export_profile, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="导入...", command=self._import_profile, width=8).pack(side=tk.LEFT, padx=2)

        # ---- exe 路径栏 ----
        exe_frame = ttk.Frame(self.root, padding=(10, 2))
        exe_frame.pack(fill=tk.X)

        ttk.Label(exe_frame, text="llama-server:").pack(side=tk.LEFT)
        self.exe_var = tk.StringVar(value=self.exe_path)
        exe_entry = ttk.Entry(exe_frame, textvariable=self.exe_var)
        exe_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(exe_frame, text="浏览...", command=self._browse_exe).pack(side=tk.LEFT)
        Tooltip(exe_entry, "llama-server.exe 的路径。自动检测同目录，也可手动选择。")

        # ---- 主体：Tab 区域 ----
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.tab_frames = {}
        for tab_name, params in PARAM_DEFINITIONS.items():
            scrollable = ScrollableFrame(self.notebook)
            self.notebook.add(scrollable, text=tab_name)
            self.tab_frames[tab_name] = scrollable
            self._build_tab(scrollable.scrollable, tab_name, params)

        # ---- 附加参数 Tab ----
        extra_frame = ttk.Frame(self.notebook)
        self.notebook.add(extra_frame, text="附加参数")
        ttk.Label(extra_frame, text="额外命令行参数（直接追加到命令末尾）:").pack(anchor=tk.W, padx=10, pady=(10, 5))
        self.extra_text = tk.Text(extra_frame, height=10, wrap=tk.WORD, font=('Consolas', 10))
        self.extra_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        Tooltip(self.extra_text, "在此输入额外的命令行参数，将直接追加到生成的命令末尾。\n例：--chat-template llama3 --api-key mykey123")

        # ---- 命令预览 ----
        preview_frame = ttk.LabelFrame(self.root, text="命令预览", padding=5)
        preview_frame.pack(fill=tk.X, padx=10, pady=5)

        self.cmd_preview = tk.Text(preview_frame, height=4, wrap=tk.WORD, font=('Consolas', 9),
                                   background='#F5F5F5', relief=tk.FLAT)
        self.cmd_preview.pack(fill=tk.X)
        self.cmd_preview.config(state=tk.DISABLED)

        # ---- 底部操作栏 ----
        bottom_frame = ttk.Frame(self.root, padding=(10, 5))
        bottom_frame.pack(fill=tk.X)

        self.btn_start = ttk.Button(bottom_frame, text="启动服务器", command=self._start_server)
        self.btn_start.pack(side=tk.LEFT, padx=2)

        self.btn_stop = ttk.Button(bottom_frame, text="停止", command=self._stop_server, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=2)

        ttk.Button(bottom_frame, text="复制命令", command=self._copy_command).pack(side=tk.LEFT, padx=2)

        self.btn_webui = ttk.Button(bottom_frame, text="打开 WebUI", command=self._open_webui, state=tk.DISABLED)
        self.btn_webui.pack(side=tk.LEFT, padx=2)

        self.status_label = ttk.Label(bottom_frame, text="状态: 已停止", foreground="gray")
        self.status_label.pack(side=tk.RIGHT)

        # 绑定参数变化事件
        self._bind_change_events()

    def _build_tab(self, parent, tab_name, params):
        """构建单个 Tab 的参数控件"""
        for i, param in enumerate(params):
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, padx=10, pady=3)

            label_text = param["label"]
            label = ttk.Label(row, text=label_text + ":", width=18, anchor=tk.W)
            label.pack(side=tk.LEFT, padx=(0, 5))

            ptype = param["type"]
            arg = param["arg"]
            key = arg.lstrip("-").replace("-", "_")
            default = param["default"]

            if ptype == "checkbox":
                var = tk.BooleanVar(value=default)
                widget = ttk.Checkbutton(row, variable=var, command=self._update_preview)
                widget.pack(side=tk.LEFT)
                self.widgets[key] = var

            elif ptype == "entry":
                var = tk.StringVar(value=str(default) if default is not None else "")
                widget = ttk.Entry(row, textvariable=var, width=40)
                widget.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.widgets[key] = var

            elif ptype == "spinbox":
                min_val = param.get("min_val", 0)
                max_val = param.get("max_val", 999999)
                var = tk.IntVar(value=int(default)) if isinstance(default, int) else tk.StringVar(value=str(default))
                widget = ttk.Spinbox(row, from_=min_val, to=max_val, textvariable=var, width=15)
                widget.pack(side=tk.LEFT)
                self.widgets[key] = var

            elif ptype == "combobox":
                choices = param.get("choices", [])
                var = tk.StringVar(value=str(default))
                widget = ttk.Combobox(row, textvariable=var, values=choices, width=20, state="readonly")
                widget.pack(side=tk.LEFT)
                self.widgets[key] = var

            elif ptype == "file":
                var = tk.StringVar(value=str(default) if default else "")
                entry = ttk.Entry(row, textvariable=var, width=35)
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
                filetypes = param.get("filetypes", [("所有文件", "*.*")])
                btn = ttk.Button(row, text="浏览...", width=8,
                                 command=lambda v=var, ft=filetypes: self._browse_file(v, ft))
                btn.pack(side=tk.LEFT)
                self.widgets[key] = var

            elif ptype == "dir":
                var = tk.StringVar(value=str(default) if default else "")
                entry = ttk.Entry(row, textvariable=var, width=35)
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
                btn = ttk.Button(row, text="浏览...", width=8,
                                 command=lambda v=var: self._browse_dir(v))
                btn.pack(side=tk.LEFT)
                self.widgets[key] = var

                # 模型文件夹特殊处理：选择后更新模型下拉列表
                if arg == "--model-dir":
                    self.model_dir_entry = var
                    refresh_btn = ttk.Button(row, text="刷新", width=6,
                                             command=self._refresh_model_list)
                    refresh_btn.pack(side=tk.LEFT, padx=(2, 0))
                    Tooltip(entry, param["tooltip"])

            # GPU 设备特殊处理：添加检测按钮
            if arg == "--device":
                detect_btn = ttk.Button(row, text="检测", width=6,
                                        command=self._detect_gpu_devices)
                detect_btn.pack(side=tk.LEFT, padx=(2, 0))

            # 模型文件特殊处理：添加下拉列表
            if arg == "--model" and self.model_dir_entry is not None:
                # 在模型文件行下方添加模型选择下拉
                model_row = ttk.Frame(parent)
                model_row.pack(fill=tk.X, padx=10, pady=2)
                ttk.Label(model_row, text="快速选择:", width=18, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
                self.model_combo = ttk.Combobox(model_row, textvariable=self.widgets[key],
                                                values=[], width=50, state="readonly")
                self.model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.model_combo.bind("<<ComboboxSelected>>", lambda e: self._update_preview())

            # 绑定 Tooltip
            tooltip_text = param.get("tooltip", "")
            if tooltip_text:
                Tooltip(label, tooltip_text)
                if ptype == "entry":
                    Tooltip(widget, tooltip_text)
                elif ptype in ("file", "dir"):
                    Tooltip(entry, tooltip_text)
                elif ptype in ("combobox", "spinbox", "checkbox"):
                    Tooltip(widget, tooltip_text)

    def _browse_file(self, var, filetypes):
        """浏览选择文件"""
        filepath = filedialog.askopenfilename(filetypes=filetypes)
        if filepath:
            var.set(filepath)
            self._update_preview()

    def _browse_dir(self, var):
        """浏览选择文件夹"""
        dirpath = filedialog.askdirectory()
        if dirpath:
            var.set(dirpath)
            self._update_preview()
            # 如果是模型文件夹，刷新模型列表
            if var is self.model_dir_entry:
                self._refresh_model_list()

    def _browse_exe(self):
        """浏览选择 exe"""
        filepath = filedialog.askopenfilename(
            title="选择 llama-server.exe",
            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")]
        )
        if filepath:
            self.exe_path = filepath
            self.exe_var.set(filepath)
            self._update_preview()

    def _refresh_model_list(self):
        """刷新模型文件夹下的 .gguf 文件列表"""
        if not self.model_dir_entry or not self.model_combo:
            return
        dir_path = self.model_dir_entry.get().strip()
        if not dir_path or not os.path.isdir(dir_path):
            return
        gguf_files = sorted(glob.glob(os.path.join(dir_path, "*.gguf")))
        self.model_combo['values'] = gguf_files
        if gguf_files and not self.widgets["model"].get():
            self.model_combo.current(0)
            self._update_preview()

    def _detect_gpu_devices(self):
        """检测可用的 GPU 设备"""
        exe = self.exe_var.get().strip()
        if not exe or not os.path.exists(exe):
            messagebox.showerror("错误", "llama-server.exe 路径无效")
            return

        self.status_label.config(text="状态: 正在检测 GPU 设备...", foreground="orange")
        self.root.update()

        try:
            result = subprocess.run(
                [exe, "--list-devices"],
                capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            output = result.stdout + result.stderr

            # 解析设备列表，格式：
            #   CUDA0: NVIDIA P104-100 (8191 MiB, 7219 MiB free)
            devices = []
            all_combo_choices = [""]
            for line in output.splitlines():
                line = line.strip()
                if not line or line.startswith("Available"):
                    continue
                # 设备名在冒号前面，如 "CUDA0: NVIDIA P104-100 (...)"
                if ":" in line:
                    dev_name = line.split(":")[0].strip()
                    # 确认是设备名（通常以 CUDA/Vulkan/OpenCL/SYCL 开头）
                    if dev_name and not dev_name.isdigit() and dev_name not in devices:
                        devices.append(dev_name)
                        all_combo_choices.append(dev_name)

            if devices:
                # 添加组合选项
                if len(devices) > 1:
                    all_combo_choices.append(",".join(devices))
                all_combo_choices.append("none")

                # 更新下拉框
                if "device" in self.widgets:
                    self.widgets["device"].set(devices[0])
                    # 找到 combobox 控件并更新 values
                    for tab_frame in self.tab_frames.values():
                        for child in tab_frame.scrollable.winfo_children():
                            for child2 in child.winfo_children():
                                if isinstance(child2, ttk.Combobox) and child2.cget("textvariable") == str(self.widgets["device"]):
                                    child2['values'] = all_combo_choices

                self.status_label.config(text="状态: 已停止", foreground="gray")
                messagebox.showinfo("GPU 检测结果",
                    f"检测到 {len(devices)} 个 GPU 设备:\n\n" +
                    "\n".join(f"  {i+1}. {d}" for i, d in enumerate(devices)) +
                    f"\n\n已自动选择: {devices[0]}\n可在下拉框中切换。")
            else:
                self.status_label.config(text="状态: 已停止", foreground="gray")
                messagebox.showwarning("GPU 检测",
                    "未检测到 GPU 设备。\n\n可能原因:\n• 未安装 CUDA 驱动\n• llama-server 未编译 GPU 支持\n\n输出信息:\n" + output[:500])

            self._update_preview()
        except subprocess.TimeoutExpired:
            self.status_label.config(text="状态: 已停止", foreground="gray")
            messagebox.showerror("错误", "检测超时，请确认 llama-server.exe 可正常运行")
        except Exception as e:
            self.status_label.config(text="状态: 已停止", foreground="gray")
            messagebox.showerror("错误", f"检测失败:\n{e}")

    def _bind_change_events(self):
        """绑定所有控件的变化事件以更新命令预览"""
        for var in self.widgets.values():
            if isinstance(var, tk.BooleanVar):
                var.trace_add('write', lambda *a: self._update_preview())
            elif isinstance(var, tk.StringVar):
                var.trace_add('write', lambda *a: self._update_preview())
            elif isinstance(var, tk.IntVar):
                var.trace_add('write', lambda *a: self._update_preview())
        self.extra_text.bind('<KeyRelease>', lambda e: self._update_preview())
        self.exe_var.trace_add('write', lambda *a: self._update_preview())

    # ---- 命令预览 ----

    def _update_preview(self):
        """更新命令预览"""
        params = self._collect_params()
        extra = self.extra_text.get("1.0", tk.END).strip()
        cmd = CommandBuilder.build(self.exe_var.get(), params, PARAM_DEFINITIONS, extra)
        self.cmd_preview.config(state=tk.NORMAL)
        self.cmd_preview.delete("1.0", tk.END)
        self.cmd_preview.insert("1.0", cmd)
        self.cmd_preview.config(state=tk.DISABLED)

    def _collect_params(self):
        """从 GUI 控件收集所有参数值"""
        params = {}
        for key, var in self.widgets.items():
            if isinstance(var, tk.BooleanVar):
                params[key] = var.get()
            elif isinstance(var, tk.IntVar):
                try:
                    params[key] = var.get()
                except (tk.TclError, ValueError):
                    params[key] = 0
            else:  # StringVar
                params[key] = var.get()
        return params

    def _copy_command(self):
        """复制命令到剪贴板"""
        params = self._collect_params()
        extra = self.extra_text.get("1.0", tk.END).strip()
        cmd = CommandBuilder.build(self.exe_var.get(), params, PARAM_DEFINITIONS, extra)
        self.root.clipboard_clear()
        self.root.clipboard_append(cmd)
        messagebox.showinfo("已复制", "命令已复制到剪贴板")

    # ---- 设置方案管理 ----

    def _load_on_startup(self):
        """启动时加载 Default 方案"""
        if self.settings_mgr.exists("Default"):
            self._load_profile("Default")
        else:
            self._update_preview()

    def _on_profile_selected(self, event=None):
        """下拉选择方案时自动加载"""
        name = self.current_profile.get()
        if name and self.settings_mgr.exists(name):
            self._load_profile(name)

    def _load_profile(self, name=None):
        """加载设置方案"""
        if name is None:
            name = self.current_profile.get()
        if not name:
            messagebox.showwarning("提示", "请先选择一个设置方案")
            return
        try:
            data = self.settings_mgr.load(name)
            if data is None:
                messagebox.showwarning("提示", f"设置方案 '{name}' 不存在")
                return
            self._apply_settings(data)
            self.current_profile.set(name)
            self._update_preview()
        except Exception as e:
            messagebox.showerror("错误", f"加载设置方案失败:\n{e}")

    def _apply_settings(self, data):
        """将设置数据应用到 GUI 控件"""
        params = data.get("params", {})
        for key, var in self.widgets.items():
            if key in params:
                val = params[key]
                if isinstance(var, tk.BooleanVar):
                    var.set(bool(val))
                elif isinstance(var, tk.IntVar):
                    try:
                        var.set(int(val))
                    except (ValueError, TypeError):
                        var.set(0)
                else:
                    var.set(str(val) if val is not None else "")
            else:
                # 恢复默认
                self._reset_to_default(key, var)

        # 附加参数
        extra = data.get("extra_args", "")
        self.extra_text.delete("1.0", tk.END)
        self.extra_text.insert("1.0", extra)

        # exe 路径
        if data.get("exe_path"):
            self.exe_var.set(data["exe_path"])

        # 刷新模型列表
        if self.model_dir_entry and self.model_dir_entry.get():
            self._refresh_model_list()

    def _reset_to_default(self, key, var):
        """恢复单个参数到默认值"""
        for tab_params in PARAM_DEFINITIONS.values():
            for p in tab_params:
                if p["arg"].lstrip("-").replace("-", "_") == key:
                    if isinstance(var, tk.BooleanVar):
                        var.set(p["default"])
                    elif isinstance(var, tk.IntVar):
                        try:
                            var.set(int(p["default"]))
                        except (ValueError, TypeError):
                            var.set(0)
                    else:
                        var.set(str(p["default"]) if p["default"] is not None else "")
                    return

    def _save_profile(self):
        """保存当前设置到当前方案"""
        name = self.current_profile.get()
        if not name:
            self._save_as_profile()
            return
        if self.settings_mgr.exists(name):
            # 保留 created 时间
            try:
                old = self.settings_mgr.load(name)
                created = old.get("created", datetime.now().isoformat())
            except Exception:
                created = datetime.now().isoformat()
        else:
            created = datetime.now().isoformat()

        data = self._gather_settings()
        data["created"] = created
        self.settings_mgr.save(name, data)
        self._refresh_profile_list()
        messagebox.showinfo("已保存", f"设置方案 '{name}' 已保存")

    def _save_as_profile(self):
        """另存为新方案"""
        name = simpledialog.askstring("另存为", "请输入设置方案名称:", parent=self.root,
                                      initialvalue=self.current_profile.get())
        if not name:
            return
        if self.settings_mgr.exists(name):
            if not messagebox.askyesno("确认", f"方案 '{name}' 已存在，是否覆盖？"):
                return
        data = self._gather_settings()
        self.settings_mgr.save(name, data)
        self.current_profile.set(name)
        self._refresh_profile_list()
        messagebox.showinfo("已保存", f"设置方案 '{name}' 已保存")

    def _delete_profile(self):
        """删除当前方案"""
        name = self.current_profile.get()
        if not name:
            return
        if not self.settings_mgr.exists(name):
            return
        if not messagebox.askyesno("确认", f"确定要删除方案 '{name}' 吗？"):
            return
        self.settings_mgr.delete(name)
        self._refresh_profile_list()
        # 切换到第一个可用方案
        profiles = self.settings_mgr.list_profiles()
        if profiles:
            self.current_profile.set(profiles[0])
            self._load_profile(profiles[0])
        else:
            self.current_profile.set("")

    def _export_profile(self):
        """导出当前设置到外部 JSON 文件"""
        filepath = filedialog.asksaveasfilename(
            title="导出设置方案",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
            initialfile=self.current_profile.get() + ".json"
        )
        if not filepath:
            return
        try:
            data = self._gather_settings()
            self.settings_mgr.export(filepath, data)
            messagebox.showinfo("已导出", f"设置已导出到:\n{filepath}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败:\n{e}")

    def _import_profile(self):
        """从外部 JSON 文件导入设置"""
        filepath = filedialog.askopenfilename(
            title="导入设置方案",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        if not filepath:
            return
        try:
            data = self.settings_mgr.import_profile(filepath)
            name = data.get("name", os.path.splitext(os.path.basename(filepath))[0])
            if self.settings_mgr.exists(name):
                if not messagebox.askyesno("确认", f"方案 '{name}' 已存在，是否覆盖？"):
                    return
            self.settings_mgr.save(name, data)
            self._refresh_profile_list()
            self.current_profile.set(name)
            self._apply_settings(data)
            self._update_preview()
            messagebox.showinfo("已导入", f"设置方案 '{name}' 已导入")
        except Exception as e:
            messagebox.showerror("错误", f"导入失败:\n{e}")

    def _gather_settings(self):
        """收集当前 GUI 设置为字典"""
        return {
            "name": self.current_profile.get(),
            "exe_path": self.exe_var.get(),
            "params": self._collect_params(),
            "extra_args": self.extra_text.get("1.0", tk.END).strip(),
        }

    def _refresh_profile_list(self):
        """刷新方案下拉列表"""
        profiles = self.settings_mgr.list_profiles()
        self.profile_combo['values'] = profiles

    # ---- 服务器启动/停止 ----

    def _start_server(self):
        """启动 llama-server"""
        if not self.exe_var.get() or not os.path.exists(self.exe_var.get()):
            messagebox.showerror("错误", "llama-server.exe 路径无效，请重新选择")
            return

        model_path = self.widgets.get("model")
        if model_path and not model_path.get().strip():
            if not messagebox.askyesno("确认", "未选择模型文件，是否继续？"):
                return

        params = self._collect_params()
        extra = self.extra_text.get("1.0", tk.END).strip()
        cmd = CommandBuilder.build(self.exe_var.get(), params, PARAM_DEFINITIONS, extra)

        try:
            # 写入临时 bat 文件，确保控制台窗口不会闪退
            bat_path = os.path.join(self.script_dir, "_run_server.bat")
            with open(bat_path, 'w', encoding='utf-8') as f:
                f.write('@echo off\n')
                f.write('chcp 65001 >nul\n')
                f.write('title llama-server\n')
                f.write(cmd + '\n')
                f.write('echo.\n')
                f.write('echo [服务器已停止] 按任意键关闭窗口...\n')
                f.write('pause >nul\n')

            self.process = subprocess.Popen(
                f'cmd /c "{bat_path}"',
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.btn_webui.config(state=tk.NORMAL)
            self.status_label.config(text="状态: 运行中", foreground="green")
        except Exception as e:
            messagebox.showerror("启动失败", f"无法启动 llama-server:\n{e}")

    def _stop_server(self):
        """停止 llama-server"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception:
                pass
            finally:
                self.process = None
                self.btn_start.config(state=tk.NORMAL)
                self.btn_stop.config(state=tk.DISABLED)
                self.btn_webui.config(state=tk.DISABLED)
                self.status_label.config(text="状态: 已停止", foreground="gray")

    def _open_webui(self):
        """打开浏览器访问 WebUI"""
        host = self.widgets.get("host")
        port = self.widgets.get("port")
        h = host.get() if host else "127.0.0.1"
        p = port.get() if port else "8080"
        # 0.0.0.0 替换为 127.0.0.1
        if h == "0.0.0.0":
            h = "127.0.0.1"
        url = f"http://{h}:{p}"
        webbrowser.open(url)

    def _on_close(self):
        """窗口关闭事件"""
        if self.process:
            if messagebox.askyesno("确认", "服务器正在运行，是否停止并退出？"):
                self._stop_server()
            else:
                return
        self.root.destroy()


# ============================================================
# 7. 入口
# ============================================================

def main():
    root = tk.Tk()
    app = LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
