import { useState, useEffect, useRef } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'

function App() {
  const [count, setCount] = useState(0)
  const [isTalking, setIsTalking] = useState(false);
  const [logs, setLogs] = useState(["Hello! It is your voice assistant. I am here to help you make a new schefule on Google Calendar. Let me know how can I help!"]);

  const logEndRef = useRef(null); // 1. Create the ref

  // 2. This hook watches the logs. Every time they change, it scrolls.
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const toggleTalk = () => {
    const newState = !isTalking;
    setIsTalking(newState);

    const timestamp = new Date().toLocaleTimeString();
    const message = newState ? "Started talking..." : "Stopped talking.";
    // setLogs((prev) => [`[${timestamp}] ${message}`, ...prev]);
    setLogs((prev) => [...prev, `[${timestamp}] ${message}`]);
  };

  return (
    <div className="p-8 font-sans">
      {/* Button with dynamic Tailwind classes */}
      <button
        onClick={toggleTalk}
        className={`px-6 py-2 rounded-lg font-semibold text-white transition-colors duration-200 
          ${isTalking ? 'bg-red-500 hover:bg-red-600' : 'bg-green-600 hover:bg-green-700'}`}
      >
        {isTalking ? 'Stop' : 'Talk'}
      </button>


      <div className="w-[300px] h-[300px] border-4 border-[#121212] box-border overflow-y-auto text-left">

        <div className="space-y-2">
            {logs.map((log, i) => (
              <div key={i} className="animate-in fade-in slide-in-from-left-2 duration-300">
                {log}
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
          
      </div>

    </div>
  )
}

export default App
