from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from typing import Any

# 从 .env 加载 API Key 等配置
load_dotenv(override=True)


def create_retriever() -> Any:
    """
    构建基于 FAISS 的文档检索器。

    步骤:
        1. 加载 PDF（默认 data/sample.pdf）
        2. 切分文档
        3. 生成向量 Embedding
        4. 写入 FAISS 向量库
        5. 返回 retriever 接口

    返回:
        可用于相似度检索的 retriever 对象
    """
    # 1. 加载 PDF
    loader = PyMuPDFLoader("data/sample.pdf")
    docs = loader.load()

    # 2. 切分文档（保留重叠以维持上下文）
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=50)
    split_documents = text_splitter.split_documents(docs)

    # 3. 生成 Embedding（需 OPENAI_API_KEY）
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    # 4. 构建 FAISS 向量库
    vectorstore = FAISS.from_documents(documents=split_documents, embedding=embeddings)

    # 5. 创建检索器
    retriever = vectorstore.as_retriever()
    return retriever


# 初始化 RAG MCP 服务
mcp = FastMCP(
    "Retriever",
    instructions="文档检索器，可从向量库中检索与问题相关的段落。",
    host="0.0.0.0",
    port=8005,
)


@mcp.tool()
async def retrieve(query: str) -> str:
    """
    根据用户问题检索相关文档内容。

    参数:
        query: 检索关键词或自然语言问题

    返回:
        检索到的文档片段（多段以换行拼接）
    """
    # 每次调用新建 retriever；生产环境可考虑缓存向量库以提升性能
    retriever = create_retriever()

    retrieved_docs = retriever.invoke(query)

    return "\n".join([doc.page_content for doc in retrieved_docs])


if __name__ == "__main__":
    # stdio 启动，由 MCP Client 以子进程方式拉起
    mcp.run(transport="stdio")
