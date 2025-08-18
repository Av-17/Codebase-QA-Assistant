from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv
load_dotenv()
import asyncio
from langchain.docstore.document import Document

def my_retriever(chunks):
    if not chunks or not isinstance(chunks, list):
        raise ValueError("'chunks' must be a non-empty list of Document objects.")

    if not all(isinstance(chunk, Document) for chunk in chunks):
        raise ValueError("All items in 'chunks' must be of type langchain.docstore.document.Document.")

    try:
        embedding = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    except Exception as e:
        raise RuntimeError(f"Failed to initialize embedding model: {e}")

    try:
        vectorestore = FAISS.from_documents(chunks, embedding)
    except Exception as e:
        raise RuntimeError(f"Error while creating FAISS index: {e}")

    try:
        retriever = vectorestore.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 50, "lambda_mult": 0.5}
        )
    except Exception as e:
        raise RuntimeError(f"Failed to create retriever: {e}")

    return retriever

