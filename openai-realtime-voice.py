# -*- coding: utf-8 -*-

import asyncio
import websockets
import json
import os
import base64
import sounddevice as sd
import numpy as np

async def main():
    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
    headers = {
        "Authorization": "Bearer " + "xxxxxxxxxx",
        "OpenAI-Beta": "realtime=v1",
    }

    audio_queue = asyncio.Queue()

    # Function to capture audio and put it into the queue
    def audio_callback(indata, frames, time, status):
        if status:
            print(f"Audio status: {status}", flush=True)
        # Convert audio data to bytes
        pcm_bytes = indata.tobytes()
        # Base64 encode the PCM data
        base64_audio = base64.b64encode(pcm_bytes).decode('ascii')
        # Put the base64-encoded audio data into the queue
        asyncio.run_coroutine_threadsafe(audio_queue.put(base64_audio), loop)

    loop = asyncio.get_running_loop()

    async with websockets.connect(url, extra_headers=headers) as ws:
        print("Connected to server.")

        # Start the conversation with initial instructions
        await ws.send(json.dumps({
            "type": "response.create",
            "response": {
                "modalities": ["text"],
                "instructions": "Please assist the user.",
            }
        }))

        # Function to process messages from the server
        async def receive_messages():
            async for message in ws:
                response = json.loads(message)
                print("Received:", response)

        # Function to send audio data from the queue to the WebSocket
        async def send_audio():
            while True:
                base64_audio = await audio_queue.get()
                await ws.send(json.dumps({
                    'type': 'input_audio_buffer.append',
                    'audio': base64_audio
                }))
                audio_queue.task_done()

        # Start tasks for receiving messages and sending audio
        receive_task = asyncio.create_task(receive_messages())
        send_audio_task = asyncio.create_task(send_audio())

        # Start capturing audio
        duration = 5  # Adjust the duration as needed
        fs = 16000  # Sampling rate
        print("Recording...")

        with sd.InputStream(samplerate=fs, channels=1, dtype='int16', callback=audio_callback):
            # Wait for the recording to finish
            await asyncio.sleep(duration)

        print("Recording finished.")

        # Wait for the queue to be fully processed
        await audio_queue.join()

        # Commit the audio buffer and request a response
        await ws.send(json.dumps({'type': 'input_audio_buffer.commit'}))
        await ws.send(json.dumps({'type': 'response.create'}))

        # Wait for all tasks to complete
        await receive_task
        await send_audio_task

asyncio.run(main())