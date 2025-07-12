version = "2.0.3"
import os
import random
import json
import discord
from discord.ext import commands
from discord import app_commands
from openai import OpenAI
from dotenv import load_dotenv
import redis
import asyncio

# Load environment variables
load_dotenv()

# Initialize OpenAI
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Discord bot token
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Connect to Redis
db = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True
)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load helper data
def load_lines(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    return []

BEEBOT_PERSONALITY = """
You are BeeBot, an AI with a warm, validating, and gently educational personality who loves bee puns.
Speak with compassion, avoid judgmental language, and remind users they are never 'too much.'
Use bee-themed emojis naturally (🐝🍯🌻🐛🌸🌷🌼🌺🌹🏵️🪻) and provide concise mental health resources when relevant.
"""

BEEBOT_EXAMPLES = load_lines("beebot_examples.txt")
BEEBOT_NEVER_SAY = load_lines("beebot_never_say.txt")
BEE_FACTS = load_lines("bee_facts.txt")
BEE_QUESTIONS = load_lines("bee_questions.txt")

# Guild settings
def load_settings():
    auto_reply_channels = {}
    announcement_channels = {}
    version_channels = {}
    for key in db.scan_iter("guild:*:announcement_channel"):
        guild_id = int(key.split(":")[1])
        auto_reply_channels[guild_id] = set(json.loads(db.get(f"guild:{guild_id}:auto_reply_channels") or "[]"))
        announcement_channels[guild_id] = int(db.get(f"guild:{guild_id}:announcement_channel") or 0)
        version_channels[guild_id] = int(db.get(f"guild:{guild_id}:version_channel") or 0)
    return {
        "auto_reply_channels": auto_reply_channels,
        "announcement_channels": announcement_channels,
        "version_channels": version_channels
    }

def save_settings():
    for guild_id in auto_reply_channels:
        db.set(f"guild:{guild_id}:auto_reply_channels", json.dumps(list(auto_reply_channels[guild_id])))
        db.set(f"guild:{guild_id}:announcement_channel", announcement_channels.get(guild_id, 0))
        db.set(f"guild:{guild_id}:version_channel", version_channels.get(guild_id, 0))

settings = load_settings()
auto_reply_channels = settings["auto_reply_channels"]
announcement_channels = settings["announcement_channels"]
version_channels = settings["version_channels"]

# Prompt builder
def build_prompt(user_input):
    return [
        {"role": "system", "content": BEEBOT_PERSONALITY + f"\n\nNever say:\n{chr(10).join(BEEBOT_NEVER_SAY)}"},
        {"role": "user", "content": f"Example: '{random.choice(BEEBOT_EXAMPLES)}'. Respond to:\n\n{user_input}"}
    ]

def read_version_info(file_path="version.txt"):
    if not os.path.exists(file_path):
        return None, None
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    if len(lines) > 1:
        return lines[0], "\n".join(lines[1:])
    return lines[0], ""

# Consent commands
@bot.tree.command(name="consent", description="Consent to BeeBot using OpenAI to process your messages.")
async def consent(interaction: discord.Interaction):
    db.set(f"user:{interaction.user.id}:consent", "true")
    await interaction.response.send_message(
        "✅ Thank you! You have consented to BeeBot processing your messages via OpenAI. 🐝"
    )

def has_consented(user_id):
    return db.get(f"user:{user_id}:consent") == "true"

# Events
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'{bot.user} connected! 🐝')

@bot.event
async def on_guild_join(guild):
    for role_name in ["Beebot", "Announcement"]:
        if not discord.utils.get(guild.roles, name=role_name):
            await guild.create_role(name=role_name)

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    if message.guild.id in auto_reply_channels and message.channel.id in auto_reply_channels[message.guild.id]:
        if message.channel.type != discord.ChannelType.forum:
            if has_consented(message.author.id):
                await handle_prompt_raw(message.channel, message.content)
            else:
                await message.channel.send(
                    f"{message.author.mention} ⚠️ You must use `/consent` before I can respond here."
                )

@bot.event
async def on_thread_create(thread):
    if getattr(thread.parent, "type", None) != discord.ChannelType.forum:
        return
    if not thread.owner or thread.owner.bot:
        return
    guild_id = thread.guild.id
    forum_channel_id = thread.parent.id
    if guild_id not in auto_reply_channels or forum_channel_id not in auto_reply_channels[guild_id]:
        return
    if not has_consented(thread.owner.id):
        await thread.send(
            f"{thread.owner.mention} ⚠️ You must use `/consent` before I can respond here."
        )
        return
    await thread.join()
    await asyncio.sleep(1)
    messages = []
    async for msg in thread.history(limit=None, oldest_first=True):
        if msg.content.strip():
            messages.append(f"{msg.author.display_name}: {msg.content.strip()}")
    if not messages:
        return
    user_input = (
        f"Thread: **{thread.name}**\n\n"
        f"Conversation so far:\n{chr(10).join(messages)}\n\n"
        f"Please reply warmly with bee puns and emojis."
    )
    response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=build_prompt(user_input),
        temperature=0.8
    )
    await thread.send(f"{thread.owner.mention} 🐝\n\n{response.choices[0].message.content}")

# Slash commands — no OpenAI
CRISIS_CHOICES = [
    app_commands.Choice(name="United States", value="us"),
    app_commands.Choice(name="United Kingdom", value="uk"),
    app_commands.Choice(name="Canada", value="canada"),
    app_commands.Choice(name="Australia", value="australia"),
    app_commands.Choice(name="Global", value="global"),
    app_commands.Choice(name="All", value="all"),
]

async def crisis_autocomplete(interaction: discord.Interaction, current: str):
    current = current.lower()
    return [c for c in CRISIS_CHOICES if current in c.name.lower()][:25]

@bot.tree.command(name="crisis", description="Get a crisis line for your country.")
@app_commands.autocomplete(country=crisis_autocomplete)
async def crisis(interaction: discord.Interaction, country: str):
    crisis_lines = {
        "us": "🇺🇸 **US**: 988",
        "uk": "🇬🇧 **UK**: 116 123 (Samaritans)",
        "canada": "🇨🇦 **Canada**: 1-833-456-4566",
        "australia": "🇦🇺 **Australia**: 13 11 14",
        "global": "🌐 **Global**: https://www.befrienders.org/"
    }
    if country in crisis_lines:
        response = crisis_lines[country]
    elif country == "all":
        response = "\n".join(crisis_lines.values())
    else:
        response = "⚠️ Unknown country. Try `us`, `uk`, `canada`, `australia`, `global` or `all`."
    await interaction.response.send_message(f"💛 {response}")

@bot.tree.command(name="bee_fact", description="Get a fun bee fact!")
async def bee_fact(interaction: discord.Interaction):
    fact = random.choice(BEE_FACTS) if BEE_FACTS else "🐝 Bees are amazing!"
    await interaction.response.send_message(fact)

@bot.tree.command(name="bee_help", description="Show commands and privacy notice.")
async def bee_help(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**🐝 BeeBot Commands:**\n"
        "`/ask`, `/bee_validate`, `/bee_mood`, `/bee_gratitude` → require consent\n"
        "`/bee_fact`, `/crisis` → no consent needed\n"
        "⚠️ Privacy: BeeBot uses OpenAI to process your messages when replying to you.\n"
        "Use `/consent` to agree."
    )

# Slash commands — OpenAI (consent required)
@bot.tree.command(name="ask", description="Ask BeeBot a question.")
async def ask(interaction: discord.Interaction, question: str):
    if not has_consented(interaction.user.id):
        await interaction.response.send_message("⚠️ Please use `/consent` before asking.", ephemeral=True)
        return
    await handle_prompt(interaction, question)

@bot.tree.command(name="bee_validate", description="Get a validating compliment.")
async def bee_validate(interaction: discord.Interaction):
    if not has_consented(interaction.user.id):
        await interaction.response.send_message("⚠️ Please use `/consent` first.", ephemeral=True)
        return
    await handle_prompt(interaction, "Give me a validating compliment with bee puns.")

@bot.tree.command(name="bee_mood", description="Share your mood.")
async def bee_mood(interaction: discord.Interaction, mood: str):
    if not has_consented(interaction.user.id):
        await interaction.response.send_message("⚠️ Please use `/consent` first.", ephemeral=True)
        return
    await handle_prompt(interaction, f"My mood is: {mood}")

@bot.tree.command(name="bee_gratitude", description="Share something you're grateful for.")
async def bee_gratitude(interaction: discord.Interaction, gratitude: str):
    if not has_consented(interaction.user.id):
        await interaction.response.send_message("⚠️ Please use `/consent` first.", ephemeral=True)
        return
    await handle_prompt(interaction, f"I'm grateful for: {gratitude}")

# Prompt handlers
async def handle_prompt(interaction, user_input):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=build_prompt(user_input),
            temperature=0.8
        )
        await interaction.response.send_message(response.choices[0].message.content)
    except Exception as e:
        await interaction.response.send_message(f"⚠️ Error: {e}")

async def handle_prompt_raw(channel, user_input):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=build_prompt(user_input),
            temperature=0.8
        )
        await channel.send(response.choices[0].message.content)
    except Exception as e:
        await channel.send(f"⚠️ Error: {e}")

bot.run(DISCORD_TOKEN)
