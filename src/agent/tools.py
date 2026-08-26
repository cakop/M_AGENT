from langchain_core.tools import tool
from pydantic import BaseModel, Field
import  os
import fnmatch
# 工作根目录：模型只能访问这个目录内的文件
WORK_DIR = r"D:\Agent_Test"

class ReadFileArgs(BaseModel): # ← 自己定义 schema
    """读取文件参数"""
    file_path: str = Field(description="要读取的文件路径")
    offset: int = Field(default=1, description="从第几行开始读（从 1 开始）")
    limit: int = Field(default=500, description="最多读多少行")


class ExecuteCommandArgs(BaseModel):
    """执行命令参数"""
    command:str = Field(description="要执行的shell命令")

class EditFileArgs(BaseModel):
    """编辑文件参数"""
    file_path: str = Field(description="要编辑的文件路径")
    old_string: str = Field(description="要替换的字符串")
    new_string: str = Field(description="替换的新内容")
    replace_all: bool = Field(default=False, description="是否替换所有出现（True=全部替换，False=只允许唯一匹配）")

class PlanTaskArgs(BaseModel):
    """规划任务参数"""
    task: str = Field(description="要规划的任务描述")
    files: list[str] = Field(default=[], description="需要调研的文件路径列表")

class ListDirArgs(BaseModel):
    """列目录参数"""
    path: str = Field(default=".", description="要列出的目录路径（默认当前工作目录）")

class GrepArgs(BaseModel):
    """搜索内容参数"""
    pattern: str = Field(description="要搜索的文本或正则")
    path: str = Field(default=".", description="搜索的目录")

class GlobArgs(BaseModel):
    """按文件名模式查找文件"""
    pattern: str = Field(description="文件名模式，如 *.py、test*.txt、*config*")
    path: str = Field(default=".", description="在哪个目录下查找")



@tool(args_schema=ReadFileArgs, description="读取文件内容（只读）。支持分段读取：offset 指定起始行，limit 指定行数。")
def read_file(file_path: str,offset: int = 1, limit: int = 500,**kwargs)-> str :
    """读取文件指定行范围带行号返回"""
    if not is_within_workdir(file_path):
        return f"错误：只能访问工作目录 {WORK_DIR} 内的文件，已拒绝读取 {file_path}"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        total=len(lines)
        if offset < 1:
            offset=1
        end = offset +limit -1
        if end >total:
            end=total
        output = []
        for i in range(offset - 1,end):
            output.append(f"{i+1}: {lines[i].rstrip('\r\n')}")
        result ="\n".join( output)
        #提示还有多少行没显示
        if end < total:
            result += f"\n...（共 {total} 行，已显示 {offset}~{end} 行，剩余 {total - end} 行）"
        return result
    except FileNotFoundError:
        return f"文件不存在: {file_path}"
    except Exception as e:
        return f"发生错误: {str(e)}"

@tool(args_schema=EditFileArgs, description="修改文件：把 old_string 替换为 new_string。replace_all=False 时 old_string 必须唯一出现；True 时替换所有出现。")
def edit_file(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """把 old_string 替换为 new_string；默认要求唯一匹配，replace_all=True 时替换全部。"""
    if not is_within_workdir(file_path):
        return f"错误：只能访问工作目录 {WORK_DIR} 内的文件，已拒绝修改 {file_path}"
    try:
        with open(file_path, 'r+', encoding='utf-8') as f:
            content = f.read()
            count=content.count(old_string)
            if count==0:
                return f"文件 {file_path} 中没有 {old_string}"
            if count>1 and not replace_all:
                return f"错误：{old_string!r} 在文件中出现了 {count} 次。请提供更长的片段，或设置 replace_all=True 替换全部"
            #恰好一次进行替换
            with open(file_path, 'w', encoding='utf-8')as f:
                f.write(content.replace(old_string, new_string))
            if replace_all and count>1:
                suffix = f"（共替换 {count} 处）"
            else:
                suffix = ""
            return f"文件 {file_path} 已修改{suffix}"
    except FileNotFoundError:
        return f"文件不存在: {file_path}"
    except Exception as e:
        return f"发生错误: {str(e)}"


@tool(args_schema=ExecuteCommandArgs,description="在终端执行 shell 命令并返回输出（如 ls、git、python 等）")
def execute_command(command: str)-> str:
    """在终端执行 shell 命令并返回输出（如 ls、git、python 等）"""
    import subprocess #让 Python 代码去跑「操作系统的命令」，相当于在 cmd /powershell/ 终端敲命令
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True,timeout=30)
        # 捕获stdout标准输出、stderr错误输出，不打印到控制台 最多运行30秒，防止卡死死循环命令
        output=result.stdout
        # 如果有错误输出，把stderr也拼到结果里
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        # returncode不等于0 → shell命令报错（比如命令不存在、文件找不到）
        if result.returncode != 0:
            output = f"命令执行失败(exit{result.returncode}):\n{output}"
        # 保护：输出太长截断，防止几万字返回给模型，token爆炸
        if len( output) > 4000:
            output = output[:4000] + "\n...(输出已截断)"
        return  output
    # 超过timeout=30秒触发，比如死循环脚本
    except subprocess.TimeoutExpired:
        return "命令执行超时"
    except Exception as e:
        return f"发生错误: {str(e)}"

def is_within_workdir(path:str)->bool:
    """判断 path 是否在工作目录内。返回True代表允许，返回False代表拒绝"""
    path_abs = os.path.abspath(path)# 把传入路径转成【绝对路径】，处理../、相对路径
    work_abs=os.path.abspath(WORK_DIR)# 配置的允许根目录，也转绝对路径
    # 相等（就是根目录本身）或 以 根目录+分隔符 开头 → 允许
    return path_abs == work_abs or path_abs.startswith(work_abs + os.sep)
    #path_abs.startswith(work_abs + os.sep)：文件在工作目录子文件夹内部


# 主 agent 收到复杂任务
#   → 调 plan_task 工具（子 agent 入口）
@tool(args_schema=PlanTaskArgs, description="派一个规划子 Agent 去调研任务并产出方案（只读，不执行任何修改）。适合复杂任务先出计划。")
def plan_task(task: str, files: list[str] = []) -> str:
    """让规划子 Agent 调研并返回方案。"""
    from src.agent.graph import build_plan_app
    app=build_plan_app()
    messages = [{"role": "user", "content": f"任务：{task}\n\n需要调研的文件：{files}"}]
    result = app.invoke({"messages": messages})
    return result["messages"][-1].content

@tool(args_schema=ListDirArgs, description="列出目录下的文件和子目录（只读）。探查项目结构时用这个，不要猜文件名。")
def list_dir(path: str=".")-> str:
    """列出目录内容"""
    # 安全校验：判断访问路径是否在允许的工作目录内，防止越权访问外面磁盘文件
    if not is_within_workdir(path):
        return f"错误：只能访问工作目录 {WORK_DIR} 内的文件，已拒绝访问 {path}"
    try:
        # 获取该路径下全部子项（文件名+文件夹名，只是名字，不是完整路径
        entries = os.listdir(path)
        files, dirs = [], []
        for e in entries:
            # 拼接成完整绝对路径，才能判断是文件夹还是文件
            full = os.path.join(path, e)
            if os.path.isdir( full):#os.path.isdir(完整路径)：判断这个东西是不是文件夹。
                dirs.append(e+"/")
            else:
                files.append(e)
        parts=[f"[目录] {d}" for d in sorted(dirs)] + [f"[文件] {f}" for f in sorted(files)]#sorted(files)：文件名按字母排序
        return "\n".join(parts) if parts else "(空目录)"
    except Exception as e:
        return f"发生错误: {str(e)}"

@tool(args_schema=GrepArgs, description="在目录中搜索包含指定文本的文件（只读）。")
def grep_code(pattern: str,path: str=".")-> str:
    """在目录中搜索包含指定文本的文件"""
    # 安全校验：判断访问路径是否在允许的工作目录内，防止越权访问外面磁盘文件
    if not is_within_workdir(path):
        return f"错误：只能搜索工作目录 {WORK_DIR} 内的目录"
    results =[]
    # os.walk(path)递归遍历整个目录树。
    # root：当前正在扫描的文件夹完整路径
    # dirs：当前文件夹下子文件夹名称列表
    # files：当前文件夹下文件名称列表
    for root,dirs,files in os.walk(path):
        # 原地过滤：遍历文件夹时，不要进入下面这些文件夹 dirs[:]原地修改列表，告诉 os.walk 不要进入黑名单文件夹
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "venv", "venv312", "sessions")]
        for f in files:
            print(f"[DEBUG] 正在检查: {os.path.join(root, f)}")
            if not f.endswith((".py",".js",".ts",".tsx",".md",".html",".css",".json",".yml",".yaml",".txt")):
                 continue
            fp = os.path.join(root, f)
            try:
                with open(fp, "r", encoding="utf-8",errors="ignore") as fh:
                    for i,line in enumerate(fh,1):
                        if pattern.lower() in line.lower():#把搜索关键词和当前行全部转小写再判断是否包含
                            rel=os.path.relpath(fp,path)#os.path.relpath(完整文件路径, 搜索根目录path) 算出相对路径
                            results.append(f"{rel}:{i}:{line.strip()[:100]}")
                            break
            except Exception:
                continue
    return  "\n".join(results[:50]) if results else "未找到匹配"

@tool(args_schema=GlobArgs, description="按文件名模式查找文件（只读）。pattern 支持通配符：* 匹配任意字符，? 匹配单个字符。")
def glob_file(pattern: str, path: str = ".") -> str:
    """在目录中搜索包含指定模式的文件"""
    # 安全校验：判断访问路径是否在允许的工作目录内，防止越权访问外面磁盘文件
    if not is_within_workdir(path):
        return f"错误：只能搜索工作目录 {WORK_DIR} 内的目录"
    results = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "venv", "venv312", "sessions")]
        for f in files:
            if fnmatch.fnmatch(f, pattern):#  用模式匹配
                results.append(os.path.relpath(os.path.join(root, f), path))
    # 限制返回条数，防止刷屏
    if not results:
        return f"未找到匹配 {pattern!r} 的文件"
    output = "\n".join(results[:50])
    if len(results) > 50:
        output += f"\n...（共 {len(results)} 个，只显示前 50 个）"
    return output


