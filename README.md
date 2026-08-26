# M_Agent — 终端 AI 编程助手

基于 LangGraph 从零实现的交互式终端 AI 编程助手（Python）。支持在终端中通过自然语言完成文件读写、命令执行、代码检索等编程任务，内置多层安全防护与上下文管理。

## 功能特性

- **ReAct 循环**：自定义 StateGraph 编排「模型调用 → 安全校验 → 工具执行 → 结果回填」的完整循环，条件路由控制多轮工具调用与自动终止
- **工具系统**：
  - `read_file` 分段读取（offset/limit）、超大文件截断、缩进保留
  - `edit_file` 唯一匹配校验 + `replace_all` 批量替换
  - `execute_command` 命令执行（超时控制、输出截断）
  - `list_dir` / `glob_file` / `grep_code` 目录探查与检索
- **三层安全防护**：
  - 危险命令正则黑名单（覆盖 rm -rf 变体、磁盘写入、权限篡改等 10+ 类高危操作）直接拦截
  - 写操作人工确认（y/n/a，支持永久放行）
  - 工作目录路径沙箱，硬拦截越界访问
- **上下文管理**：对话超限自动 LLM 摘要压缩；JSON 会话持久化，重启可恢复
- **多工具并行**：读操作并发执行、写操作串行执行，异常容错
- **流式输出**：token 级打字机效果，工具结果穿插显示
- **规划子 Agent**：只读子图实现复杂任务「先方案后执行」的上下文隔离
- **单元测试**：pytest 覆盖安全层与工具核心分支，防回归

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key（DeepSeek，OpenAI 兼容协议）
# Windows PowerShell:
$env:DEEPSEEK_API_KEY = "sk-你的key"

# 3. 启动
python src/agent/main.py
```

## 使用示例

```
> 读取 D:/Agent_Test/test/test2.txt 并告诉我第一行内容
> 把 hello.py 里所有的 Hello 改成 Hi（全部替换）
> 搜一下 test 目录里哪个文件包含 "orange"
> 用 plan_task 调研 test 目录并给出整理方案
```

## 项目结构

```
src/agent/
├── main.py          # 入口：REPL、会话持久化、上下文压缩、流式渲染
├── graph.py         # 主图（ReAct 循环）+ 规划子图（只读）
├── tools.py         # 工具定义：read/edit/command/list_dir/grep/glob/plan_task
├── safety.py        # 安全层：危险命令检测 + 决策（block/confirm/allow）
├── storage.py       # JSON 会话存档
└── ui.py            # 终端界面（预留）
tests/
└── test_safety.py   # 单元测试
```

## 技术栈

Python · LangGraph · LangChain · DeepSeek（OpenAI 兼容）· Rich

## 测试

```bash
python -m pytest tests/ -v
```
