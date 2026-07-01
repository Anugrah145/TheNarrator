import edge_tts
import asyncio


class AudioGenerator:
    @staticmethod
    async def generate_audio(text: str, voice: str = "en-GB-SoniaNeural") -> bytes:
        try:
            communicate = edge_tts.Communicate(text, voice)
            mp3_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3_bytes += chunk["data"]
            return mp3_bytes
        except Exception as e:
            print(f"Audio generation failed: {e}")
            return b""

    @classmethod
    def generate_audio_sync(cls, text: str, voice: str = "en-GB-SoniaNeural") -> bytes:
        return asyncio.run(cls.generate_audio(text, voice))
