import emoji as emoji_lib
from dotenv import load_dotenv

load_dotenv()

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
        name = m.group(1).replace("_", " ")
        return f"อีโมจิ {name}"
    text = CUSTOM_EMOJI_RE.sub(_custom_replace, text)
    demojized = emoji_lib.demojize(text)
    demojized = re.sub(r":([a-zA-Z0-9_]+):", lambda m: f"อีโมจิ {m.group(1).replace('_',' ')}", demojized)
    demojized = demojized.replace("@everyone", "ทุกคน").replace("@here", "ทุกคนในห้องนี้")
    demojized = re.sub(r"https?://\S+", "ลิงก์", demojized)
    return demojized.strip()

async def ensure_queue(guild_id: int) -> asyncio.Queue:
    if guild_id not in guild_queues:
        guild_queues[guild_id] = asyncio.Queue()
    return guild_queues[guild_id]

async def tts_to_file(text: str) -> str:
    communicate = edge_tts.Communicate(text, voice="th-TH-PremwadeeNeural", rate="+0%")
    queue = await ensure_queue(guild.id)
    while True:
        text = await queue.get()
        try:
            mp3_path = await tts_to_file(text)
        except Exception as e:
            print("TTS error:", e)
            queue.task_done()
            continue

        vc = guild.voice_client
        if not vc or not vc.is_connected():
            os.remove(mp3_path)
            queue.task_done()
            continue

        audio = discord.FFmpegPCMAudio(mp3_path)
        finished = asyncio.Event()

        def after_play(err):
            try:
                os.remove(mp3_path)
            except:
                pass
            finished.set()

        vc.play(audio, after=lambda e: after_play(e))
        await finished.wait()
        queue.task_done()

def start_player_task(guild: discord.Guild):
    if guild.id not in playing_tasks or playing_tasks[guild.id].done():
        playing_tasks[guild.id] = asyncio.create_task(player_loop(guild))

@bot.tree.command(name="join", description="ให้บอทเข้าห้องเสียงของคุณ")
async def join_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("ใช้คำสั่งนี้ในเซิร์ฟเวอร์เท่านั้น", ephemeral=True)

    author = interaction.user
    if not isinstance(author, (discord.Member,)):
        author = interaction.guild.get_member(author.id)

    if not author or not author.voice or not author.voice.channel:
        return await interaction.response.send_message("คุณยังไม่ได้อยู่ในห้องเสียงนะ", ephemeral=True)

    if interaction.guild.voice_client and interaction.guild.voice_client.is_connected():
        vc = interaction.guild.voice_client
        if vc.channel.id != author.voice.channel.id:
            return await interaction.response.send_message("ไม่ว่าง ตอนนี้ติดภารกิจในห้องเสียงอื่นอยู่", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    channel = author.voice.channel
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected():
        await channel.connect()
        start_player_task(interaction.guild)
        await interaction.followup.send(f"มาแล้ว เข้าห้อง **{channel.name}** เรียบร้อย", ephemeral=True)
    else:
        await interaction.followup.send("อยู่ในห้องนี้อยู่แล้ว", ephemeral=True)

@bot.tree.command(name="leave", description="ให้บอทออกจากห้องเสียง")
async def leave_cmd(interaction: discord.Interaction):
    if interaction.guild and interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect(force=True)
        await interaction.response.send_message("ออกจากห้องเสียงแล้ว", ephemeral=True)
    else:
        await interaction.response.send_message("ตอนนี้ไม่ได้อยู่ในห้องเสียง", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        await bot.tree.sync()
        print("Slash commands synced")
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

    text = normalize_text_for_tts(message.content)
    if not text:
        return

    queue = await ensure_queue(message.guild.id)
    await queue.put(f"{message.author.display_name} กล่าวว่า {text}")
    start_player_task(message.guild)

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.bot:
        return

    guild = member.guild
    vc = guild.voice_client
    if not vc or not vc.is_connected():
        return

    joined = (before.channel != vc.channel) and (after.channel == vc.channel)
    if joined:
        queue = await ensure_queue(guild.id)
        await queue.put(f"{member.display_name} ขออยู่ด้วย")
        start_player_task(guild)

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("กรุณาตั้งค่า DISCORD_TOKEN ในไฟล์ .env")
    bot.run(token)
