try:
    import sounddevice as sd
except OSError:
    sd = None
import numpy as np
import asyncio
import io
from scipy.io.wavfile import write

async def record_audio_until_stop():
    """Records audio from the microphone until Enter is pressed."""
    print("\n[Recording... Press Enter to stop]")
    
    audio_data = []
    recording = True
    sample_rate = 16000

    def callback(indata, frames, time, status):
        if recording:
            audio_data.append(indata.copy())

    def stop_recording():
        input()
        nonlocal recording
        recording = False

    loop = asyncio.get_running_loop()
    
    if sd is None:
        print("⚠️ PortAudio not found. Native recording disabled.")
    else:
        # Start the input stream
        with sd.InputStream(samplerate=sample_rate, channels=1, callback=callback):
            await loop.run_in_executor(None, stop_recording)

    if not audio_data:
        return ""

    audio_np = np.concatenate(audio_data, axis=0)
    
    # In a real app, you'd send this to a STT API.
    # For this tutorial, let's keep it as a placeholder but functional in structure.
    print("⚠️ (Voice processing not implemented. Please type your request below.)")
    text = input("You: ")
    return text

async def play_audio(message: str):
    """Pass clean text message to a TTS engine or just print."""
    cleaned_message = message.replace("**", "")
    print(f"\n🗣️ Luna: {cleaned_message}")
    # In a real app, you'd use a TTS library here like Edge-TTS or gTTS.