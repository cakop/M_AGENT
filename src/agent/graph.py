from dotenv import load_dotenv
from langchain_core.messages import ToolMessage
from concurrent.futures import ThreadPoolExecutor
load_dotenv(override=True)
from langchain_deepseek import ChatDeepSeek
from src.agent.tools import read_file,execute_command,edit_file,plan_task,list_dir,grep_code,glob_file,load_skill
from src.agent.safety import decide
from typing import TypedDict
from typing import Annotated
from langgraph.graph.message import add_messages
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.utils.function_calling import convert_to_openai_tool
_ALWAYS_ALLOW: set[str] = set()

MAX_PARALLEL_TOOLS = 4
class State(TypedDict):
    messages: Annotated[list, add_messages]
    pending_calls: list[dict] # 通过安全层的调用，每轮用完清空
    always_allow: list[str]  # 用户选过 "a" 的工具名

model = ChatDeepSeek(
    model="deepseek-v4-flash",
    extra_body={
        "thinking": {
            "type": "disabled"
        }
    }
)

SYSTEM_PROMPT = """\
你是 M_Agent，运行在 Windows 本地终端的 AI 编程助手，专注完成代码编写、修改、调试、执行任务。

## 身份规则
- 你是 M_Agent，不要冒充其他大模型。
- 全程使用中文，回答简洁干练，减少多余礼貌用语，聚焦任务本身。

## 可用工具
1. read_file：读取本地文件，只读，不能修改文件；返回内容携带行号，用于定位代码位置。
2. edit_file：修改文件。old_string必须和文件原文**完全精确匹配、在文件内唯一**，替换才会生效；匹配失败直接报错。修改完成必须校验结果。
3. execute_command：执行 Windows CMD/PowerShell 命令，**必须使用Windows语法，禁止直接使用Linux命令（ls、rm等）**。
4. plan_task：复杂任务先派规划子 Agent 出方案，确认后再执行。
5. list_dir：探查目录结构（不要猜文件名，先 list_dir 再看）。
6. grep_code：在目录中搜索文本。
7. glob_files：按文件名模式查找文件（*.py、test*.txt）。
8. load_skill：加载专业技能。可用技能：
   - commit（写规范的 git commit message）
   - review（代码评审：逻辑/边界/命名/安全）
   - test（编写 pytest 单元测试）
   当任务匹配某个技能时，先调用 load_skill 加载规范，再执行。

## 工作目录边界
- 你的工作目录是 D:\\Agent_Test。只能读取和修改这个目录内的文件。
- 访问目录外的文件会被拒绝。需要操作目录外文件时，告诉用户并停止。

## 执行流程（严格遵守）
1. 收到用户任务，先评估当前信息是否充足，**按需调用工具，禁止一次性批量调用多个无关工具**。
2. 修改文件强制流程：先用 read_file 读取目标文件确认原文 → 执行 edit_file 修改 → 读取文件或者运行命令验证修改效果，确认无误再向用户汇报。
3. 执行命令后仔细阅读 stdout、stderr、退出码，识别报错，根据报错修复问题。
4. 同一时间只推进一个目标，不要中途跳转无关任务。

## 安全约束
- 禁止尝试删除系统目录、格式化磁盘、批量破坏文件等高风险操作，该类操作会被安全节点直接拦截。
- 如果工具返回「危险操作已拦截」「操作被拒绝」，不要重复发起相同调用，立刻更换安全方案完成目标；无法替代则如实告知用户。
- 不要尝试绕过安全校验。

## 输出与汇报规范
- 优先给出任务结论，再补充关键细节，拒绝大段废话。
- 任务完成汇报固定说明三件事：①做了哪些操作 ②执行结果 ③是否存在异常/待处理问题。
- 工具调用不要做文本模拟，必须真实发起工具调用；不要编造文件内容、命令执行结果。

## 禁止行为
- 不要主动闲聊，用户没有闲聊就专注处理任务。
- 不要猜测文件内容，不清楚就调用 read_file。
- edit_file 不要省略空格、换行、缩进，old_string必须和源文件一字不差。
- 工具结果就是权威信息，不要编造或美化，直接汇报事实

"""


def call_model(state: State) -> dict:
    messages = state["messages"]
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    response = model.invoke(full_messages, tools=[convert_to_openai_tool(read_file),
                                                  convert_to_openai_tool(execute_command),
                                                  convert_to_openai_tool(edit_file),
                                                  convert_to_openai_tool(plan_task),
                                                  convert_to_openai_tool(list_dir),
                                                  convert_to_openai_tool(grep_code),
                                                  convert_to_openai_tool(glob_file),
                                                  convert_to_openai_tool(load_skill)
                                                  ])

    return {"messages": [response]}

def security(state: State) -> dict:
    last_ai = state["messages"][-1]
    outputs = {"messages": [], "pending_calls": []}
    for tc in last_ai.tool_calls:
        decision = decide(tc["name"], tc["args"])
        # 构造ToolMessage告诉大模型：危险操作已经被拦掉
        if decision == "block":
            outputs["messages"].append(ToolMessage(content="危险操作已拦截", tool_call_id=tc["id"]))
        #     confirm 需要人工确认；并且工具不在永久放行集合
        elif decision == "confirm" and tc["name"] not in _ALWAYS_ALLOW:
            # # 在控制台弹出交互，等待人输入 y/n/a
            ans = input(f"允许执行 {tc['name']}({tc['args']})? [y/n/a] ").strip().lower()
            # a = always：永久放行这个工具，后续再调用不再弹窗确认
            if ans == "a":
                _ALWAYS_ALLOW.add(tc["name"])
                # 加入待执行列表，可以跑
                outputs["pending_calls"].append(tc)
            elif ans == "y":
                # y = yes：本次允许执行，下次调用依旧会弹窗确认
                outputs["pending_calls"].append(tc)
            else:
                # n或者其他输入：拒绝本次操作
                outputs["messages"].append(ToolMessage(content="操作被拒绝", tool_call_id=tc["id"]))
     # allow，不需要确认，直接加入待执行队列
        else:
            outputs["pending_calls"].append(tc)
    return outputs

def tools(state: State)->dict:
    calls= state["pending_calls"]
    reads= [tc for tc in calls if tc.get("name") == "read_file"]#读并行
    writes= [tc for tc in calls if tc.get("name") != "read_file"]#其余串行
    tool_map = {
        "read_file": read_file,
        "execute_command": execute_command,
        "edit_file": edit_file,
        "plan_task": plan_task,
        "list_dir": list_dir,
        "grep_code": grep_code,
        "glob_file": glob_file,
        "load_skill": load_skill
    }

    def run_one(tc):
        tc_id= tc["id"]
        name= tc.get("name")
        # 模型输出了一个不存在的工具名
        if name not in tool_map:
            return tc_id, f"错误：未知工具 {name}"
        try:
            tool= tool_map[name] # 根据名字取出工具
            res= tool.invoke(tc["args"])
            return tc_id,res
        except Exception as e:
            # 只要工具执行抛任何异常（文件不存在、权限报错等），捕获，包装成字符串返回，不让整个图崩溃
            return tc_id, f"工具执行异常：{str(e)}"

    results= {}
    # read_file 并发
    if reads:
        with ThreadPoolExecutor(MAX_PARALLEL_TOOLS) as pool:
            # map：把 reads 里面每一个元素，丢给 run_one() 去执行，在线程池里面并发跑
            # ("call_001", "文件内容A"), ("call_002", "文件内容B"), ("call_003", "文件内容C")
            for tid, r in pool.map(run_one, reads):
                results[tid] = r
    # 其余串行
    for tc in writes:
        tid, r = run_one(tc)
        results[tid] = r
    msg = [ToolMessage(content=results[tc["id"]], tool_call_id=tc["id"]) for tc in calls]
    return {"messages": msg, "pending_calls": []}



def my_router(state: State) -> str:
    if state["messages"][-1].tool_calls:
        return "security"
    return END
# 构建函数
def build_app():
    graph = StateGraph(State)
    #添加节点
    graph.add_node("call_model", call_model)
    graph.add_node("tools", tools)
    graph.add_node("security", security)
    #添加边
    graph.add_edge(START, "call_model")
    graph.add_conditional_edges("call_model", my_router)         # 返回 "security" 或 END
    graph.add_conditional_edges("security", lambda s: "tools" if s["pending_calls"] else "call_model")
    graph.add_edge("tools", "call_model")
    app = graph.compile()
    return app

#子agent
def build_plan_app():
    """构建规划子 Agent 的图：只有只读工具，只能产出方案，不能执行。"""
    from langgraph.graph import StateGraph, START, END
    from langgraph.graph.message import add_messages
    from typing import TypedDict, Annotated

    class PlanState(TypedDict):
        messages : Annotated[list,add_messages]

    # 只读工具：只有 read_file,子 agent 用同一个 model，但只绑只读工具
    plan_tools=[convert_to_openai_tool(read_file),
                convert_to_openai_tool(list_dir),
                convert_to_openai_tool(grep_code),
                convert_to_openai_tool(glob_file)

                ]

    def plan_call_model(state: PlanState) -> dict:
        messages = state["messages"]
        full = [{"role": "system",
                 "content": "你是规划专家。只分析、只读文件、只出方案。绝不修改任何文件。输出结构化 plan：1. 现状 2. 方案步骤 3. 风险。"}] + messages
        response = model.invoke(full, tools=plan_tools)
        return {"messages": [response]}

    def plan_tools_node(state: PlanState) -> dict:
        # 执行只读工具

        results=[]
        for tc in state["messages"][-1].tool_calls:
            res=read_file.invoke(tc["args"])
            results.append(ToolMessage(content=res, tool_call_id=tc["id"]))
        return {"messages":results}

    def plan_router(state: PlanState) -> str:
        if state["messages"][-1].tool_calls:
            return "tools"
        return END

    g = StateGraph(PlanState)
    g.add_node("call_model", plan_call_model)
    g.add_node("tools", plan_tools_node)
    g.add_edge(START, "call_model")
    g.add_conditional_edges("call_model", plan_router)
    g.add_edge("tools", "call_model")
    return g.compile()

if __name__ == "__main__":
    app=build_app()
    result = app.invoke({"messages": [("user", r"把D:\Agent_Test\test\test.txt中的2改成3")]})
    print(result["messages"][-1].content)
