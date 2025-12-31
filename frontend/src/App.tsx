import { useState, useEffect, useRef } from 'react'

import './App.css'

interface CalendarApiResponse {
  // status: string;
  message: string;
  reply: string;
  audio: string;
  // state?: any;
  conflicted_date: string;
}

interface LoginResponse {
  reply: string;
  audio: string;
}

// const init_log_message = "Hi there! I’m your calendar assistant. I can help you schedule new meetings on Google Calendar. If you're not signed in your google account, a window will appear for you to log in.";
const init_log_message = "hi";

function App() {
  const [isStarted, setIsStarted] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isLoggingin, setIsLoggingin] = useState(false);
  const [isTalking, setIsTalking] = useState(false);
  const [logs, setLogs] = useState([""]);
  const logEndRef = useRef<HTMLDivElement>(null);

  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const audioChunks = useRef<Blob[]>([]);

  // Every time sth added to logs, it scrolls.
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const toggleTalk = () => {
    const newState = !isTalking;
    setIsTalking(newState);
  };

  const startRecording = async () => {
    try {
      // Get Microphone Access
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder.current = new MediaRecorder(stream);
      audioChunks.current = [];

      // Collect audio
      mediaRecorder.current.ondataavailable = (event) => {
        audioChunks.current.push(event.data);
      };

      // Audio on stop
      mediaRecorder.current.onstop = async () => {
        setIsProcessing(true);
        const audioBlob = new Blob(audioChunks.current, { type: 'audio/webm' });

        const formData = new FormData();
        formData.append('audio', audioBlob, `recording-${Date.now()}.webm`);

        const response = await fetch('/api/process', {
          method: 'POST',
          body: formData,
        });
        const data: CalendarApiResponse = await response.json();
        const timestamp = new Date().toLocaleTimeString();
        setLogs((prev) => [...prev, `[${timestamp}] You: ${data['message']}`]);
        setLogs((prev) => [...prev, `[${timestamp}] Assistant: ${data['reply']}`]);

        const audio = new Audio(`data:audio/mp3;base64,${data['audio']}`);
        await audio.play();

        stream.getTracks().forEach(track => track.stop());
        setIsProcessing(false);
      };

      mediaRecorder.current.start();
      toggleTalk();
    } catch (err) {
      console.error(err);
    }
  };

  const stopRecording = () => {
    mediaRecorder.current?.stop();
    toggleTalk();
  };

  const resetChat = async () => {
    await fetch('/api/reset', {
      method: 'POST',
    });
    setLogs(() => ['']);
  }

  const handleStart = async () => {
    setIsLoggingin(true);
    const response_welcome_msg_audio = await fetch(`/api/get-audio?text=${encodeURIComponent(init_log_message)}`, {
      method: 'POST',
    });
    const data: CalendarApiResponse = await response_welcome_msg_audio.json();
    const timestamp = new Date().toLocaleTimeString();
    setLogs(() => [`[${timestamp}] Assistant: ${init_log_message}`]);
    
    await new Promise((resolve, reject) => { 
      const audio = new Audio(`data:audio/mp3;base64,${data['audio']}`);

      audio.onended = () => resolve(true);
      audio.onerror = (err) => reject(err);

      setTimeout(() => {
        audio.play().catch(reject);
      }, 500);
    });

    const login_response = await fetch(`/api/login`, {
      method: 'GET',
    });
    const login_response_data: LoginResponse = await login_response.json();
    const login_status_audio = new Audio(`data:audio/mp3;base64,${login_response_data['audio']}`);
    const newtimestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, `[${newtimestamp}] Assistant: ${login_response_data['reply']}`]);
    await login_status_audio.play();

    setIsLoggingin(false);
    setIsStarted(true);
  };

  return (
    <div className="p-8 font-sans">

      <header className="mb-8 text-center">
        <h1 className="text-3xl font-mono font-bold tracking-[0.2em] uppercase text-green-500 drop-shadow-[0_0_8px_rgba(34,197,94,0.6)]">
          Google Calendar Assistant
          <span className="animate-pulse ml-2">_</span>
        </h1>
      </header>

      {/* Button to talk/stop */}
      {!isStarted ? (
        // Initial State
        <button onClick={handleStart} disabled={isLoggingin}>
          Start
        </button>
      ) : (
        // Active State
        <div className='flex gap-4 items-center justify-center'>
          <button
            onClick={isTalking ? stopRecording : startRecording}
            disabled={isProcessing}
          >
            {isProcessing
              ? 'Processing...'
              : (isTalking ? 'Stop' : 'Talk')
            }
          </button>
          <button
            onClick={resetChat}
            disabled={isProcessing}
          >
            Reset Chat
          </button>

        </div>
      )}

      {/* padding */}
      <div className="h-[10px]" />

      {/* ui for the log board */}
      <div
        id="log-container"
        className="terminal-log-board w-[600px] h-[300px] border-2 border-green-900 bg-black box-border overflow-y-auto text-left p-4 shadow-[inset_0_0_15px_rgba(0,0,0,1)]"
      >
        <div className="space-y-1">
          {logs.map((log, i) => (
            <div
              key={i}
              className="log-entry font-mono text-sm animate-in fade-in slide-in-from-left-2 duration-300"
            >
              <span className="text-green-500">{log}</span>
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      </div>

    </div>
  )
}

export default App
