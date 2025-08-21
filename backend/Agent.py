from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END, add_messages
from vectoreDB import my_retriever
from langchain_core.messages import HumanMessage, BaseMessage,SystemMessage, AIMessage
from typing import TypedDict, List, Optional, Annotated, Literal
from dotenv import load_dotenv
from langchain.docstore.document import Document
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from load import fetch_github, chunk_splitter
from vectoreDB import my_retriever
import asyncio
import os
# Load environment variables
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
from load import fetch_github, chunk_splitter
from vectoreDB import my_retriever
# print(GITHUB_TOKEN)
data = asyncio.run(fetch_github(repo_url="https://github.com/Av-17/AI-Driven-Stock-Predictor",token=GITHUB_TOKEN))
chunks = chunk_splitter(data)

# LLM initialization
try:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
except Exception as e:
    raise RuntimeError(f"Failed to initialize LLM: {e}")

# State type definition
class AgentState(TypedDict):
    question: str
    chunks: Optional[List[Document]]
    retriever_doc: Optional[List[Document]]
    messages : Annotated[List[BaseMessage], add_messages]
    onChat : str

checkpointer = MemorySaver()

class GradeQuestion(BaseModel):
    score: Literal["yes", "no"] = Field(
        description="yes if general/non-repo, no if repo-related"
    )

def intend_classifier(state: AgentState):
    state["onChat"] = ""
    past_messages = state.get("messages", [])[-2:]
    user_input = state.get("question", "")
   
    # print("enterd into having message")
    formatted_conversation = ""
    for msg in past_messages:
        role = msg.__class__.__name__.replace("Message","")
        # print(f"role in intend : {role}")
        # print(f"content in intend : {msg.content}")

        formatted_conversation += f"{role}: {msg.content}\n"
    if not formatted_conversation:
        formatted_conversation = HumanMessage(content=f"user_input : {user_input}")
        
    system_prompt = SystemMessage(content=f"""
        You are an intent classifier for a codebase Q&A system.

        Task:
        - Respond "no" if the user’s question requires fetching content from the repository 
        (e.g., asking about specific functions, classes, file contents, or definitions).
        - Respond "yes" if the user’s question can be answered without fetching files 
        (e.g., general programming questions, conceptual questions, or if the user 
        already provides the code snippet to explain).

        Guidelines:
        - If the question mentions specific files, functions, or classes from the repo → "no".
        - If the question is theoretical, about models/algorithms, or includes its own code 
        snippet for explanation → "yes".
        - Use the past conversation for context: if the user’s input is a follow-up to a repo-related 
        question (e.g., "and what about that function?"), classify it as "no".

        Only output a single word: yes or no.

        Past conversation:
        {formatted_conversation}

        """)

    human_message = HumanMessage(
                        content=f"user_input : {user_input}"
                    )
    grade_prompt = ChatPromptTemplate.from_messages([system_prompt, human_message])
    structured_llm = llm.with_structured_output(GradeQuestion)
    grader_llm = grade_prompt | structured_llm
    result = grader_llm.invoke({})
    state["onChat"] = result.score.strip()
    return state


def on_topic_router(state: AgentState):
            # print("Entering on_topic_router")
            on_topic = state.get("onChat", "").strip().lower()
            if on_topic == "yes":
                # print("Routing to answer node")
                return "answer_node"
            else:
                # print("Routing to retrieve node")
                return "retriever_node"

    


# LLM-based file classifier
def classify_query_with_llm(query: str, available_files: list[str]) -> str:
    file_list = "\n".join(available_files)
    prompt = f"""
You are a smart assistant that classifies the user's question based on the provided project files.

Files available in the project:
{file_list}

User Question:
{query}

Classify the question into exactly one of these categories:
- py → Python code
- html → HTML files
- css → CSS styling/layout
- js → JavaScript
- ts → TypeScript
- java → Java code
- directory → Questions about file/folder
- general -> if user want explanation of full project/repo
- other → Anything outside the project or unrelated

Rules:
1. Respond with exactly one category label in lowercase (no explanation).
2. If unsure, output "other".
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
        # print(file_type)
        if file_type in ["directory", "dir", "folder", "directory_structure"]:
            # print("enter in DIR")
            router_prompt = ChatPromptTemplate.from_template("""
            You are a classifier for user queries about project directories.

            Decide if the query is:
            - "general" → The user wants overall project structure (all folders).
            - "specific" → The user wants only a particular folder.

            Query: {query}

            Return ONLY one word: "general" or "specific".
            """)

            router_chain = router_prompt | llm  # llm = your chosen LLM
            route = router_chain.invoke({"query": ques}).content.strip().lower()
            if route == "general":
        # return all directories
                all_dirs = list({doc.metadata.get("dir", "") for doc in chunks if doc.metadata.get("dir")})
                # print(f"All directories: {all_dirs}")
                filtered = [doc for doc in chunks if doc.metadata.get("dir", "") in all_dirs]

            elif route == "specific":
                keywords = ques.lower().split()
                filtered = [doc for doc in chunks if any(k in doc.metadata.get("dir", "").lower() for k in keywords)]
            # print(f"printing filterd chunks : {filtered}")
            return {**state, "retriever_doc": filtered}

        if file_type == "general":
            return {**state, "retriever_doc": chunks}

        if file_type == "other":
             return {**state, "retriever_doc": []}
        
        filtered_docs = [doc for doc in retrieved_docs if doc.metadata.get("type", "") == file_type]
        return {**state, "retriever_doc": filtered_docs or retrieved_docs}

    except Exception as e:
        raise RuntimeError(f"Retriever node failed: {e}")

# Answer generation
def answer_node(state: AgentState) -> AgentState:
    try:
        if state["onChat"].lower().strip() == "yes":
            # print(state["onChat"])
            ques = state["question"]
            past_conversation = state.get("messages", [])[-2:]
            formatted_conversation = ""
            for msg in past_conversation:
                role = msg.__class__.__name__.replace("Message","")
                formatted_conversation += f"{role}: {msg.content}\n"
                # print(f"role in answer node : {role}")
                # print(f"content in answer node : {msg.content}")

            if not formatted_conversation:
                formatted_conversation = HumanMessage(content=f"user_input : {ques}")
            prompt = f"""You are a Github Codebase AI.
            You must answer user queries related to their Github repo.
            Use the chat history to maintain context and avoid repeating questions.

            This is the past conversation so far:
            {formatted_conversation}

            This is the user’s new question:
            {ques}
            """
            stream = llm.invoke([HumanMessage(content=prompt)])
            state["messages"].append(HumanMessage(content=ques))
            state["messages"].append(AIMessage(content=stream.content.strip()))
            return state
        else:
            # print(state["onChat"])

            ques = state["question"]
            docs = state.get("retriever_doc",[]) or []
            # Past_conversation = state["messages"]
            context = "\n\n".join(
                f"# From Dir: {doc.metadata.get('source', 'unknown')}\n\n# File: {doc.metadata.get('filename', 'unknown')}\n\n{doc.page_content}"
                for doc in docs)

            prompt = f"""
    You are an expert AI assistant designed to help users understand GitHub codebases.

    Your job is to analyze the following code context and answer the user's question accurately.

    ---

    📁 Context:
    {context}

    ❓ User Question:
    {ques}

    ---
    Rules:
    1. Use only the code provided in CONTEXT. Do NOT invent or assume code.
    2. If no relevant code is found, respond naturally
    3. Show only the minimal code needed for the explanation (no unrelated lines).
    4. Explanations must be short, precise, and tied to the shown code.
    5. Keep the output format exactly as follows:
    """
            stream = llm.invoke([HumanMessage(content=prompt)])
            state["messages"].append(HumanMessage(content=ques))
            state["messages"].append(AIMessage(content=stream.content.strip()))
            return state
            

    except Exception as e:
        return {**state, "messages": f" Failed to generate answer: {e}"}

# LangGraph Setup
graph = StateGraph(AgentState)
graph.add_node("retriever_node", retriever_node)
graph.add_node("answer_node", answer_node)
graph.add_node("intend_classifier",intend_classifier)
graph.add_conditional_edges(
     "intend_classifier",
     on_topic_router,{
          "retriever_node" : "retriever_node",
          "answer_node" : "answer_node"
     }
)
graph.add_edge("retriever_node", "answer_node")
graph.add_edge("answer_node", END)
graph.set_entry_point("intend_classifier")

try:
    agent = graph.compile(checkpointer=checkpointer)
    while True:
        user = input("user : ").lower()
        if user in ["end","exit","stop"]:
             break
        else:
            response = agent.invoke({"question" : user,"chunks":chunks},config={"configurable": {"thread_id": 3}})
            print(response["messages"][-1].content)


except Exception as e:
    raise RuntimeError(f"LangGraph compilation failed: {e}")