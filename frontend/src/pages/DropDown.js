import { useState, useRef, useEffect } from "react";
import "../components/CustomDropDown.css";

function DropDown({ repos, username, setRepoUrl }) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState("");
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (repo) => {
    setSelected(repo);
    setRepoUrl(`https://github.com/${username}/${repo}`);
    setOpen(false);
  };

  return (
    <div className="custom-dropdown" ref={dropdownRef}>
      <button
        className="dropdown-btn"
        onClick={() => setOpen(!open)}
      >
        {selected || "-- Choose a repo --"}
      </button>

      {open && (
        <div className="dropdown-list">
          {repos.map((repo) => (
            <div
              key={repo}
              className="dropdown-item"
              onClick={() => handleSelect(repo)}
            >
              {repo}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default DropDown;
