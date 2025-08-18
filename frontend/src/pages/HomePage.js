import React, { useState, useEffect } from 'react';
import '../components/HomePage.css'; // Import the CSS file
import { useLocation } from 'react-router-dom';
import ReactMarkdown from "react-markdown";
function HomePage() {
  const [repoUrl, setRepoUrl] = useState("");
  const [question, setQuestion] = useState("");
  // const [token, setToken] = useState("");
  const [username, setusername] = useState("");
  // const [Chunks, setChunks] = useState("");
  const [conversation, setConversation] = useState([]);
  const [repoMessage, setRepoMessage] = useState(null);
  const [ansmessage, setansmessage] = useState("");
  const [isFetchingRepo, setIsFetchingRepo] = useState(false);
  const [isGettingAnswer, setIsGettingAnswer] = useState(false);


  const location = useLocation()

  useEffect (() =>{
  const param = new URLSearchParams(location.search);
  // const tokenFromURL  = param.get("token");
  const usernameFromURL  = param.get("username");
  // setToken(tokenFromURL);
  setusername(usernameFromURL);

  },[location])


const showRepoMessage = (message) => {
  setRepoMessage(message);
  setTimeout(() => {
    setRepoMessage("");
  }, 5000); // Clear after 5 seconds
};

const showansMessage = (message) => {
  setansmessage(message);
  setTimeout(() => {
    setansmessage("");
  }, 5000); // Clear after 5 seconds
};

const handleFetchRepo = async () => {
  console.log('Fetching repo:', repoUrl);
  setIsFetchingRepo(true);
  try {
    const res = await fetch(
      `http://localhost:8000/fetch_repo?repo_url=${encodeURIComponent(repoUrl)}`,{
      
        method : "GET",
        credentials: "include"
      }
    );
    const data = await res.json();

    // setChunks(data);
    showRepoMessage(`${data.message}`);
    console.log("chunk data \n", data);

  } catch (error) {
    console.error("Error:", error);
    showRepoMessage("❌  to fetch repository. Please try again.");
  }
  finally {
    setIsFetchingRepo(false);  // stop spinner
  }
};


  const handleResetRepo = async () => {
  console.log("Resetting repo...");
  setIsFetchingRepo(true);
  try {
    const res = await fetch(`http://localhost:8000/reset_repo?repo_url=${encodeURIComponent(repoUrl)}`,{
      method: "POST",           // better to use POST for reset
      credentials: "include",   // send cookies/session
    });

    const data = await res.json();

    // ✅ Clear frontend states
    setRepoUrl("");
    // setConversation([]);   // clear chat history
    // setChunks([]);       // if you keep repo chunks in state
    showRepoMessage({ text: data.message, success: data.success });

    console.log("Repo reset response:", data);
  } catch (error) {
    console.error("Error resetting repo:", error);
    showRepoMessage("❌ Failed to reset repository. Please try again.");
  } finally {
    setIsFetchingRepo(false);
  }
};


  const handleQuestionChange = async () => {
    console.log("entered  into answer");
  if (!question.trim()) 
    {showansMessage("⚠️ enter the question first");
      return;
    }
    setIsGettingAnswer(true);
  try {
    const ans = await fetch(`http://localhost:8000/answer`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        question: question,
        repo_url : repoUrl
      })
    });

    const data = await ans.json();
    if (!data.success) {
    showansMessage({text : data.message, success : data.success});
    }
    else{
      
          // Append question + answer to conversation
          setConversation(prev => [
            ...prev,
            { type: "user", text: question },
            { type: "ai", text: data.answer }
          ]);
      
          setQuestion(""); // clear input

    }
    console.log("AI response", data);
  } catch (error) {
    console.error("Error:", error);
  }
  finally {
    setIsGettingAnswer(false); // stop spinner
  }
};


  return (
    <div className="container">
      <h1 className="title">🚀 Codebase Agent</h1>

      {username ? (
  <div className="user-info">
    <p><strong>👤 Name:</strong> {username || "N/A"}</p>
  </div>
) : (
  <p>Loading user info...</p>
)}

      <div className="section">
        <label htmlFor="repoUrl" className="label">🔗 Repository URL:</label>
        <input
          type="text"
          id="repoUrl"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          placeholder="https://github.com/user/repo"
          className="input"
        />
        <div className="button-group">
          <button
  onClick={handleFetchRepo}
  className="btn fetch-btn"
  disabled={isFetchingRepo}
>
  {isFetchingRepo ? (
    <>
      ⏳ Fetching...
      <div className="spinner" style={{ display: 'inline-block', marginLeft: 8 }}></div>
    </>
  ) : (
    "📥 Fetch Repo"
  )}
</button>
          <button onClick={handleResetRepo} className="btn reset-btn">♻️ Clear Repo</button>
        </div>
      </div>
      {/* ✅ Message display */}
{repoMessage && (
  <p style={{ marginTop: "0.5rem", color: repoMessage.success ? "green" : "red" }}>
    {repoMessage.text}
  </p>
)}

      <div className="section">
        <label htmlFor="question" className="label">💬 Ask a Question:</label>
        <input
          type="text"
          id="question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="What does this function do?"
          className="input"
        />
        <button onClick={handleQuestionChange} className="btn fetch-btn" disabled={isGettingAnswer}>
        {isGettingAnswer ? (
          <>
            ⏳ Thinking...
            <div className="spinner" style={{ display: 'inline-block', marginLeft: 8 }}></div>
          </>
        ) : (
          "Ask AI"
        )}
</button>
        {ansmessage && (
  <p style={{ marginTop: "0.5rem", color: ansmessage.success ? "green" : "red" }}>
    {ansmessage.text}
  </p>)}
      {/* Show AI answer below the question input */}
      <div className="chat-box">
  {conversation.map((msg, idx) => (
    <div key={idx} className={`chat-bubble ${msg.type === "user" ? "user-bubble" : "ai-bubble"}`}>
      <ReactMarkdown>{msg.text}</ReactMarkdown>
    </div>
  ))}
</div>
    </div>
      </div>
    
  );
}

export default HomePage;
