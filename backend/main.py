from fastapi import FastAPI, Request, Query, HTTPException, Header, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
import os, requests
from urllib.parse import urlencode
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from load import fetch_github, chunk_splitter
from Agent import agent
from typing import  Union, List, Dict, Any
from pydantic import BaseModel
from langchain_core.documents import Document
# load_dotenv(dotenv_path="../.env")
import json
load_dotenv()
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://codebase-qa-assistant.vercel.app/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI") 

@app.get("/login")
def login():
    if not all([CLIENT_ID, CLIENT_SECRET, REDIRECT_URI]):
        return JSONResponse({"error": "Missing GitHub OAuth configuration"}, status_code=500)

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "repo read:user",
        # "prompt": "consent"
    }
    github_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return RedirectResponse(github_url)

@app.get("/callback")
def callback(code: str):
    if not all([CLIENT_ID, CLIENT_SECRET, REDIRECT_URI]):
        return JSONResponse({"error": "Missing GitHub OAuth configuration"}, status_code=500)

    # Exchange code for access token
    token_res = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI
        }
    )
    token_data = token_res.json()
    token = token_data.get("access_token")

    if not token:
        # print(f"Failed to retrieve access token: {token_data}")
        return JSONResponse({"error": "Failed to retrieve access token", "details": token_data.get("error_description", token_data.get("error"))}, status_code=400)

    
    user_res = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"token {token}"}
    )
    user_data = user_res.json()
    username = user_data.get("login", "unknown")

    if not username:
        # print(f"Failed to retrieve username: {user_data}") 
        username = "unknown"
    
    response = RedirectResponse(url=f"https://codebase-qa-assistant.vercel.app/home?username={username}")
    print(f"access token in callback {token}")
    # Set cookie for token - HTTPOnly and Secure recommended for security
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,  # Not accessible by JS
        secure=False,   # Set to True if using HTTPS in production
        max_age=3600*24*7,  # 7 days expiry
        samesite="lax"
    )
    return response

@app.get("/.well-known/appspecific/com.chrome.devtools.json")
def ignore_devtools():
    return {}

# to get all the repos of user

@app.get("/api/repos")
def get_repos(access_token: str = Cookie(None)):
    print(f"api access token : {access_token}")
    if not access_token:
        return {"error": "Not logged in"}

    # Call GitHub API to fetch repos
    repo_res = requests.get(
        "https://api.github.com/user/repos",
        headers={"Authorization": f"token {access_token}"}
    )

    if repo_res.status_code != 200:
        return {"error": "Failed to fetch repos", "details": repo_res.json()}

    repos = repo_res.json()
    repo_names = [repo["name"] for repo in repos]  # extract only repo names

    return {"repositories": repo_names}


repo_chunks_store = {}
@app.get("/fetch_repo")
async def fetch_repo(repo_url : str = Query(...), access_token : str = Cookie(...)):
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized: No access token provided")
    data = await fetch_github(repo_url,access_token)
    if len(data) == 0:
        return {"success": False,"message": "❌ At least one file must be there"}
    if len(data) > 100:
        return {"success": False,"message": "❌ Cannot fetch more than 100 files"}

    chunks = chunk_splitter(data)
    repo_chunks_store[repo_url] = chunks  # Save in memory

    return {"success" : True, "message": "✅ Repo fetched successfully"}


class DocumentModel(BaseModel):
    page_content: str
    metadata: Dict[str, Any] = {}

class AnswerQuestion(BaseModel):
    question: str
    repo_url : str

@app.post("/answer")
async def getAnswer(req : AnswerQuestion):
    chunks = repo_chunks_store.get(req.repo_url)  # repo_id could be repo_url or username
    if not chunks:
        return {"success" : False,"message": "❌  No repo data found","answer": None}

    response = agent.invoke({
        "question": req.question,
        "chunks": chunks
    },config={"configurable": {"thread_id": 3}})
    answer = response.get("messages", ["No answer returned"])[-1].content
    # print(f"printing chunks : {chunks}")
    return {"success": True, "message": "✅ Answer generated successfully", "answer": answer}


@app.post("/reset_repo")
async def reset_repo(repo_url: str = Query(...)):
    if repo_url in repo_chunks_store:
        del repo_chunks_store[repo_url]   # remove only that repo's chunks
        return {"success": False, "message": f"Repo {repo_url} has been reset."}
    return {"success": False, "message": f"Repo {repo_url} not found in store."}
