import React from "react"

function Loginpage(){
    const handleLogin =() => {
        window.location.href = 'https://codebase-qa-assistant.onrender.com/login';
    };
    return (
    <div style={{ textAlign: 'center', marginTop: '50px' }}>
      <h1>Login with GitHub</h1>
      <button onClick={handleLogin} style={{ padding: '10px 20px', fontSize: '16px' }}>
        🔐 Login with GitHub
      </button>
    </div>
);
};

export default Loginpage;