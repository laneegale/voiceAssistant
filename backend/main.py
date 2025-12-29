
import os
import shutil
from fastapi import FastAPI, File, UploadFile
from pydub import AudioSegment

app = FastAPI()

UPLOAD_DIR = "recordings"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)
mp3_path = os.path.join(UPLOAD_DIR, "talking.mp3")

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/api/save-audio")
async def save_audio(audio: UploadFile = File(...)):
# 1. Define paths
    temp_webm_path = os.path.join(UPLOAD_DIR, "temp_recording.webm")

    # 2. Save the incoming WebM file temporarily
    with open(temp_webm_path, "wb") as buffer:
        shutil.copyfileobj(audio.file, buffer)
        buffer.flush()

    try:
        audio_data = AudioSegment.from_file(temp_webm_path)
        audio_data.export(mp3_path, format="mp3")
        os.remove(temp_webm_path)
        
        print(f"Successfully converted to: {mp3_path}")
        return {"message": "Saved as MP3", "path": mp3_path}
        
    except Exception as e:
        print("bad", str(e))
        return {"message": "Conversion failed", "error": str(e)}