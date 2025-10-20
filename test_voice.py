import asyncio
import edge_tts

voices = [
    "th-TH-PremwadeeNeural",
    "th-TH-NiwatNeural",
    "th-TH-SomchaiNeural",
    "th-TH-PirapongNeural",
    "th-TH-AcharaNeural",
    "th-TH-SompornNeural"
]

TEXT = "สวัสดีครับ ยินดีที่ได้รู้จัก"

async def main():
    for voice in voices:
        filename = f"{voice}.mp3"
        print(f"สร้างเสียง: {voice}")
        tts = edge_tts.Communicate(TEXT, voice=voice)
        await tts.save(filename)
        print(f"✔ เสร็จแล้ว -> {filename}")

asyncio.run(main())
