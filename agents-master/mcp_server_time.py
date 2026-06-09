from mcp.server.fastmcp import FastMCP
from datetime import datetime
import pytz
from typing import Optional

# 初始化 FastMCP 服务
mcp = FastMCP(
    "TimeService",  # MCP 服务名称
    instructions="你是时间助手，可查询不同时区的当前时间。",  # 供 LLM 理解如何使用该工具
    host="0.0.0.0",  # 监听地址（0.0.0.0 表示允许任意 IP 连接，SSE 模式用）
    port=8005,  # 端口号（SSE 模式用）
)


@mcp.tool()
async def get_current_time(timezone: Optional[str] = "Asia/Shanghai") -> str:
    """
    查询指定时区的当前时间。

    参数:
        timezone: IANA 时区名，默认 Asia/Shanghai

    返回:
        当前时间的格式化字符串
    """
    try:
        # 解析时区
        tz = pytz.timezone(timezone)

        # 获取该时区下的当前时间
        current_time = datetime.now(tz)

        # 格式化为可读字符串
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S %Z")

        return f"{timezone} 当前时间：{formatted_time}"
    except pytz.exceptions.UnknownTimeZoneError:
        return f"错误：未知时区 '{timezone}'，请提供有效的 IANA 时区名。"
    except Exception as e:
        return f"获取时间失败：{str(e)}"


if __name__ == "__main__":
    # 以 stdio 方式启动 MCP 服务
    # stdio 通过标准输入/输出与 Client 通信，适合本地子进程集成（与 config.json 一致）
    mcp.run(transport="stdio")
