import { useState, useEffect, useRef } from 'react'
// import { ReactMediaRecorder } from "react-media-recorder";

import './App.css'

function App() {
  const [isTalking, setIsTalking] = useState(false);
  const [logs, setLogs] = useState(["Hello! It is your voice assistant. I am here to help you make a new schedule on Google Calendar. Let me know how can I help! Start scheduling by clicking the talk button!"]);
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

    const timestamp = new Date().toLocaleTimeString();
    const message = newState ? "Started talking..." : "Stopped talking.";
    setLogs((prev) => [...prev, `[${timestamp}] ${message}`]);
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
        const audioBlob = new Blob(audioChunks.current, { type: 'audio/webm' });
        // const audioUrl = URL.createObjectURL(audioBlob);

        const formData = new FormData();
        formData.append('audio', audioBlob, `recording-${Date.now()}.webm`);
        
        await fetch('/api/save-audio', {
          method: 'POST',
          body: formData,
        });
        try {
          console.log("Saving to project folder...");
          
          console.log("File saved successfully!");
        } catch (error) {
          console.log("Save failed: " + error);
        }
        // setLogs(`Recording saved. Size: ${(audioBlob.size / 1024).toFixed(1)} KB`);
        // console.log("Audio URL:", audioUrl);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.current.start();
      toggleTalk();
      // setLogs("Microphone active... recording.");
    } catch (err) {
      // setLogs("Error: Could not access microphone.");
      console.error(err);
    }
  };

  const stopRecording = () => {
    mediaRecorder.current?.stop();
    toggleTalk();
    // addLog("Recording stopped.");
  };

  return (
    <div className="p-8 font-sans">
      {/* Button to talk/stop */}
      <button
        // onClick={toggleTalk}
        onClick={isTalking ? stopRecording : startRecording}
        className={`px-6 py-2 rounded-lg font-semibold text-white transition-colors duration-200 
          ${isTalking ? 'bg-red-500 hover:bg-red-600' : 'bg-green-600 hover:bg-green-700'}`}
      >
        {isTalking ? 'Stop' : 'Talk'}
      </button>

      {/* padding */}
      <div className="h-[10px]" />

      {/* ui for the log board */}
      <div className="w-[600px] h-[300px] border-4 border-[#121212] box-border overflow-y-auto text-left">
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
