from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END, add_messages
from vectoreDB import my_retriever
from langchain_core.messages import HumanMessage, BaseMessage
from typing import TypedDict, List, Optional, Annotated
from dotenv import load_dotenv
from langchain.docstore.document import Document
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from load import fetch_github, chunk_splitter
from vectoreDB import my_retriever
import asyncio
# Load environment variables
load_dotenv()


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

class GradeQuestion(BaseModel):# pydentic model to get structure output 
            score: str = Field(
                description="Question is about the specified topics? If yes -> 'Yes' if not -> 'No'"
            )

def intend_classifier(state: AgentState):
    state["onChat"] = ""
    prompt = f"""
    Classify the user input below as either:
    - "yes" if it's a friendly chat and not about Q&A on a codebase.
    - "no" if it's a Q&A about a codebase or files.

    User input: {state["question"]}
    Respond with only yes or no.
    """

    human_message = HumanMessage(
                    content=f"User question: {state['question']}"
                )
    grade_prompt = ChatPromptTemplate.from_messages([prompt, human_message])
    structured_llm = llm.with_structured_output(GradeQuestion)
    grader_llm = grade_prompt | structured_llm
    result = grader_llm.invoke({})
    state["onChat"] = result.score.strip()
    return state


def on_topic_router(state: AgentState):
            # print("Entering on_topic_router")
            on_topic = state.get("onChat", "").strip().lower()
            if on_topic == "yes":
                print("Routing to answer node")
                return "answer_node"
            else:
                print("Routing to retrieve node")
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
        print(file_type)
        if file_type in ["directory", "dir", "folder", "directory_structure"]:
            print("enter in DIR")
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

        # if file_type == "general":
        #     return {**state, "retriever_doc": chunks}

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
            print(state["onChat"])
            ques = state["question"]
            conversation = state["messages"]
            prompt = f'''You Github Codebase AI, where user can do QA to there Github repo.
                        but now user not want to do QA so Continue the conversation naturally based on the messages so far.
                        Use the chat history to maintain context and avoid repeating questions.
                        this is past conversation : {conversation}
                        this is user Question : {ques}
'''
            stream = llm.invoke([HumanMessage(content=prompt)])
            return {**state, "messages": stream.content.strip()}
        else:
            print(state["onChat"])

            ques = state["question"]
            docs = state.get("retriever_doc",[]) or []
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
    📄 Relevant Code:
    <minimal snippet>

    📝 Explanation:
    <precise explanation>
    """
            stream = llm.invoke([HumanMessage(content=prompt)])
            return {**state, "messages": stream.content.strip()}
            

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
    # while True:
    #     user = input("user : ").lower()
    #     if user in ["end","exit","stop"]:
    #          break
    #     else:
    #         response = agent.invoke({"question" : user,"chunks":chunks},config={"configurable": {"thread_id": 3}})
    #         print(response["messages"][-1].content)


except Exception as e:
    raise RuntimeError(f"LangGraph compilation failed: {e}")