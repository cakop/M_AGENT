from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.agent.graph import build_app
from rich.console import Console
from src.agent.storage import save_session, load_session, list_sessions
from src.agent.storage import SESSIONS_DIR
from src.agent.graph import model
from langchain_core.messages import BaseMessage
console = Console()


def msg_to_dict(msg) -> dict:
    """LangChain 消息 → 纯 dict（可 JSON 序列化）。"""
    role_map = {
        "human": "user",
        "user": "user",
        "ai": "assistant",
        "assistant": "assistant",
        "AIMessageChunk": "assistant",
        "tool": "tool",
        "ToolMessage": "tool",
    }
    d = {"role": role_map.get(msg.type, "assistant" if "AI" in str(msg.type) else msg.type), "content": msg.content}
    tool_call_id = getattr(msg, "tool_call_id", None)
    if tool_call_id:
        d["tool_call_id"] = tool_call_id
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        d["tool_calls"] = [
            {
                "name": tc.get("name", ""),
                "args": tc.get("args", {}),
                "id": tc.get("id", ""),
                "type": tc.get("type", "tool_call"),

            }
            for tc in tool_calls
        ]
    return d


def dict_to_msg(d: dict):
    """纯 dict → LangChain 消息。"""
    role = d["role"]
    if role == "user":
        return HumanMessage(content=d["content"])
    if role == "assistant":
        tool_calls = d.get("tool_calls")
        if tool_calls:
            return AIMessage(
                content=d["content"],
                tool_calls=[
                    {
                        "name": tc.get("name", ""),
                        "args": tc.get("args", {}),
                        "id": tc.get("id", ""),
                        "type": "tool_call",
                    }
                    for tc in tool_calls
                ],
            )
        return AIMessage(content=d["content"])
    if role == "tool":
        return ToolMessage(
            content=d["content"],
            tool_call_id=d.get("tool_call_id") or "recovered",
        )
    return None

#上下文压缩
MAX_HISTORY = 100        # 超过这条数就压缩
KEEP_RECENT = 5        # 压缩后保留最近多少条
def compact_history(history:list,summary:str)->list:
    """把历史压缩成: [摘要消息] + 最近 KEEP_RECENT 条。"""
    recent=history[-KEEP_RECENT:]
    return [{"role": "user", "content": f"[对话摘要] {summary}"}] + recent

def generate_summary(old_part:list)->str:
    """让模型总结一段对话历史。"""
    lines = []
    for m in old_part:
        lines.append(f"{m['role']}: {m['content'][:100]}")
    text = "\n".join(lines)
    prompt=[
        {"role": "system", "content": "你是摘要助手。把下面的对话压缩成 2-3 句话的摘要，保留关键事实（做了什么、改了什么文件、用户偏好）。只输出摘要。"},
        {"role": "user", "content": f"对话记录：\n{text}"},
    ]
    response=model.invoke(prompt)
    return response.content


def main():
    console.print(f"[dim]会话目录: {SESSIONS_DIR}[/dim]")
    app = build_app()
    console.print("[bold cyan]^-^ 小助手已启动。输入任务开始，输入 /exit 退出。[/bold cyan]")
    history = []
    sessions = list_sessions()

    sid = None
    if sessions:
        console.print(f"[dim]历史会话: {', '.join(sessions[:3])}[/dim]")
        sid = input("输入会话 id 恢复（回车开新会话）: ").strip()
        if sid:
            loaded = load_session(sid)
            history = loaded if loaded is not None else []
            console.print(f"[dim]已恢复会话 {sid}（{len(history)} 条消息）[/dim]")


    while True:
        user_input = input("> ").strip()
        if not user_input:
            continue
        if user_input == "/exit":
            if history:
                sid = save_session(history, sid)
                console.print(f"[dim]会话已保存: {sid}[/dim]")
            console.print("再见！")
            break

        console.print(f"[bold cyan]你:[/bold cyan] {user_input}")

        # 先把用户消息存进历史（关键修复：user 必须进 history）
        history.append({"role": "user", "content": user_input})

        # 生成摘要：取"摘要之前的内容"（history[:-KEEP_RECENT]）让 LLM 总结

        if len(history) > MAX_HISTORY:
            old_part = history[:-KEEP_RECENT]
            summary = generate_summary(old_part)
            history = compact_history(history, summary)
            console.print(f"[dim] 上下文已压缩（{len(old_part)} 条 → 摘要）[/dim]")



        #  转成 LangChain 消息喂图（user 已在 history 里，不用再拼）
        lc_history = [m for m in (dict_to_msg(x) for x in history) if m is not None]
        # 收集本轮所有 chunk，拼成完整消息
        reply_chunks = []
        streaming = False
        for msg_chunk, metadata in app.stream({"messages": lc_history}, stream_mode="messages"):
            node = metadata.get("langgraph_node")
            if not isinstance(msg_chunk, BaseMessage):
                continue
            if node == "call_model":
                console.print(msg_chunk.content, end="", style="bold green")
                streaming = True
                if reply_chunks and reply_chunks[-1].type == msg_chunk.type:
                    reply_chunks[-1] += msg_chunk
                else:
                    reply_chunks.append(msg_chunk)
            elif node == "tools":
                if streaming:
                    console.print("\n")
                    streaming = False
                console.print(f"[dim] {msg_chunk.content[:200]}[/dim]")
                if reply_chunks and reply_chunks[-1].type == msg_chunk.type:
                    reply_chunks[-1] += msg_chunk
                else:
                    reply_chunks.append(msg_chunk)
        console.print("\n")

        for m in reply_chunks:
            history.append(msg_to_dict(m))



        #  本轮结束统一保存
        try:
            sid = save_session(history, sid)
            console.print(f"[dim]✓ 已保存 {len(history)} 条到 {sid}[/dim]")
        except Exception as e:
            console.print(f"[bold red]✗ 保存失败: {type(e).__name__}: {e}[/bold red]")
            raise
        console.print("  ")


if __name__ == "__main__":
    main()