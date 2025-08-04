from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from vectoreDB import my_retriever
from langchain_core.messages import HumanMessage
from typing import TypedDict, List, Optional
from dotenv import load_dotenv
from langchain.docstore.document import Document
import os
import streamlit as st
if 'GOOGLE_API_KEY' in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
# Load environment variables
load_dotenv()

# LLM initialization
try:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
except Exception as e:
    raise RuntimeError(f"Failed to initialize LLM: {e}")

# Token and repo config
# repo_owner_with_repo_name = "dexkor-tech/B2C-Backend"
# api_token = os.getenv("GITHUB_API_TOKEN")

# State type definition
class AgentState(TypedDict):
    question: str
    chunks: List[Document]
    retriever_doc: Optional[List[Document]]
    answer: Optional[str]

# LLM-based file classifier
def classify_query_with_llm(query: str, available_files: list[str]) -> str:
    file_list = "\n".join(available_files)
    prompt = f"""
        You are a smart assistant helping decide which type of code a user's question is about.
        Files:
        {file_list}

        Question: "{query}"

        Classify the question as one of: py, html, css, js, ts, java, directory_structure, general, other.
    """
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip().lower()
    except Exception as e:
        return "general" 

# Retriever logic
def retriever_node(state: AgentState) -> AgentState:
    try:
        ques = state["question"]
        chunks = state["chunks"]
        retriever = my_retriever(chunks)
        retrieved_docs = retriever.invoke(ques)

        available_files = [doc.metadata.get("source", "") for doc in retrieved_docs]
        file_type = classify_query_with_llm(ques, available_files)

        if file_type in ["directory", "dir", "folder", "directory_structure"]:
            keywords = ques.lower().split()
            filtered = [doc for doc in chunks if any(k in doc.metadata.get("dir", "").lower() for k in keywords)]
            return {**state, "retriever_doc": filtered or retrieved_docs}

        if file_type == "general":
            return {**state, "retriever_doc": chunks}

        filtered_docs = [doc for doc in retrieved_docs if doc.metadata.get("type", "") == file_type]
        return {**state, "retriever_doc": filtered_docs or retrieved_docs}

    except Exception as e:
        raise RuntimeError(f"Retriever node failed: {e}")

# Answer generation
def answer_node(state: AgentState) -> AgentState:
    try:
        ques = state["question"]
        docs = state["retriever_doc"] or []
        context = "\n\n".join(
            f"# From Dir: {doc.metadata.get('source', 'unknown')}\n\n# File: {doc.metadata.get('filename', 'unknown')}\n\n{doc.page_content}"
            for doc in docs)

        prompt = f"""
You are an expert AI assistant designed to help users understand GitHub codebases.

Your job is to analyze the following code context and answer the user's question accurately.

---

📁 Project Context:
{context}

❓ User Question:
{ques}

---

🎯 Instructions:
- Extract and explain only the **relevant** code related to the question.
- If the question is about **project structure** or file organization, provide a concise summary.
- For implementation-specific questions, focus only on the **core logic** and avoid unrelated details.
- When needed, simplify technical terms but preserve accuracy.
- Be clear, concise, and helpful — like a senior developer reviewing code for a junior.

Respond only based on the available context. If the answer is not in the provided code, say so.
"""
        stream = llm.invoke([HumanMessage(content=prompt)])
        return {**state, "answer": stream.content.strip()}

    except Exception as e:
        return {**state, "answer": f" Failed to generate answer: {e}"}

# LangGraph Setup
graph = StateGraph(AgentState)
graph.add_node("retriever_node", retriever_node)
graph.add_node("answer_node", answer_node)
graph.add_edge("retriever_node", "answer_node")
graph.add_edge("answer_node", END)
graph.set_entry_point("retriever_node")

try:
    app = graph.compile()
except Exception as e:
    raise RuntimeError(f"LangGraph compilation failed: {e}")