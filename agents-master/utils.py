from typing import Any, Dict, List, Callable, Optional
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
import uuid


def random_uuid():
    """生成随机 UUID 字符串。"""
    return str(uuid.uuid4())


async def astream_graph(
    graph: CompiledStateGraph,
    inputs: dict,
    config: Optional[RunnableConfig] = None,
    node_names: List[str] = [],
    callback: Optional[Callable] = None,
    stream_mode: str = "messages",
    include_subgraphs: bool = False,
) -> Dict[str, Any]:
    """
    异步流式执行 LangGraph，并将输出打印到终端或通过回调处理。

    参数:
        graph: 已编译的 LangGraph 图
        inputs: 图输入字典
        config: 运行配置（可选）
        node_names: 仅输出这些节点的内容；空列表表示全部输出
        callback: 每个 chunk 的回调，签名为 {"node": str, "content": Any}
        stream_mode: "messages" 或 "updates"
        include_subgraphs: 是否包含子图输出

    返回:
        最后一次 chunk 的结果字典
    """
    config = config or {}
    final_result = {}

    def format_namespace(namespace):
        return namespace[-1].split(":")[0] if len(namespace) > 0 else "root graph"

    prev_node = ""

    if stream_mode == "messages":
        async for chunk_msg, metadata in graph.astream(
            inputs, config, stream_mode=stream_mode
        ):
            curr_node = metadata["langgraph_node"]
            final_result = {
                "node": curr_node,
                "content": chunk_msg,
                "metadata": metadata,
            }

            # node_names 为空或当前节点在列表中时才处理
            if not node_names or curr_node in node_names:
                if callback:
                    result = callback({"node": curr_node, "content": chunk_msg})
                    if hasattr(result, "__await__"):
                        await result
                else:
                    # 节点切换时打印分隔线
                    if curr_node != prev_node:
                        print("\n" + "=" * 50)
                        print(f"🔄 节点: \033[1;36m{curr_node}\033[0m 🔄")
                        print("- " * 25)

                    # 提取文本内容（兼容 Claude/OpenAI 等多种 chunk 格式）
                    if hasattr(chunk_msg, "content"):
                        if isinstance(chunk_msg.content, list):
                            for item in chunk_msg.content:
                                if isinstance(item, dict) and "text" in item:
                                    print(item["text"], end="", flush=True)
                        elif isinstance(chunk_msg.content, str):
                            print(chunk_msg.content, end="", flush=True)
                    else:
                        print(chunk_msg, end="", flush=True)

                prev_node = curr_node

    elif stream_mode == "updates":
        async for chunk in graph.astream(
            inputs, config, stream_mode=stream_mode, subgraphs=include_subgraphs
        ):
            # 兼容 (namespace, chunk_dict) 与单 dict 两种返回格式
            if isinstance(chunk, tuple) and len(chunk) == 2:
                namespace, node_chunks = chunk
            else:
                namespace = []
                node_chunks = chunk

            if isinstance(node_chunks, dict):
                for node_name, node_chunk in node_chunks.items():
                    final_result = {
                        "node": node_name,
                        "content": node_chunk,
                        "namespace": namespace,
                    }

                    if len(node_names) > 0 and node_name not in node_names:
                        continue

                    if callback is not None:
                        result = callback({"node": node_name, "content": node_chunk})
                        if hasattr(result, "__await__"):
                            await result
                    else:
                        if node_name != prev_node:
                            print("\n" + "=" * 50)
                            print(f"🔄 节点: \033[1;36m{node_name}\033[0m 🔄")
                            print("- " * 25)

                        if isinstance(node_chunk, dict):
                            for k, v in node_chunk.items():
                                if isinstance(v, BaseMessage):
                                    if hasattr(v, "content"):
                                        if isinstance(v.content, list):
                                            for item in v.content:
                                                if (
                                                    isinstance(item, dict)
                                                    and "text" in item
                                                ):
                                                    print(
                                                        item["text"], end="", flush=True
                                                    )
                                        else:
                                            print(v.content, end="", flush=True)
                                    else:
                                        v.pretty_print()
                                elif isinstance(v, list):
                                    for list_item in v:
                                        if isinstance(list_item, BaseMessage):
                                            if hasattr(list_item, "content"):
                                                if isinstance(list_item.content, list):
                                                    for item in list_item.content:
                                                        if (
                                                            isinstance(item, dict)
                                                            and "text" in item
                                                        ):
                                                            print(
                                                                item["text"],
                                                                end="",
                                                                flush=True,
                                                            )
                                                else:
                                                    print(
                                                        list_item.content,
                                                        end="",
                                                        flush=True,
                                                    )
                                            else:
                                                list_item.pretty_print()
                                        elif (
                                            isinstance(list_item, dict)
                                            and "text" in list_item
                                        ):
                                            print(list_item["text"], end="", flush=True)
                                        else:
                                            print(list_item, end="", flush=True)
                                elif isinstance(v, dict) and "text" in v:
                                    print(v["text"], end="", flush=True)
                                else:
                                    print(v, end="", flush=True)
                        elif node_chunk is not None:
                            if hasattr(node_chunk, "__iter__") and not isinstance(
                                node_chunk, str
                            ):
                                for item in node_chunk:
                                    if isinstance(item, dict) and "text" in item:
                                        print(item["text"], end="", flush=True)
                                    else:
                                        print(item, end="", flush=True)
                            else:
                                print(node_chunk, end="", flush=True)

                    prev_node = node_name
            else:
                print("\n" + "=" * 50)
                print("🔄 原始输出 🔄")
                print("- " * 25)
                print(node_chunks, end="", flush=True)
                final_result = {"content": node_chunks}

    else:
        raise ValueError(
            f"无效的 stream_mode: {stream_mode}，必须是 'messages' 或 'updates'。"
        )

    return final_result


async def ainvoke_graph(
    graph: CompiledStateGraph,
    inputs: dict,
    config: Optional[RunnableConfig] = None,
    node_names: List[str] = [],
    callback: Optional[Callable] = None,
    include_subgraphs: bool = True,
) -> Dict[str, Any]:
    """
    异步流式执行 LangGraph（updates 模式），打印各节点更新并返回最终结果。

    参数:
        graph: 已编译的 LangGraph 图
        inputs: 图输入字典
        config: 运行配置（可选）
        node_names: 仅输出指定节点；空列表表示全部
        callback: 每个 chunk 的回调
        include_subgraphs: 是否包含子图

    返回:
        最后一个节点的输出字典
    """
    config = config or {}
    final_result = {}

    def format_namespace(namespace):
        return namespace[-1].split(":")[0] if len(namespace) > 0 else "root graph"

    async for chunk in graph.astream(
        inputs, config, stream_mode="updates", subgraphs=include_subgraphs
    ):
        if isinstance(chunk, tuple) and len(chunk) == 2:
            namespace, node_chunks = chunk
        else:
            namespace = []
            node_chunks = chunk

        if isinstance(node_chunks, dict):
            for node_name, node_chunk in node_chunks.items():
                final_result = {
                    "node": node_name,
                    "content": node_chunk,
                    "namespace": namespace,
                }

                if node_names and node_name not in node_names:
                    continue

                if callback is not None:
                    result = callback({"node": node_name, "content": node_chunk})
                    if hasattr(result, "__await__"):
                        await result
                else:
                    print("\n" + "=" * 50)
                    formatted_namespace = format_namespace(namespace)
                    if formatted_namespace == "root graph":
                        print(f"🔄 节点: \033[1;36m{node_name}\033[0m 🔄")
                    else:
                        print(
                            f"🔄 节点: \033[1;36m{node_name}\033[0m "
                            f"in [\033[1;33m{formatted_namespace}\033[0m] 🔄"
                        )
                    print("- " * 25)

                    if isinstance(node_chunk, dict):
                        for k, v in node_chunk.items():
                            if isinstance(v, BaseMessage):
                                v.pretty_print()
                            elif isinstance(v, list):
                                for list_item in v:
                                    if isinstance(list_item, BaseMessage):
                                        list_item.pretty_print()
                                    else:
                                        print(list_item)
                            elif isinstance(v, dict):
                                for node_chunk_key, node_chunk_value in v.items():
                                    print(f"{node_chunk_key}:\n{node_chunk_value}")
                            else:
                                print(f"\033[1;32m{k}\033[0m:\n{v}")
                    elif node_chunk is not None:
                        if hasattr(node_chunk, "__iter__") and not isinstance(
                            node_chunk, str
                        ):
                            for item in node_chunk:
                                print(item)
                        else:
                            print(node_chunk)
                    print("=" * 50)
        else:
            print("\n" + "=" * 50)
            print("🔄 原始输出 🔄")
            print("- " * 25)
            print(node_chunks)
            print("=" * 50)
            final_result = {"content": node_chunks}

    return final_result
