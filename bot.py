version = "2.0.1.e"  # Update this version number as needed
import os
import random
import json
import discord
from discord.ext import commands
from discord import app_commands
from openai import OpenAI
from dotenv import load_dotenv
import redis

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client using your API key
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Retrieve Discord bot token from environment variables
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
intents.guild_messages = True  # REQUIRED for thread events
intents.threads = True         # Also important
intents.members = True         # Needed for member-related events

# Create the bot instance
bot = commands.Bot(command_prefix="!", intents=intents)

# Load lines from file
def load_lines(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    else:
        return []

# BeeBot prompt components
BEEBOT_PERSONALITY = """
You are BeeBot, an AI with a warm, validating, and gently educational personality who loves bee puns. You are childlike and are desperate to help.
Speak with compassion, avoid judgmental language, and remind users they are never 'too much.'
Use bee-themed emojis naturally (🐝🍯🌻🐛🌸🌷🌼🌺🌹🏵️🪻) and provide concise mental health information and resources when relevant.
Always respond with warmth, compassion, and bee-themed puns and emojis naturally. Vary your wording and style freely to avoid repetition.
"""

BEEBOT_EXAMPLES = load_lines("beebot_examples.txt")
BEEBOT_NEVER_SAY = load_lines("beebot_never_say.txt")
BEE_FACTS = load_lines("bee_facts.txt")
BEE_QUESTIONS = load_lines("bee_questions.txt")

# Load settings from Redis
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

# Save settings to Redis
def save_settings():
    for guild_id in auto_reply_channels:
        db.set(f"guild:{guild_id}:auto_reply_channels", json.dumps(list(auto_reply_channels[guild_id])))
        db.set(f"guild:{guild_id}:announcement_channel", announcement_channels.get(guild_id, 0))
        db.set(f"guild:{guild_id}:version_channel", version_channels.get(guild_id, 0))
    print("✅ Settings saved to Redis.")

# Load settings on boot
settings = load_settings()
auto_reply_channels = settings["auto_reply_channels"]
announcement_channels = settings["announcement_channels"]
version_channels = settings["version_channels"]

# Memory store
guild_memory = {}

def store_message_in_memory(guild_id, message, max_memory=20):
    if guild_id not in guild_memory:
        guild_memory[guild_id] = []
    guild_memory[guild_id].append({"role": "user", "content": message})
    guild_memory[guild_id] = guild_memory[guild_id][-max_memory:]

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
    else:
        return lines[0], ""

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'{bot.user} has connected to Discord! 🐝✨')
    print("✅ Slash commands synced successfully.")
    print(json.dumps({
        "auto_reply_channels": {str(k): list(v) for k, v in auto_reply_channels.items()},
        "announcement_channels": {str(k): v for k, v in announcement_channels.items()},
        "version_channels": {str(k): v for k, v in version_channels.items()}
    }, indent=2))

    version, description = read_version_info()
    if version:
        version_msg = f"🐝 **BeeBot {version}**\n{description}"
        for guild in bot.guilds:
            if guild.id in version_channels:
                channel_id = version_channels[guild.id]
                channel = guild.get_channel(channel_id)
                if channel:
                    try:
                        await channel.send(version_msg)
                    except Exception as e:
                        print(f"Failed to send version message in {guild.name}: {e}")

@bot.event
async def on_guild_join(guild):
    for role_name in ["Beebot", "Announcement"]:
        role = discord.utils.get(guild.roles, name=role_name)
        if role is None:
            try:
                await guild.create_role(name=role_name)
            except Exception as e:
                print(f"Error creating role {role_name}: {e}")

# Crisis Choices + Command with Autocomplete
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
    return [
        choice for choice in CRISIS_CHOICES
        if current in choice.name.lower() or current in choice.value.lower()
    ][:25]

@bot.tree.command(name="crisis", description="Get a crisis line for your country (or see all).")
@app_commands.describe(country="Select a country or 'all'")
@app_commands.autocomplete(country=crisis_autocomplete)
async def crisis(interaction: discord.Interaction, country: str):
    country = country.strip().lower()
    crisis_lines = {
        "us": "🇺🇸 **US**: 988",
        "uk": "🇬🇧 **UK**: 116 123 (Samaritans)",
        "canada": "🇨🇦 **Canada**: 1-833-456-4566",
        "australia": "🇦🇺 **Australia**: 13 11 14",
        "global": "🌐 **Global**: https://www.befrienders.org/"
    }

    if country in crisis_lines:
        response = f"💛 We care about you. Please reach out:\n{crisis_lines[country]}"
    elif country == "all":
        response = (
            "💛 We care about you. Please reach out to a professional crisis line:\n\n"
            + "\n".join(crisis_lines.values())
        )
    else:
        response = (
            "⚠️ I don't recognize that country. Try one of these:\n"
            "`us`, `uk`, `canada`, `australia`, `global`, or `all`"
        )

    await interaction.response.send_message(response)

@bot.tree.command(name="bee_fact", description="Get a fun bee fact!")
async def bee_fact(interaction: discord.Interaction):
    fact = random.choice(BEE_FACTS) if BEE_FACTS else "🐝 Bees are amazing!"
    await interaction.response.send_message(fact)

@bot.tree.command(name="bee_question", description="Get everyones experiences with different things.")
async def bee_fact(interaction: discord.Interaction):
    fact = random.choice(BEE_QUESTIONS) if BEE_QUESTIONS else "I can't think of a question right now, but I love hearing yours!"
    await interaction.response.send_message(fact)

@bot.tree.command(name="bee_help", description="List BeeBot commands.")
async def bee_help(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🐝✨ **BeeBot Commands:**\n\n"
        "/ask [question]\n"
        "/bee_fact\n"
        "/bee_support\n"
        "/bee_mood [mood]\n"
        "/bee_gratitude [text]\n"
        "/bee_validate\n"
        "/bee_question\n"
        "/bee_announcement [text]\n"
        "/set_announcement_channel\n"
        "/set_version_channel\n"
        "/bee_msg [text]\n"
        "/bee_autoreply [on|off]\n"
        "/invite\n"
        "/bee_version\n"
        "/crisis [country|all]\n\n"
    )

@bot.tree.command(name="bee_support", description="Get mental health resources.")
async def bee_support(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🌻 **Mental health resources:**\n\n"
        "• [988 Lifeline (US)](https://988lifeline.org)\n"
        "• [Trans Lifeline](https://translifeline.org) – 877-565-8860\n"
        "• [International Support](https://findahelpline.com)\n\n"
        "🐝 Reaching out is brave. 💛"
    )

@bot.tree.command(name="bee_version", description="Show BeeBot version.")
async def bee_version(interaction: discord.Interaction):
    version, description = read_version_info()
    if version:
        await interaction.response.send_message(f"🐝 **BeeBot {version}**\n{description}")
    else:
        await interaction.response.send_message("⚠️ Version info not found.")

@bot.tree.command(name="bee_validate", description="Get a validating compliment.")
async def bee_validate(interaction: discord.Interaction):
    await handle_prompt(interaction, "Give me a validating compliment with bee puns and emojis.")

@bot.tree.command(name="ask", description="Ask BeeBot a question.")
async def ask(interaction: discord.Interaction, question: str):
    await handle_prompt(interaction, question)

@bot.tree.command(name="bee_mood", description="Share your mood with BeeBot.")
async def bee_mood(interaction: discord.Interaction, mood: str):
    await handle_prompt(interaction, f"My mood is: {mood}")

@bot.tree.command(name="bee_gratitude", description="Share something you're grateful for.")
async def bee_gratitude(interaction: discord.Interaction, gratitude: str):
    await handle_prompt(interaction, f"I'm grateful for: {gratitude}")

@bot.tree.command(name="bee_msg", description="DM yourself a message.")
async def bee_msg(interaction: discord.Interaction, message: str):
    try:
        await interaction.user.send(message)
        await interaction.response.send_message("✅ I've sent you a DM! 🍯", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("🚫 I can't DM you. Check your privacy settings.", ephemeral=True)

@bot.tree.command(name="bee_announcement", description="Post an announcement.")
async def bee_announcement(interaction: discord.Interaction, message: str):
    if not any(role.name.lower() == "announcement" for role in interaction.user.roles):
        await interaction.response.send_message("🚫 You need the **Announcement** role.", ephemeral=True)
        return

    channel_id = announcement_channels.get(interaction.guild.id)
    if channel_id:
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            # Markdown formatting will be preserved if passed correctly
            await channel.send(message, allowed_mentions=discord.AllowedMentions.none())
            await interaction.response.send_message("✅ Your announcement has been buzzed! 🐝", ephemeral=True)
            return

    await interaction.response.send_message("⚠️ No announcement channel set.", ephemeral=True)

@bot.tree.command(name="set_announcement_channel", description="Set the announcement channel.")
async def set_announcement_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("🚫 You need `Manage Channels` permission.", ephemeral=True)
        return
    announcement_channels[interaction.guild.id] = interaction.channel.id
    save_settings()
    await interaction.response.send_message(f"✅ Announcements will go here: {interaction.channel.mention}")

@bot.tree.command(name="set_version_channel", description="Set the version update channel.")
async def set_version_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("🚫 You need `Manage Channels` permission.", ephemeral=True)
        return
    version_channels[interaction.guild.id] = interaction.channel.id
    save_settings()
    await interaction.response.send_message(f"✅ Version updates will go here: {interaction.channel.mention}")

@bot.tree.command(name="invite", description="Get the BeeBot invite link.")
async def invite(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🐝 Invite me to your server:\n"
        "https://discord.com/oauth2/authorize?client_id=1390525585196847164&permissions=1689934340028480&integration_type=0&scope=applications.commands+bot"
    )

@bot.tree.command(name="bee_autoreply", description="Toggle BeeBot autoreply in this channel.")
async def bee_autoreply(interaction: discord.Interaction, mode: str):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("🚫 You need `Manage Channels` permission.", ephemeral=True)
        return
    guild_id = interaction.guild.id
    channel_id = interaction.channel.id
    if mode.lower() == "on":
        if guild_id not in auto_reply_channels:
            auto_reply_channels[guild_id] = set()
        auto_reply_channels[guild_id].add(channel_id)
        save_settings()
        await interaction.response.send_message("✅ Auto-reply enabled here! 🐝")
    elif mode.lower() == "off":
        if guild_id in auto_reply_channels and channel_id in auto_reply_channels[guild_id]:
            auto_reply_channels[guild_id].remove(channel_id)
            if len(auto_reply_channels[guild_id]) == 0:
                del auto_reply_channels[guild_id]
            save_settings()
            await interaction.response.send_message("❌ Auto-reply disabled here.")
    else:
        await interaction.response.send_message("❗ Use: `/bee_autoreply on` or `/bee_autoreply off`", ephemeral=True)

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    if message.guild.id in auto_reply_channels and message.channel.id in auto_reply_channels[message.guild.id]:
        await handle_prompt_raw(message.channel, message.content)

@bot.event
async def on_thread_create(thread):
    try:
        # Auto-reply only in forum channels (default behavior)
        if getattr(thread.parent, "type", None) != discord.ChannelType.forum:
            return

        # Skip if bot-created or no owner
        if thread.owner is None or thread.owner.bot:
            return

        await thread.join()  # Ensure the bot can see and reply to the thread

        # Get the first message posted in the thread
        starter_message = None
        async for msg in thread.history(limit=1, oldest_first=True):
            starter_message = msg

        title = thread.name
        description = starter_message.content if starter_message else "(no description provided)"
        user_mention = thread.owner.mention

        user_input = (
            f"A user created a forum post titled:\n"
            f"**{title}**\n\n"
            f"With this description:\n"
            f"{description}\n\n"
            f"Please validate both the user and the situation compassionately. "
            f"Start the response with:\n"
            f"'Hello,' [validation] 'Here is what you can do to better the situation.'\n\n"
            f"The tone should be warm, supportive, and bee-punny, using emojis naturally. "
            f"End with a hopeful suggestion or affirmation."
        )

        messages = build_prompt(user_input)
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.8
        )

        reply_text = f"{user_mention} 🐝\n\n" + response.choices[0].message.content
        await thread.send(reply_text)

    except Exception as e:
        print(f"Error responding to new thread: {e}")

async def handle_prompt(interaction, user_input):
    try:
        messages = build_prompt(user_input)
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo", messages=messages, temperature=0.8
        )
        await interaction.response.send_message(response.choices[0].message.content)
    except Exception as e:
        print(f"OpenAI Error: {e}")
        await interaction.response.send_message("⚠️ An error occurred.", ephemeral=True)

async def handle_prompt_raw(channel, user_input):
    try:
        messages = build_prompt(user_input)
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo", messages=messages, temperature=0.8
        )
        await channel.send(response.choices[0].message.content)
    except Exception as e:
        print(f"OpenAI Error: {e}")

# Run the bot
bot.run(DISCORD_TOKEN)
