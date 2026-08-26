import re

# 危险命令模式
DANGEROUS_COMMAND_PATTERN = [
    # ── rm -rf 系列（根目录 / 绝对路径，容忍可选引号）──
    r"rm\s+-rf?\s+[\"']?[a-zA-Z]:[\\/]",   # rm -rf D:\ 或 "D:\..."
    r"rm\s+-rf?\s+[\"']?/",                # rm -rf / 或 "/tmp/x"

    # ── Windows 强删 ──
    r"rmdir\s+/s\s+/q\s+[\"']?[a-z]:\\",
    r"del\s+/f\s+/s\s+/q\s+[\"']?[a-z]:\\",

    # ── 磁盘 / 系统级 ──
    r"format\s+[\"']?[a-z]:",
    r"shutdown",
    r"diskpart",

    # ── 管道下载执行 shell ──
    r"curl\s+.*\|\s*(ba)?sh",
    r"wget\s+.*\|\s*(ba)?sh",

    # ── chmod / chown：目标为根目录或系统目录 ──
    # 修复1：允许 -R 标志（之前 chmod -R 777 /etc 匹配不上）
    r"chmod\s+(?:-R\s+)?[-0-7]*\s+[\"']?/(?:etc|usr|var|bin|sbin|boot|dev|home|root)?[\"']?",
    # 修复2：Windows 系统目录
    r"chmod\s+[-0-7r]+\s+[\"']?[a-z]:[\\/]windows",
    # 修复3：chown -R 后允许任意内容（用户:组 等）再匹配 /
    r"chown\s+-R\s+.*[\"']?/",

    # ── dd 写块设备 ──
    r"dd\s+.*of\s*=\s*[\"']?/dev/",

    # ── mkfs 系列 ──
    r"mkfs(?:\.[a-z0-9]+)?\s+[\"']?/dev/",

    # ── 重定向写块设备 ──
    r">\s*[\"']?/dev/",

    # ── 解压到根 ──
    r"tar\s+.*-C\s+[\"']?/[\"']?",
    r"unzip\s+.*-d\s+[\"']?/[\"']?",

    # ── sudo 组合高危命令 ──
    r"sudo\s+.*(?:rm\s+-rf|dd\s+.*of=/dev/|mkfs|chmod\s+[-0-7]+\s+/)",

    # ── 磁盘分区 ──
    r"fdisk\s+/dev/",
]



def is_dangerous_command(command: str) -> bool:
    """判断命令是否危险"""
    for pattern in DANGEROUS_COMMAND_PATTERN:
        if re.search(pattern, command, re.IGNORECASE):#re.IGNORECASE：忽略大小写，比如 DEL、Del、del 全部都能识别出来
            return True
    return False

def decide(tool_name: str, args: dict)-> str:
    """返回 "block" | "confirm" | "allow"。"""
    if tool_name == "execute_command" and is_dangerous_command(args.get("command", "")):
        return "block"
    if tool_name in ("execute_command", "edit_file"):   # 写操作：改文件/跑命令 → 确认
        return "confirm"
    return "allow"