from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
# from github.GithubException import GithubException, UnknownObjectException
import aiohttp
import asyncio
import base64
from pprint import pprint

async def fetch_github(repo_url, token):
    async with aiohttp.ClientSession() as session:
        headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        valid_token = token.strip() if token else None
        # print(len(valid_token))
        # pprint(valid_token)
        if valid_token:
            headers["Authorization"] = f"token {valid_token}"

        # Extract owner/repo name
        repo_name = repo_url.replace("https://github.com/", "").strip("/")
        if '/' not in repo_name:
            raise ValueError("Invalid Repo URL format. Should be 'username/repo'")

        OWNER, REPO = repo_name.split("/")
        GITHUB_API = "https://api.github.com"
        url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/contents/"

        async def fetch_url(session, url):
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 404:
                        if "Authorization" not in resp.headers or not resp.headers["Authorization"]:
                            raise FileNotFoundError(f" Repo not found or it may be private. Try providing a GitHub token.\nURL: {url}")
                        else:
                            raise FileNotFoundError(f" Repo not found or it may be empty. If it's private, ensure your token has access.\nURL: {url}")

                    elif resp.status == 403:
                        detail = await resp.text()
                        raise PermissionError(f" Access denied (403). Reason: {detail}")
                    else:
                        raise Exception(f" Unexpected status {resp.status} for {url}")
            except aiohttp.ClientError as e:
                raise ConnectionError(f" Network error: {e}")
            
        async def fetch_content(session, url):
            items = await fetch_url(session, url)
            file_data = {}
            if not items:
                return file_data
            try :
                for item in items:
                    if item['type'] == 'file':
                        new_data = await fetch_url(session, item['url'])
                        if new_data and new_data.get('encoding') == 'base64':
                            content = base64.b64decode(new_data['content']).decode(errors='ignore')
                            file_data[new_data['path']] = content

                    elif item['type'] == 'dir':
                        subdata = await fetch_content(session, item['url'])
                        if subdata:
                            file_data.update(subdata)

                return file_data
            except Exception as e:
                        print(f"Error reading {item.get('path', 'unknown file')}: {e}")

        return await fetch_content(session, url)

def get_separators_for_extension(ext: str):
    ext = ext.lower()
    return {
        "py": ["\nclass ", "\ndef ", "\n\n", "\n", " "],
        "ipynb": ["\n\n", "\n", " "],
        "js": ["\nclass ", "\nfunction ", "\nconst ", "\nlet ", "\n\n", "\n", " "],
        "ts": ["\nclass ", "\nfunction ", "\nconst ", "\nlet ", "\n\n", "\n", " "],
        "jsx": ["\nfunction ", "\nconst ", "\nclass ", "\n\n", "\n", " "],
        "tsx": ["\nfunction ", "\nconst ", "\nclass ", "\n\n", "\n", " "],
        "java": ["\nclass ", "\npublic ", "\nprivate ", "\nprotected ", "\nvoid ", "\n\n", "\n", " "],
        "c": ["\nvoid ", "\nint ", "\nfloat ", "\nchar ", "\n\n", "\n", " "],
        "cpp": ["\nclass ", "\nnamespace ", "\nvoid ", "\nint ", "\n\n", "\n", " "],
        "cs": ["\nclass ", "\npublic ", "\nprivate ", "\nprotected ", "\nvoid ", "\n\n", "\n", " "],
        "go": ["\nfunc ", "\nvar ", "\n\n", "\n", " "],
        "rb": ["\ndef ", "\nclass ", "\nmodule ", "\n\n", "\n", " "],
        "rs": ["\nfn ", "\nstruct ", "\nimpl ", "\n\n", "\n", " "],
        "swift": ["\nfunc ", "\nclass ", "\nstruct ", "\n\n", "\n", " "],
        "kt": ["\nfun ", "\nclass ", "\nobject ", "\n\n", "\n", " "],
        "kts": ["\nfun ", "\nclass ", "\nobject ", "\n\n", "\n", " "],
        "php": ["\nfunction ", "\nclass ", "\n\n", "\n", " "],
        "sh": ["\nfunction ", "\n\n", "\n", " "],
        "bat": ["\n", " "],
        "ps1": ["\nfunction ", "\n\n", "\n", " "],
        "sql": [";\n", "\n", " "],
        "json": ["},", ",\n", "\n", " "],
        "yaml": ["\n-", "\n", " "],
        "yml": ["\n-", "\n", " "],
        "toml": ["\n[", "\n", " "],
        "ini": ["\n[", "\n", " "],
        "env": ["\n", " "],
        "md": ["\n## ", "\n# ", "\n\n", "\n", " "],
        "txt": ["\n\n", "\n", " "],
    }.get(ext, ["\n\n", "\n", " "])  


def chunk_splitter(code: dict) -> list[Document]:
    if not isinstance(code, dict):
        raise ValueError("'code' must be a dictionary with {filepath: content}.")

    docs = []
    for filepath, content in code.items():
        if not filepath or not isinstance(filepath, str):
            # print(f"⚠️ Skipping invalid file path: {filepath}")
            continue

        if '.' not in filepath:
            # print(f"Skipping {filepath}: no file extension found.")
            continue

        if not isinstance(content, str) or not content.strip():
            # print(f"Skipping {filepath}: content is empty or invalid.")
            continue

        file_exten = filepath.split('.')[-1].lower()
        filetype = file_exten if file_exten in [
            "py", "ipynb", "html", "htm", "js", "ts", "jsx", "tsx",
            "php", "java", "c", "cpp", "cs", "go", "rb", "rs", "swift",
            "kt", "kts", "css", "scss", "json", "yaml", "yml", "toml",
            "ini", "sh", "bat", "ps1", "sql", "xml", "md", "txt", "env"
        ] else "other"

        metadata = {
            "source": filepath,
            "type": filetype,
            "filename": filepath.split('/')[-1],
            "dir": "/".join(filepath.split('/')[:-1])
        }

        doc = Document(page_content=content, metadata=metadata)
        docs.append(doc)

    chunks = []
    for doc in docs:
        ext = doc.metadata["type"]
        if len(doc.page_content) < 100:
            chunks.append(doc)
            continue

        separators = get_separators_for_extension(ext)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=3000 if len(doc.page_content) > 5000 else 2000,
            chunk_overlap=300 if len(doc.page_content) > 5000 else 200,
            separators=separators
        )

        try:
            chunks.extend(splitter.split_documents([doc]))
        except Exception as e:
            print(f" Error splitting {doc.metadata['source']}: {str(e)}")

    return chunks