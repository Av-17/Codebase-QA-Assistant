🧠 Codebase QA Assistant

An AI-powered assistant that analyzes GitHub codebases and answers natural language questions using LLMs, vector databases, and agents.

Now built with a React frontend and a FastAPI backend for a full-stack developer experience.

🚀 Features

📂 Fetch and analyze any GitHub repository (public or private)

🔍 Chunk and embed source code files (Python, HTML, JS, etc.)

🤖 Ask natural language questions about the codebase

🛡️ Secure handling of secrets (API keys not exposed to frontend)

⚡ Powered by LangChain agents, Google GenAI embeddings, and vector databases (FAISS/Chroma)

🌐 Modern React frontend with GitHub login + interactive UI

⚙️ FastAPI backend managing agent workflow and retrieval

📂 Project Structure
Codebase-QA-Assistant/
│── frontend/              # React app (UI + routing)
│   ├── src/
│   │   ├── App.js
│   │   ├── pages/
│   │   │   ├── LoginPage.js
│   │   │   └── HomePage.js
│   │   └── ...
│   └── package.json
│
│── backend/               # FastAPI + AI Agent
│   ├── agent.py           # Core agent logic
│   ├── load.py            # Load embeddings/models
│   ├── vectorDB.py        # Vector database setup + retrieval
│   ├── main.py            # FastAPI server
│   └── requirements.txt
│
│── README.md              # Project documentation

⚙️ Setup Instructions
🔹 1. Clone the Repo
git clone https://github.com/Av-17/Codebase-QA-Assistant.git
cd Codebase-QA-Assistant
