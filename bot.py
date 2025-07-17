BeeBot_version = "4.0.2"
import os
import random
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from openai import OpenAI
from dotenv import load_dotenv
import redis
from datetime import datetime
import time
import uuid
import json

# Load environment variables
load_dotenv()
client = OpenAI(
  api_key=os.env["OPENAI_API_KEY"]
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Redis DB setup
db = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True
)

AUTO_REPLY_CHANNELS_KEY = "global:auto_reply_channels"
UNIVERSAL_CONSENT_KEY = "global:universal_consent"

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Duration parsing
def parse_duration(duration_str: str) -> int:
    units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    duration_str = duration_str.strip().lower()
    if duration_str.isdigit():
        return int(duration_str)
    unit = duration_str[-1]
    value = duration_str[:-1]
    if unit in units and value.isdigit():
        return int(value) * units[unit]
    raise ValueError("Invalid duration format")

# Utility functions
def enable_auto_reply(channel_id: int):
    db.sadd(AUTO_REPLY_CHANNELS_KEY, str(channel_id))

def disable_auto_reply(channel_id: int):
    db.srem(AUTO_REPLY_CHANNELS_KEY, str(channel_id))

def is_auto_reply_enabled(channel_id: int) -> bool:
    return db.sismember(AUTO_REPLY_CHANNELS_KEY, str(channel_id))

def grant_universal_consent(user_id: int):
    db.sadd(UNIVERSAL_CONSENT_KEY, str(user_id))

def revoke_universal_consent(user_id: int):
    db.srem(UNIVERSAL_CONSENT_KEY, str(user_id))

def has_universal_consent(user_id: int) -> bool:
    return db.sismember(UNIVERSAL_CONSENT_KEY, str(user_id))

# Load content files
def load_lines(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    return []

def load_quiz_questions(filename):
    questions = []
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            for i in range(0, len(lines) - 1, 2):
                questions.append({"question": lines[i], "answer": lines[i+1], "options": []})
    return questions

BEE_PERSONALITY = open("bee_personality.txt", encoding="utf-8").read()
BEEBOT_NEVER_SAY = load_lines("beebot_never_say.txt")
BEE_FACTS = load_lines("bee_facts.txt")
BEE_QUESTIONS = load_lines("bee_questions.txt")
BEE_JOKES = load_lines("bee_jokes.txt")
BEE_NAME_PREFIXES = load_lines("bee_name_prefixes.txt")
BEE_NAME_SUFFIXES = load_lines("bee_name_suffixes.txt")
BEE_FORTUNES = load_lines("bee_fortunes.txt")
BEE_QUIZZES = load_quiz_questions("bee_quiz.txt")
BEE_SPECIES = load_lines("bee_species.txt")

# AI response
def format_prompt(user_input):
    return [
        {"role": "system", "content": BEE_PERSONALITY},
        {"role": "user", "content": user_input or "Say something fun as Bieebot!"}
    ]

async def generate_bee_response(user_input: str) -> str:
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=format_prompt(user_input),
            max_tokens=100,
            temperature=0.8
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error: {e}")  # Log the error to console
        return "🐝 Buzz buzz! I'm having trouble thinking right now... try again later!"

# Ready
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user} and synced slash commands.")
    for key in db.scan_iter("reminder:*"):
        parts = key.split(":")
        if len(parts) == 4:
            try:
                data = json.loads(db.get(key))
                asyncio.create_task(schedule_reminder(
                    int(parts[1]), int(parts[2]), parts[3], data.get('remind_time', time.time()), data.get('message', '')
                ))
            except Exception as e:
                print(f"❌ Failed to reschedule {key} with data {db.get(key)}: {e}")

# Message listener
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if isinstance(message.channel, discord.Thread) or (has_universal_consent(message.author.id) and is_auto_reply_enabled(message.channel.id)):
        response = await generate_bee_response(message.content)
        await message.channel.send(response)
    elif message.content.strip().lower() in ["/consent", "/consent_set"]:
        return
    else:
        await message.channel.send(
            "👋 To chat with me, use `/consent_set` and turn it **On**."
        )

# Slash commands
@bot.tree.command(name="bee_fact", description="Get a fun bee fact!")
async def bee_fact(interaction: discord.Interaction):
    fact = random.choice(BEE_FACTS) if BEE_FACTS else "🐝 Bees are amazing!"
    await interaction.response.send_message(fact)

@bot.tree.command(name="bee_question", description="Get a bee-related question to ponder!")
async def bee_question(interaction: discord.Interaction):
    question = random.choice(BEE_QUESTIONS) if BEE_QUESTIONS else "🐝 Hmm... no questions right now!"
    await interaction.response.send_message(question)

@bot.tree.command(name="bee_joke", description="Get a fun bee-themed joke!")
async def bee_joke(interaction: discord.Interaction):
    joke = random.choice(BEE_JOKES) if BEE_JOKES else "🐝 Hmm... I couldn’t think of a joke!"
    await interaction.response.send_message(joke)

@bot.tree.command(name="bee_name", description="Get a cute bee-themed nickname!")
async def bee_name(interaction: discord.Interaction):
    if not BEE_NAME_PREFIXES or not BEE_NAME_SUFFIXES:
        await interaction.response.send_message("🐝 Hmm... I can't come up with a bee name!", ephemeral=True)
        return
    name = random.choice(BEE_NAME_PREFIXES) + random.choice(BEE_NAME_SUFFIXES)
    await interaction.response.send_message(f"🐝 Your bee name is: **{name}**!")

@bot.tree.command(name="bee_species", description="Discover your inner bee species!")
async def bee_species(interaction: discord.Interaction):
    if not BEE_SPECIES:
        await interaction.response.send_message("🐝 Hmm... I don’t know any bee species right now!", ephemeral=True)
        return
    species = random.choice(BEE_SPECIES)
    await interaction.response.send_message(f"🔍 You are a **{species}**! 🐝✨")

@bot.tree.command(name="fortune", description="Get some validating buzzword messages for your day!")
async def fortune(interaction: discord.Interaction):
    if not BEE_FORTUNES:
        await interaction.response.send_message("🐝 Hmm... I can’t think of any fortunes right now!", ephemeral=True)
        return
    selection = random.sample(BEE_FORTUNES, min(4, len(BEE_FORTUNES)))
    response = "🌼 Your fortunes today are:\n" + "\n".join(f"*{line}*" for line in selection)
    await interaction.response.send_message(response)

@bot.tree.command(name="bee_quiz", description="Test your bee knowledge!")
async def bee_quiz(interaction: discord.Interaction):
    if not BEE_QUIZZES:
        await interaction.response.send_message("🐝 Hmm... I don't have any quizzes right now.", ephemeral=True)
        return
    q = random.choice(BEE_QUIZZES)
    formatted_options = "\n".join(q.get("options", []))
    await interaction.response.send_message(
        f"🧠 **{q['question']}**\n\n{formatted_options}\n\n*(Answer: {q['answer']})*"
    )

@bot.tree.command(name="ask", description="Ask BeeBot a question.")
async def ask(interaction: discord.Interaction, question: str):
    response = await generate_bee_response(question)
    await interaction.response.send_message(response)

@bot.tree.command(name="bee_validate", description="Get a validating compliment.")
async def bee_validate(interaction: discord.Interaction):
    response = await generate_bee_response("Give me a validating compliment with bee puns and emojis.")
    await interaction.response.send_message(response)

...

# === Reminder Commands ===

async def schedule_reminder(guild_id, user_id, reminder_id, remind_time, message):
    now = time.time()
    delay = remind_time - now
    if delay > 0:
        await asyncio.sleep(delay)
    key = f"reminder:{guild_id}:{user_id}:{reminder_id}"
    user = await bot.fetch_user(user_id)
    if user:
        try:
            await user.send(f"⏰ Reminder: {message}")
            db.delete(key)
        except Exception as e:
            print(f"Failed to send reminder {key}: {e}")

@bot.tree.command(name="remind", description="Set a reminder for yourself.")
@app_commands.describe(duration_str="Time like 10m, 2h, 1d", message="What should I remind you about?")
async def remind(interaction: discord.Interaction, duration_str: str, message: str):
    try:
        duration = parse_duration(duration_str)
        if duration <= 0 or duration > 604800:
            raise ValueError()
    except ValueError:
        await interaction.response.send_message("⚠️ Please use a valid time (like `10m`, `2h`, `1d`). Max is 7 days.", ephemeral=True)
        return
    remind_time = time.time() + duration
    reminder_id = str(uuid.uuid4())[:8]
    key = f"reminder:{interaction.guild.id}:{interaction.user.id}:{reminder_id}"
    db.set(key, json.dumps({"remind_time": remind_time, "message": message}))
    asyncio.create_task(schedule_reminder(interaction.guild.id, interaction.user.id, reminder_id, remind_time, message))
    dt = datetime.fromtimestamp(remind_time).strftime("%Y-%m-%d %H:%M:%S")
    await interaction.response.send_message(f"✅ I’ll remind you at **{dt}**! Your reminder ID is `{reminder_id}`.", ephemeral=True)

@bot.tree.command(name="list_reminders", description="List your active reminders.")
async def list_reminders(interaction: discord.Interaction):
    keys = list(db.scan_iter(f"reminder:{interaction.guild.id}:{interaction.user.id}:*"))
    if not keys:
        await interaction.response.send_message("📭 You have no active reminders.", ephemeral=True)
        return
    entries = []
    now = time.time()
    for key in keys:
        reminder_id = key.split(":")[-1]
        data = json.loads(db.get(key))
        remaining = int(data["remind_time"] - now)
        if remaining < 0:
            continue
        minutes = remaining // 60
        entries.append(f"`{reminder_id}` – in **{minutes}m** – {data['message']}")
    if not entries:
        await interaction.response.send_message("📭 You have no active reminders.", ephemeral=True)
    else:
        await interaction.response.send_message("📋 Your active reminders:\n" + "\n".join(entries), ephemeral=True)

@bot.tree.command(name="cancel_reminder", description="Cancel a reminder by its ID.")
@app_commands.describe(reminder_id="The ID of the reminder to cancel.")
async def cancel_reminder(interaction: discord.Interaction, reminder_id: str):
    key = f"reminder:{interaction.guild.id}:{interaction.user.id}:{reminder_id}"
    if db.delete(key):
        await interaction.response.send_message(f"❌ Reminder `{reminder_id}` cancelled.", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ Reminder `{reminder_id}` not found.", ephemeral=True)

...

# === Consent Commands ===

@bot.tree.command(name="consent_set", description="Manage your consent settings with the bot")
@app_commands.describe(option="Choose: On, Off, or Info")
@app_commands.choices(option=[
    app_commands.Choice(name="On", value="on"),
    app_commands.Choice(name="Off", value="off"),
    app_commands.Choice(name="Info", value="info")
])
async def consent_set(interaction: discord.Interaction, option: app_commands.Choice[str]):
    user_id = interaction.user.id

    if option.value == "on":
        grant_universal_consent(user_id)
        await interaction.response.send_message("✅ Consent enabled globally.", ephemeral=True)

    elif option.value == "off":
        revoke_universal_consent(user_id)
        await interaction.response.send_message("❌ Consent revoked globally.", ephemeral=True)

    elif option.value == "info":
        await interaction.response.send_message(
                        """**Privacy Info**
            
            This bot stores limited user data only to provide services like reminders, logs, and personalized replies.
            - Your data is not shared with third parties other than OpenAI.
            - You can revoke consent at any time using `/consent_set`.
            
            **OpenAI Privacy Policy:** https://openai.com/policies/privacy-policy
            
            🛡️ **BeeBot Privacy Policy**
            **Effective Date:** 7/16/2025
            
            At BeeBot, your privacy and trust are extremely important to us. This policy outlines how we handle your data and our commitment to keeping it safe.
            
            🔒 **What We Collect**
            - Your Discord user ID
            - Reminder messages and scheduled times (only when you set a reminder)
            - Consent preferences for AI replies
            - Channel settings for features like auto-reply and announcements
            
            We do **NOT** collect:
            - Private messages (unless you directly message BeeBot)
            - Any other personal information
            
            🚫 **What We Never Do**
            - We **NEVER** sell your data
            - We **NEVER** use your data for advertising or marketing
            
            ✅ **Why We Use Your Data**
            BeeBot uses minimal data **ONLY** to:
            - Provide features like reminders, auto-replies, and responses
            - Respect and store your consent choices
            
            🔐 **Data Retention**
            - Reminders are deleted automatically after delivery
            - You can revoke consent at any time using `/consent_set`
            
            📬 **Contact**
            For questions, reach out to the bot maintainer or your server moderator.
            """,
                        ephemeral=True
        )

# === Auto-Reply & Channel Settings ===

@bot.tree.command(name="set_autoreply", description="Enable or disable auto-reply for a specific channel.")
@app_commands.describe(channel="The text channel to set", mode="on or off")
async def set_autoreply(interaction: discord.Interaction, channel: discord.TextChannel, mode: str):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("🚫 You need `Manage Channels` permission.", ephemeral=True)
        return

    if mode.lower() == "on":
        enable_auto_reply(channel.id)
        await interaction.response.send_message(f"✅ Auto-reply enabled for {channel.mention}.", ephemeral=True)
    elif mode.lower() == "off":
        disable_auto_reply(channel.id)
        await interaction.response.send_message(f"❌ Auto-reply disabled for {channel.mention}.", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ Use 'on' or 'off' as the mode.", ephemeral=True)

@bot.tree.command(name="set_version_channel", description="Set the current channel to receive version updates.")
async def set_version_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("🚫 You need `Manage Channels` permission.", ephemeral=True)
        return

    key = f"guild:{interaction.guild.id}:version_channel"
    db.set(key, interaction.channel.id)
    await interaction.response.send_message(f"✅ This channel is now set to receive version updates.", ephemeral=True)

@bot.tree.command(name="set_announcement_channel", description="Set the current channel to receive announcements.")
async def set_announcement_channel(interaction: discord.Interaction):
    """
    Sets the current channel as the designated channel for receiving announcements in the guild.
    """
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("🚫 You need `Manage Channels` permission.", ephemeral=True)
        return

    key = f"guild:{interaction.guild.id}:announcement_channel"
    db.set(key, interaction.channel.id)
    await interaction.response.send_message(f"✅ This channel is now set to receive announcements.", ephemeral=True)
    @bot.tree.command(name="bee_help", description="Show all BeeBot commands and what they do.")
    async def bee_help(interaction: discord.Interaction):
        help_text = """
        **BeeBot Commands**
        - `/bee_fact` — Get a fun bee fact!
        - `/bee_question` — Get a question to ponder!
        - `/bee_joke` — Get a bee-themed joke!
        - `/bee_name` — Get a cute bee nickname!
        - `/bee_species` — Discover your inner bee species!
        - `/fortune` — Get validating buzzword messages for your day!
        - `/bee_quiz` — Test your bee knowledge!
        - `/ask <question>` — Ask BeeBot a question.
        - `/bee_validate` — Get a validating compliment.
        - `/remind <duration> <message>` — Set a reminder for yourself.
        - `/list_reminders` — List your active reminders.
        - `/cancel_reminder <reminder_id>` — Cancel a reminder by its ID.
        - `/consent_set <On/Off/Info>` — Manage your consent settings.
        - `/set_autoreply <channel> <on/off>` — Enable/disable auto-reply for a channel.
        - `/set_version_channel` — Set this channel for version updates.
        - `/set_announcement_channel` — Set this channel for announcements.
        - `/set_error_channel` — Set this channel for error logs.
        - `/bee_help` — Show all BeeBot commands and what they do.
        - `!announcement <message>` — Send an announcement to the designated channel.
        """
        await interaction.response.send_message(help_text, ephemeral=True)

@bot.tree.command(name="set_error_channel", description="Set the current channel to receive error logs.")
async def set_error_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("🚫 You need `Manage Channels` permission.", ephemeral=True)
        return

    key = f"guild:{interaction.guild.id}:error_channel"
    db.set(key, interaction.channel.id)
    await interaction.response.send_message("✅ This channel is now set to receive error logs.", ephemeral=True)

bot.run(DISCORD_TOKEN)