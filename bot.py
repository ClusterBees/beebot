# BeeBot Version: 0.1.4 (Fresh Hive Build)
import discord
from discord.ext import commands, tasks
from discord import app_commands
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
        return [line.strip() for line in f if line.strip()]

facts = load_lines("facts.txt")
fortunes = load_lines("fortunes.txt")
jokes = load_lines("jokes.txt")
prefixes = load_lines("prefixes.txt")
suffixes = load_lines("suffixes.txt")
with open("personality.txt", "r", encoding="utf-8") as f:
    personality = f.read().strip()
questions = load_lines("questions.txt")
quiz_questions = load_lines("quiz.txt")
bee_species = load_lines("bee_species.txt")
banned_phrases = load_lines("banned_phrases.txt")
version_text = "\n".join(load_lines("version.txt"))

# Helper functions
def check_privacy_consent(user_id):
    return r.get(f"consent:{user_id}") == "on"

def get_random_quiz():
    q = random.choice(quiz_questions)
    parts = q.split('|')
    return f"{parts[0]}\nA) {parts[1]}\nB) {parts[2]}\nC) {parts[3]}", parts[4] if len(parts) == 5 else ""

def ai_response(prompt):
    print(f"AI prompt: {prompt}")
    combined_prompt = f"{personality}\n\nUser: {prompt}\nBeeBot:"
    for phrase in banned_phrases:
        if phrase.lower() in prompt.lower():
            print("Prompt contains banned phrase.")
            return "I'm not allowed to discuss that topic."
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": personality},
            {"role": "user", "content": prompt}
        ]
    )
    reply = response.choices[0].message['content'].strip()
    print(f"AI response: {reply}")
    return reply

def parse_duration(time_str):
    match = re.fullmatch(r"(\d+)([smhd]?)", time_str.strip().lower())
    if not match:
        return None
    value, unit = match.groups()
    value = int(value)
    if unit == "s" or unit == "":
        return value
    elif unit == "m":
        return value * 60
    elif unit == "h":
        return value * 3600
    elif unit == "d":
        return value * 86400
    return None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} slash commands globally.")
    for guild in bot.guilds:
        version_id = r.get(f"channel:version:{guild.id}")
        announcement_id = r.get(f"channel:announcement:{guild.id}")
        error_id = r.get(f"channel:error:{guild.id}")

        version_channel = bot.get_channel(int(version_id)) if version_id else None
        announcement_channel = bot.get_channel(int(announcement_id)) if announcement_id else None
        error_channel = bot.get_channel(int(error_id)) if error_id else None

        if version_channel:
            await version_channel.send(version_text)
        if announcement_channel:
            await announcement_channel.send("BeeBot is online!")
        if error_channel:
            await error_channel.send("⚠️ BeeBot has restarted and is active.")

        for channel_name in ["errors", "version", "announcements"]:
            if not discord.utils.get(guild.text_channels, name=channel_name):
                await guild.create_text_channel(channel_name)

@bot.event
async def on_guild_join(guild):
    print(f"Joined new guild: {guild.name} ({guild.id})")
    if not discord.utils.get(guild.roles, name=ANNOUNCEMENT_ROLE_NAME):
        await guild.create_role(name=ANNOUNCEMENT_ROLE_NAME, reason="Creating announcement role for BeeBot")
        print(f"Created role '{ANNOUNCEMENT_ROLE_NAME}' in guild '{guild.name}'")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    print(f"Received message in #{message.channel}: {message.content}")
    user_id = str(message.author.id)
    if not check_privacy_consent(user_id):
        await message.channel.send("Please use /consent to provide data consent before using BeeBot.")
        return

    channel_key = f"autoreply:{message.channel.id}"
    if r.get(channel_key) == "on":
        if message.content.startswith("!"):
            print("Processing command...")
            await bot.process_commands(message)
        elif message.content.endswith("?"):
            print("AI response triggered...")
            reply = ai_response(message.content)
            await message.channel.send(reply)

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

@bot.command(name="announcement")
async def announcement(ctx, *, msg):
    print(f"Attempting announcement by {ctx.author.name} in {ctx.guild.name}")
    role = discord.utils.get(ctx.author.roles, name=ANNOUNCEMENT_ROLE_NAME)
    if not role:
        await ctx.send(f"⛔ You need the '{ANNOUNCEMENT_ROLE_NAME}' role to make announcements.")
        return

    try:
        announcement_id = r.get(f"channel:announcement:{ctx.guild.id}")
        print(f"Channel ID from Redis: {announcement_id}")

        if announcement_id:
            announcement_channel = await bot.fetch_channel(int(announcement_id))
        else:
            announcement_channel = discord.utils.get(ctx.guild.text_channels, name="announcements")

        print(f"Resolved channel: {announcement_channel}")

        if announcement_channel:
            await announcement_channel.send(msg)
            await ctx.send("📢 Announcement sent.")
            print(f"Announcement sent to {announcement_channel.name}: {msg}")
        else:
            await ctx.send("⚠️ Announcement channel not found or not configured.")
            print("Announcement failed: channel not found.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to send messages in the announcement channel.")
        print("Failed to send: Forbidden")
    except discord.HTTPException as e:
        await ctx.send("⚠️ Failed to send announcement due to a Discord error.")
        print(f"HTTP error while sending announcement: {e}")

bot.run(DISCORD_TOKEN)
