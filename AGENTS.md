# AGENTS.md instructions for E:\学习资料\研\我的论文\金融科技\第二章论文\codex\fintech 文本提取

禁止批量删除文件或目录。
不要使用：
- `del /s`
- `rd /s`
- `rmdir /s`
- `Remove-Item -Recurse /s`
- `rm -rf`

需要删除文件时，只能一次删除一个明确路径的文件。
正确示例：
`Remove-Item "C:\path\to\file.txt"`

如果需要批量删除文件，应停止操作，并向用户请求，让用户手动删除。

遇到任务时优先检索参考已安装的相关联 skill。

输出新文件时默认输出到旧文件的同一文件夹下。

## Python 环境

- 本项目默认使用项目内虚拟环境：
  `E:\学习资料\研\我的论文\金融科技\第二章论文\codex\fintech 文本提取\.venv\Scripts`
- 需要执行本地 Python 脚本、安装或检查包时，优先用完整路径调用：
  `E:\学习资料\研\我的论文\金融科技\第二章论文\codex\fintech 文本提取\.venv\Scripts\python.exe`
- 如果项目内虚拟环境不可用，再使用测试 Python 环境：
  `E:\pythoncode\test\.venv\Scripts\python.exe`
