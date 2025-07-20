# 🐝 BeeBot v0.1.9 (Fresh Hive Build)
import discord
from discord.ext import commands, tasks
from discord import Interaction, app_commands
from openai import OpenAI
import os
import redis
import random
from dotenv import load_dotenv
from datetime import datetime, timedelta
import asyncio
import re

ANNOUNCEMENT_ROLE_NAME = "Bee Announcer"

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Redis setup using environment variables
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True
)

# BeeBot-style logging function
def bee_log(message):
    print(f"🐝 [BeeBot Log] {message}")

# Emotion detection regex map
EMOTION_MAP = {
    "sad": ["sad", "upset", "cry", "lonely", "depressed"],
    "happy": ["happy", "joy", "excited", "smile"],
    "angry": ["angry", "mad", "furious"],
    "anxious": ["worried", "anxious", "scared", "nervous"],
    "tired": ["tired", "exhausted", "worn out"]
}

def detect_emotion(message):
    text = message.lower()
    for emotion, keywords in EMOTION_MAP.items():
        if any(word in text for word in keywords):
            bee_log(f"Detected emotion: {emotion} from message: '{message}'")
            return emotion
    return "neutral"

# Intents setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

class BeeBot(commands.Bot):
    async def setup_hook(self):
        await self.tree.sync()

bot = BeeBot(command_prefix="!", intents=intents)

# Load text files
def load_lines(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
        bee_log(f"Loaded {len(lines)} lines from {filename}")
        return lines

facts = load_lines("facts.txt")
fortunes = load_lines("fortunes.txt")
jokes = load_lines("jokes.txt")
prefixes = load_lines("prefixes.txt")
suffixes = load_lines("suffixes.txt")
with open("personality.txt", "r", encoding="utf-8") as f:
    personality = f.read().strip()
    bee_log("Personality loaded from personality.txt")
questions = load_lines("questions.txt")
quiz_questions = load_lines("quiz.txt")
bee_species = load_lines("bee_species.txt")
banned_phrases = load_lines("banned_phrases.txt")
version_text = "\n".join(load_lines("version.txt"))

# Helper functions
def check_privacy_consent(user_id):
    consent = r.get(f"consent:{user_id}") == "on"
    bee_log(f"Privacy consent check for {user_id}: {consent}")
    return consent

def get_random_quiz():
    q = random.choice(quiz_questions)
    parts = q.split('|')
    return f"{parts[0]}\nA) {parts[1]}\nB) {parts[2]}\nC) {parts[3]}", parts[4] if len(parts) == 5 else ""

def store_context(user_id, thread_id, message_content, limit=6):
    key = f"context:{thread_id}:{user_id}"
    r.lpush(key, message_content)
    r.ltrim(key, 0, limit - 1)
    r.expire(key, 3600)
    emotion = detect_emotion(message_content)
    r.set(f"emotion:{thread_id}:{user_id}", emotion, ex=3600)
    bee_log(f"Stored context and emotion ({emotion}) for user {user_id} in thread {thread_id}")

def get_context(user_id, thread_id):
    context = r.lrange(f"context:{thread_id}:{user_id}", 0, -1)
    bee_log(f"Fetched context for {user_id} in thread {thread_id}: {context}")
    return context

def get_emotion(user_id, thread_id):
    emotion = r.get(f"emotion:{thread_id}:{user_id}") or "neutral"
    bee_log(f"Fetched emotion for {user_id} in thread {thread_id}: {emotion}")
    return emotion

def ai_response(prompt, user_id=None, channel_id=None):
    thread_id = channel_id or "general"
    context_msgs = get_context(user_id, thread_id) if user_id and thread_id else []
    emotion = get_emotion(user_id, thread_id) if user_id and thread_id else "neutral"

    context_text = "\n".join([f"User said: {msg}" for msg in reversed(context_msgs)])
    full_prompt = f"User seems to be feeling {emotion}.\n{context_text}\nNow they say: {prompt}" if context_text else prompt

    bee_log(f"Preparing AI prompt: {full_prompt}")
    for phrase in banned_phrases:
        if phrase.lower() in prompt.lower():
            bee_log("Prompt blocked due to banned phrase.")
            return "I'm not allowed to discuss that topic."

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": personality},
                {"role": "user", "content": full_prompt}
            ]
        )
        reply = response.choices[0].message.content.strip()
        bee_log(f"BeeBot's response: {reply}")
        return reply
    except Exception as e:
        bee_log(f"Oh no! An error happened while generating AI response: {e}")
        for guild in bot.guilds:
            error_id = r.get(f"channel:error:{guild.id}")
            if error_id:
                channel = bot.get_channel(int(error_id))
                if channel:
                    asyncio.create_task(channel.send(f"⚠️ AI error: {e}"))
        return "Oops! My wings got tangled while thinking. Try again soon!"

@bot.event
async def on_ready():
    bee_log(f"Buzz buzz! I just logged in as {bot.user.name}! I'm ready to fly! 🎉")
    synced = await bot.tree.sync()
    bee_log(f"Synced {len(synced)} slash commands globally!")
    for guild in bot.guilds:
        bee_log(f"Setting up channels for guild: {guild.name}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    bee_log(f"Received message in #{message.channel}: {message.content}")
    user_id = str(message.author.id)
    channel = message.channel
    thread_id = str(channel.id if not isinstance(channel, discord.Thread) else channel.parent_id)

    if not check_privacy_consent(user_id):
        await message.channel.send("Please use /consent to provide data consent before using BeeBot.")
        return

    store_context(user_id, thread_id, message.content)

    channel_key = f"autoreply:{channel.id}"
    value = r.get(channel_key)
    is_thread = isinstance(channel, discord.Thread)

    if value == "on" or (value is None and is_thread):
        if message.content.startswith("!"):
            bee_log("BeeBot spotted a command! Processing...")
            await bot.process_commands(message)
        else:
            bee_log("BeeBot is about to buzz a reply!")
            reply = ai_response(message.content, user_id=user_id, channel_id=thread_id)
            await message.channel.send(reply)

# Slash commands
@bot.tree.command(name="bee_fact", description="Get a random bee-related fact")
async def bee_fact(interaction: discord.Interaction):
    await interaction.response.send_message(random.choice(facts))

@bot.tree.command(name="bee_fortune", description="Receive a bee-themed fortune")
async def bee_fortune(interaction: discord.Interaction):
    await interaction.response.send_message(random.choice(fortunes))

@bot.tree.command(name="bee_joke", description="Hear a bee joke")
async def bee_joke(interaction: discord.Interaction):
    await interaction.response.send_message(random.choice(jokes))

@bot.tree.command(name="bee_name", description="Generate a random bee name")
async def bee_name(interaction: discord.Interaction):
    name = f"{random.choice(prefixes)}{random.choice(suffixes)}"
    await interaction.response.send_message(name)

@bot.tree.command(name="bee_question", description="Get a deep or fun question")
async def bee_question(interaction: discord.Interaction):
    await interaction.response.send_message(random.choice(questions))

@bot.tree.command(name="bee_quiz", description="Take a random bee quiz")
async def bee_quiz(interaction: discord.Interaction):
    q, _ = get_random_quiz()
    await interaction.response.send_message(q)

@bot.tree.command(name="bee_species", description="Learn about a random bee species")
async def bee_species_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(random.choice(bee_species))

@bot.tree.command(name="ask", description="Ask BeeBot a question")
@app_commands.describe(question="Your question to BeeBot")
async def ask(interaction: discord.Interaction, question: str):
    if not check_privacy_consent(str(interaction.user.id)):
        await interaction.response.send_message("Please use /consent to provide data consent before using BeeBot.")
        return
    await interaction.response.send_message(ai_response(question))

@bot.tree.command(name="bee_validate", description="Get emotional validation")
async def bee_validate(interaction: discord.Interaction):
    await interaction.response.send_message("You're doing great! Keep buzzing!")

@bot.tree.command(name="consent", description="Manage your privacy consent")
@app_commands.describe(choice="on, off, or info")
async def consent(interaction: discord.Interaction, choice: str):
    if choice.lower() not in ["on", "off", "info"]:
        await interaction.response.send_message("Please choose: on, off, or info")
    elif choice.lower() == "info":
        await interaction.response.send_message("This is the privacy policy.")
    else:
        r.set(f"consent:{interaction.user.id}", choice.lower())
        await interaction.response.send_message(f"Consent {choice.lower()}.")

@bot.tree.command(name="set_reminder", description="Set a personal reminder")
@app_commands.describe(time="When to remind", reminder="What to remind you of")
async def set_reminder(interaction: discord.Interaction, time: str, reminder: str):
    await interaction.response.send_message(f"Reminder set for {time}: {reminder}")

@bot.tree.command(name="get_reminders", description="View your active reminders")
async def get_reminders(interaction: discord.Interaction):
    await interaction.response.send_message("Here are your reminders:")

@bot.tree.command(name="delete_reminder", description="Delete a reminder by index")
@app_commands.describe(index="Reminder index to delete")
async def delete_reminder(interaction: discord.Interaction, index: int):
    await interaction.response.send_message(f"Reminder {index} deleted.")

@bot.tree.command(name="crisis", description="View global crisis helplines")
async def crisis(interaction: discord.Interaction):
    help_lines = """
    🌍 **Global Crisis Support Lines**:

    **United States**: 988 (Suicide & Crisis Lifeline)
    **Canada**: 1-833-456-4566 (Talk Suicide Canada)
    **UK**: 116 123 (Samaritans)
    **Australia**: 13 11 14 (Lifeline Australia)
    **India**: 9152987821 (iCall)
    **Europe**: 112 (General Emergency Number)
    **International**: Check https://www.befrienders.org for local crisis centers

    You are not alone. Please reach out. 💛
    """
    await interaction.response.send_message(help_lines)

@bot.tree.command(name="bee_help", description="List BeeBot commands")
async def bee_help(interaction: discord.Interaction):
    await interaction.response.send_message("""
**🐝 BeeBot Full Command List:**

🧠 **General Info & Fun**
- `/bee_fact` — Get a random bee-related fact.
- `/bee_fortune` — Receive a bee-themed fortune.
- `/bee_joke` — Hear a bee joke.
- `/bee_name` — Generate a random bee name.
- `/bee_question` — Get a deep or fun question to think about.
- `/bee_quiz` — Take a random bee quiz (multiple choice).
- `/bee_species` — Learn about a random bee species.
- `/bee_validate` — Get some emotional validation.

🤖 **AI & Interaction**
- `/ask` — Ask BeeBot any question using AI.
- `/autoreply` — Enable or disable AI auto-reply in the current channel.

🛠️ **Context & Emotion Debugging**
- `/debug_context` — View a user’s recent message context and emotion.
- `/clear_context` — Clear saved context and emotion for a user.

📢 **Announcements & Channel Setup**
- `/announce` — Send an announcement to the designated channel.
- `/set_version_channel` — Set the current channel for version logs.
- `/set_announcement_channel` — Set the current channel for announcements.
- `/set_error_channel` — Set the current channel for error messages.

📅 **Reminders**
- `/set_reminder` — Set a personal reminder.
- `/get_reminders` — View your active reminders.
- `/delete_reminder` — Delete a reminder by index.

🛡️ **Privacy & Consent**
- `/consent` — Manage your data consent settings.

💛 **Support**
- `/crisis` — View global crisis helplines.

""")

@bot.tree.command(name="set_version_channel", description="Set this channel as the version log")
async def set_version_channel(interaction: discord.Interaction):
    r.set(f"channel:version:{interaction.guild.id}", interaction.channel.id)
    await interaction.response.send_message("✅ This channel has been set as the **version** channel.")

@bot.tree.command(name="set_announcement_channel", description="Set this channel for announcements")
async def set_announcement_channel(interaction: discord.Interaction):
    r.set(f"channel:announcement:{interaction.guild.id}", interaction.channel.id)
    await interaction.response.send_message("📢 This channel has been set as the **announcement** channel.")

@bot.tree.command(name="set_error_channel", description="Set this channel for error messages")
async def set_error_channel(interaction: discord.Interaction):
    r.set(f"channel:error:{interaction.guild.id}", interaction.channel.id)
    await interaction.response.send_message("⚠️ This channel has been set as the **error** channel.")

@bot.tree.command(name="autoreply", description="Enable or disable AI auto-reply in this channel.")
@app_commands.describe(mode="Set auto-reply mode to 'on' or 'off'. Leave blank to check status.")
async def autoreply(interaction: discord.Interaction, mode: str = None):
    channel = interaction.channel
    channel_id = str(channel.id)
    channel_key = f"autoreply:{channel_id}"

    # If no mode is given, show current status
    if mode is None:
        value = r.get(channel_key)

        if value:
            status = value
        else:
            # Default: ON in threads, OFF otherwise
            status = "on" if isinstance(channel, discord.Thread) else "off"

        await interaction.response.send_message(
            f"💬 Auto-reply is currently **{status}** in this channel.",
            ephemeral=True
        )
        return

    # Normalize and validate mode input
    mode = mode.lower()
    if mode not in ["on", "off"]:
        await interaction.response.send_message("⚠️ Mode must be either `on` or `off`.", ephemeral=True)
        return

    r.set(channel_key, mode)
    print(f"Auto-reply set to {mode} for channel {channel.name} ({channel.id})")
    await interaction.response.send_message(f"✅ Auto-reply has been turned **{mode}** in this channel.")

@bot.tree.command(name="announce", description="Send an announcement to the configured announcement channel.")
@app_commands.describe(message="The message you want to announce.")
async def announce(interaction: Interaction, message: str):
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    member = interaction.user
    role = discord.utils.get(member.roles, name=ANNOUNCEMENT_ROLE_NAME)

    if not role:
        await interaction.followup.send(
            f"⛔ You need the `{ANNOUNCEMENT_ROLE_NAME}` role to use this command.",
            ephemeral=True
        )
        return

    try:
        announcement_id = r.get(f"channel:announcement:{guild.id}")
        print(f"Redis announcement channel ID: {announcement_id}")

        if announcement_id:
            announcement_channel = await bot.fetch_channel(int(announcement_id))
        else:
            announcement_channel = discord.utils.get(guild.text_channels, name="announcements")

        if not announcement_channel:
            await interaction.followup.send(
                "⚠️ Could not find an announcement channel.",
                ephemeral=True
            )
            return

        # Create embed
        embed = discord.Embed(
            title="📢 Announcement",
            description=message,
            color=discord.Color.gold()
            )
        embed.set_footer(text=f"Posted by {member.display_name}", icon_url=member.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()


        await announcement_channel.send(embed=embed)
        await interaction.followup.send("✅ Announcement sent!", ephemeral=True)
        print(f"Sent announcement to #{announcement_channel.name} in {guild.name}: {message}")

    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to send messages in that channel.", ephemeral=True)
        print("Announcement failed: Forbidden")
    except discord.HTTPException as e:
        await interaction.followup.send("⚠️ Failed to send the announcement due to an error.", ephemeral=True)
        print(f"Announcement error: {e}")

@bot.tree.command(name="debug_context", description="View recent context and emotion")
@app_commands.describe(target="Mention a user to inspect")
async def debug_context(interaction: Interaction, target: discord.User):
    thread_id = str(interaction.channel.id if not isinstance(interaction.channel, discord.Thread) else interaction.channel.parent_id)
    context = get_context(str(target.id), thread_id)
    emotion = get_emotion(str(target.id), thread_id)
    if not context:
        await interaction.response.send_message(f"No context found for {target.mention}.", ephemeral=True)
    else:
        msg_log = "\n".join([f"- {m}" for m in reversed(context)])
        await interaction.response.send_message(
            f"🧠 **Context for {target.mention}**\n```\n{msg_log}\n```\n❤️ Emotion: **{emotion}**",
            ephemeral=True
        )

@bot.tree.command(name="clear_context", description="Clear context memory for a user")
@app_commands.describe(target="Mention a user to clear")
async def clear_context(interaction: Interaction, target: discord.User):
    thread_id = str(interaction.channel.id if not isinstance(interaction.channel, discord.Thread) else interaction.channel.parent_id)
    r.delete(f"context:{thread_id}:{target.id}")
    r.delete(f"emotion:{thread_id}:{target.id}")
    await interaction.response.send_message(f"🧹 Cleared context and emotion for {target.mention}.", ephemeral=True)

bot.run(DISCORD_TOKEN)
