import asyncio
import os
import re
import tempfile
from typing import Dict

import discord
from discord.ext import commands
import edge_tts
import emoji as emoji_lib
from dotenv import load_dotenv

load_dotenv()

VOICE = "th-TH-PremwadeeNeural"
RATE = "-20%"
PITCH = "+0Hz"

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True
INTENTS.voice_states = True
bot = commands.Bot(command_prefix="!", intents=INTENTS)

guild_queues: Dict[int, asyncio.Queue] = {}
playing_tasks: Dict[int, asyncio.Task] = {}

CUSTOM_EMOJI_RE = re.compile(r"<a?:([a-zA-Z0-9_]+):\d+>")


def normalize_text_for_tts(text: str) -> str:
    def _custom_replace(m):
        return m.group(1).replace("_", " ")
    text = CUSTOM_EMOJI_RE.sub(_custom_replace, text)

    demojized = emoji_lib.demojize(text)
    demojized = re.sub(
        r":([a-zA-Z0-9_]+):",
        lambda m: m.group(1).replace("_", " "),
        demojized
    )

    demojized = re.sub(r"https?://\S+", "ลิงก์", demojized)
    demojized = demojized.strip()

    return demojized


async def ensure_queue(guild_id: int) -> asyncio.Queue:
    if guild_id not in guild_queues:
        guild_queues[guild_id] = asyncio.Queue()
    return guild_queues[guild_id]


async def tts_to_file(text: str) -> str:
    communicate = edge_tts.Communicate(text, voice=VOICE, rate=RATE, pitch=PITCH)
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    await communicate.save(path)
    return path


async def player_loop(guild: discord.Guild):
    queue = await ensure_queue(guild.id)
    while True:
        text = await queue.get()
        try:
            mp3_path = await tts_to_file(text)
        except Exception as e:
            print("TTS Error:", e)
            queue.task_done()
            continue

        vc = guild.voice_client
        if not vc or not vc.is_connected():
            if os.path.exists(mp3_path):
                os.remove(mp3_path)
            queue.task_done()
            continue

        finished = asyncio.Event()

        def after_play(err):
            try:
                os.remove(mp3_path)
            except:
                pass
            finished.set()

        vc.play(discord.FFmpegPCMAudio(mp3_path), after=lambda e: after_play(e))
        await finished.wait()
        queue.task_done()


def start_player_task(guild: discord.Guild):
    if guild.id not in playing_tasks or playing_tasks[guild.id].done():
        playing_tasks[guild.id] = asyncio.create_task(player_loop(guild))


@bot.tree.command(name="join", description="ให้บอทเข้าห้องเสียงของคุณ")
async def join_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("ใช้ในเซิร์ฟเวอร์เท่านั้น", ephemeral=True)

    member = interaction.user
    if not isinstance(member, discord.Member):
        member = interaction.guild.get_member(member.id)

    if not member.voice or not member.voice.channel:
        return await interaction.response.send_message("คุณต้องอยู่ในห้องเสียงก่อน", ephemeral=True)

    if interaction.guild.voice_client and interaction.guild.voice_client.is_connected():
        vc = interaction.guild.voice_client
        if vc.channel.id != member.voice.channel.id:
            return await interaction.response.send_message("ไม่ว่าง อยู่ในห้องเสียงอื่นแล้ว", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    await member.voice.channel.connect()
    start_player_task(interaction.guild)
    await interaction.followup.send(f"เข้าห้อง **{member.voice.channel.name}** เรียบร้อย", ephemeral=True)


@bot.tree.command(name="leave", description="ให้บอทออกจากห้องเสียง")
async def leave_cmd(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect(force=True)
        return await interaction.response.send_message("ออกจากห้องเสียงแล้ว", ephemeral=True)
    else:
        return await interaction.response.send_message("ตอนนี้ไม่ได้อยู่ในห้องเสียง", ephemeral=True)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        await bot.tree.sync()
        print("📢 Slash commands synced")
    except Exception as e:
        print("Slash sync error:", e)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    if not message.guild:
        return

    vc = message.guild.voice_client
    if not vc or not vc.is_connected():
        return

    if message.channel.id != vc.channel.id:
        return

    if not message.content:
        return

    text = normalize_text_for_tts(message.content)
    if not text:
        return

    queue = await ensure_queue(message.guild.id)
    await queue.put(text)
    start_player_task(message.guild)


@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    guild = member.guild
    vc = guild.voice_client
    if not vc or not vc.is_connected():
        return

    joined = before.channel != vc.channel and after.channel == vc.channel
    if joined:
        queue = await ensure_queue(guild.id)
        await queue.put(f"{member.display_name} ขออยู่ด้วย")
        start_player_task(guild)


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("⚠ ต้องใส่ DISCORD_TOKEN ในไฟล์ .env ก่อน")
    bot.run(token)
