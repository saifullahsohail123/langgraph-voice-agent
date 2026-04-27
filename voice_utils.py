import whisper
import edge_tts
import pygame
import tempfile
import os
import asyncio
import numpy as np
from scipy.io.wavfile import write

try:
    import sounddevice as sd
except OSError:
    sd = None

# Load Whisper model once (using 'small' for better accuracy)
print("Loading Whisper model...")
stt_model = whisper.load_model("small")

async def record_audio_until_stop():
    """Records audio from the microphone until Enter is pressed and transcribes it."""
    sample_rate = 16000
    audio_data = []
    recording = True

    if sd is None:
        print("⚠️ PortAudio not found. Native recording disabled.")
        return input("You (type): ")

    def callback(indata, frames, time, status):
        if recording:
            audio_data.append(indata.copy())

    def stop_recording():
        input()
        nonlocal recording
        recording = False

    print("\n[Recording... Press Enter to stop]")
    
    loop = asyncio.get_running_loop()
    with sd.InputStream(samplerate=sample_rate, channels=1, callback=callback):
        await loop.run_in_executor(None, stop_recording)

    if not audio_data:
        return ""

    # Process audio
    audio_np = np.concatenate(audio_data, axis=0)
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        write(tmp_wav.name, sample_rate, (audio_np * 32768).astype(np.int16))
        
        print("Transcribing...")
        result = stt_model.transcribe(tmp_wav.name)
        text = result["text"].strip()
        
        os.unlink(tmp_wav.name)
    
    print(f"You said: {text}")
    return text

async def play_audio(message: str):
    """Synthesizes text to speech and plays it."""
    cleaned_message = message.replace("**", "")
    print(f"\n🗣️ Luna: {cleaned_message}")
    
    communicate = edge_tts.Communicate(cleaned_message, "en-US-AvaNeural")
    
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
        await communicate.save(tmp_mp3.name)
        
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(tmp_mp3.name)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)
            pygame.mixer.quit()
        except Exception as e:
            print(f"⚠️ Could not play audio: {e}")
        finally:
            if os.path.exists(tmp_mp3.name):
                os.unlink(tmp_mp3.name)