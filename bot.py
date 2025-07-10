import os
import random
import json
import discord
from discord.ext import commands
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Initialise OpenAI client with API key
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Define bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.dm_messages = True

# Create bot instance with command prefix '!' and specified intents
bot = commands.Bot(command_prefix="!", intents=intents)

# Settings file for storing per-guild configurations
SETTINGS_FILE = "guild_settings.json"

# Function to load lines from a text file into a list
def load_lines(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    else:
        return []

# Define BeeBot personality for prompt system messages
BEEBOT_PERSONALITY = """
You are BeeBot, an AI with a warm, validating, and gently educational personality who loves bee puns. You are childlike and are desperate to help.
Speak with compassion, avoid judgmental language, and remind users they are never 'too much.'
Use bee-themed emojis naturally (🐝🍯🌻🐛🌸🌷🌼🌺🌹🏵️🪻) and provide concise mental health information and resources when relevant.
Always respond with warmth, compassion, and bee-themed puns and emojis naturally. Vary your wording and style freely to avoid repetition.
"""

# Load BeeBot example prompts, forbidden phrases, and bee facts
BEEBOT_EXAMPLES = load_lines("beebot_examples.txt")
BEEBOT_NEVER_SAY = load_lines("beebot_never_say.txt")
BEE_FACTS = load_lines("bee_facts.txt")

# Function to load guild settings from JSON file
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            return {
                "auto_reply_channels": {int(k): set(v) for k, v in data.get("auto_reply_channels", {}).items()},
                "announcement_channels": {int(k): v for k, v in data.get("announcement_channels", {}).items()},
                "version_channels": {int(k): v for k, v in data.get("version_channels", {}).items()}
            }
    else:
        return {
            "auto_reply_channels": {},
            "announcement_channels": {},
            "version_channels": {}
        }

# Function to save guild settings to JSON file
def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump({
            "auto_reply_channels": {str(k): list(v) for k, v in auto_reply_channels.items()},
            "announcement_channels": {str(k): v for k, v in announcement_channels.items()},
            "version_channels": {str(k): v for k, v in version_channels.items()}
        }, f, indent=2)

# Load settings upon startup
settings = load_settings()
auto_reply_channels = settings["auto_reply_channels"]
announcement_channels = settings["announcement_channels"]
version_channels = settings["version_channels"]

# In-memory store for message history per guild
guild_memory = {}

# Function to store messages in memory for each guild, keeping a maximum defined memory length
def store_message_in_memory(guild_id, message, max_memory=10):
    if guild_id not in guild_memory:
        guild_memory[guild_id] = []
    guild_memory[guild_id].append({"role": "user", "content": message})
    guild_memory[guild_id] = guild_memory[guild_id][-max_memory:]

# Function to build the OpenAI chat prompt using BeeBot personality, forbidden phrases, and an example
def build_prompt(user_input):
    return [
        {"role": "system", "content": BEEBOT_PERSONALITY + f"\n\nNever say:\n{chr(10).join(BEEBOT_NEVER_SAY)}"},
        {"role": "user", "content": f"Example: '{random.choice(BEEBOT_EXAMPLES)}'. Respond to:\n\n{user_input}"}
    ]

# Function to read version info from version.txt
def read_version_info(file_path="version.txt"):
    if not os.path.exists(file_path):
        return None, None
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    if len(lines) > 1:
        return lines[0], "\n".join(lines[1:])
    else:
        return lines[0], ""

# on_ready event fires when the bot is connected and ready
@bot.event
async def on_ready():
    # Sync slash commands with Discord to ensure they appear in servers
    await bot.tree.sync()
    print(f'{bot.user} has connected to Discord! 🐝✨')
    print("✅ Slash commands synced successfully.")

    # Send version info to configured version channels
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

# Event handler for when BeeBot joins a new guild to create default roles
@bot.event
async def on_guild_join(guild):
    for role_name in ["Beebot", "Announcement"]:
        role = discord.utils.get(guild.roles, name=role_name)
        if role is None:
            try:
                await guild.create_role(name=role_name)
            except Exception as e:
                print(f"Error creating role {role_name}: {e}")

# All slash command definitions are below

# /bee_fact command returns a random bee fact
@bot.tree.command(name="bee_fact", description="Get a fun bee fact!")
async def bee_fact(interaction: discord.Interaction):
    fact = random.choice(BEE_FACTS) if BEE_FACTS else "🐝 Bees are amazing!"
    await interaction.response.send_message(fact)

# /bee_help command lists all BeeBot commands
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
        "/bee_announcement [text]\n"
        "/set_announcement_channel\n"
        "/set_version_channel\n"
        "/bee_msg [text]\n"
        "/bee_autoreply [on|off]\n"
        "/invite\n"
        "/bee_version"
    )

# /bee_support command returns mental health resources
@bot.tree.command(name="bee_support", description="Get mental health resources.")
async def bee_support(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🌻 **Mental health resources:**\n\n"
        "• [988 Lifeline (US)](https://988lifeline.org)\n"
        "• [Trans Lifeline](https://translifeline.org) – 877-565-8860\n"
        "• [International Support](https://findahelpline.com)\n\n"
        "🐝 Reaching out is brave. 💛"
    )

# /bee_version command returns BeeBot version info
@bot.tree.command(name="bee_version", description="Show BeeBot version.")
async def bee_version(interaction: discord.Interaction):
    version, description = read_version_info()
    if version:
        await interaction.response.send_message(f"🐝 **BeeBot {version}**\n{description}")
    else:
        await interaction.response.send_message("⚠️ Version info not found.")

# /bee_validate command returns a validating compliment
@bot.tree.command(name="bee_validate", description="Get a validating compliment.")
async def bee_validate(interaction: discord.Interaction):
    await handle_prompt(interaction, "Give me a validating compliment with bee puns and emojis.")

# /ask command sends a user question to OpenAI and returns the response
@bot.tree.command(name="ask", description="Ask BeeBot a question.")
async def ask(interaction: discord.Interaction, question: str):
    await handle_prompt(interaction, question)

# /bee_mood command shares user mood with BeeBot for validation
@bot.tree.command(name="bee_mood", description="Share your mood with BeeBot.")
async def bee_mood(interaction: discord.Interaction, mood: str):
    await handle_prompt(interaction, f"My mood is: {mood}")

# /bee_gratitude command shares gratitude with BeeBot
@bot.tree.command(name="bee_gratitude", description="Share something you're grateful for.")
async def bee_gratitude(interaction: discord.Interaction, gratitude: str):
    await handle_prompt(interaction, f"I'm grateful for: {gratitude}")

# /bee_msg command DMs the user
@bot.tree.command(name="bee_msg", description="DM yourself a message.")
async def bee_msg(interaction: discord.Interaction, message: str):
    try:
        await interaction.user.send(message)
        await interaction.response.send_message("✅ I've sent you a DM! 🍯", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("🚫 I can't DM you. Check your privacy settings.", ephemeral=True)

# /bee_announcement command posts an announcement to configured channel
@bot.tree.command(name="bee_announcement", description="Post an announcement.")
async def bee_announcement(interaction: discord.Interaction, message: str):
    if not any(role.name.lower() == "announcement" for role in interaction.user.roles):
        await interaction.response.send_message("🚫 You need the **Announcement** role.", ephemeral=True)
        return
    channel_id = announcement_channels.get(interaction.guild.id)
    if channel_id:
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            await channel.send(f"📢 **Announcement from BeeBot:**\n{message}")
            await interaction.response.send_message("✅ Your announcement has been buzzed! 🐝", ephemeral=True)
            return
    await interaction.response.send_message("⚠️ No announcement channel set.", ephemeral=True)

# /set_announcement_channel command sets the announcement channel for the guild
@bot.tree.command(name="set_announcement_channel", description="Set the announcement channel.")
async def set_announcement_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("🚫 You need `Manage Channels` permission.", ephemeral=True)
        return
    announcement_channels[interaction.guild.id] = interaction.channel.id
    save_settings()
    await interaction.response.send_message(f"✅ Announcements will go here: {interaction.channel.mention}")

# /set_version_channel command sets the version channel for the guild
@bot.tree.command(name="set_version_channel", description="Set the version update channel.")
async def set_version_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("🚫 You need `Manage Channels` permission.", ephemeral=True)
        return
    version_channels[interaction.guild.id] = interaction.channel.id
    save_settings()
    await interaction.response.send_message(f"✅ Version updates will go here: {interaction.channel.mention}")

# /invite command sends the BeeBot invite link
@bot.tree.command(name="invite", description="Get the BeeBot invite link.")
async def invite(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🐝 Invite me to your server:\n"
        "https://discord.com/oauth2/authorize?client_id=1390525585196847164&permissions=1689934340028480&integration_type=0&scope=applications.commands+bot")

# /bee_autoreply command toggles auto-reply feature for current channel
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

# Event handler for on_message for auto-reply channels
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    if message.guild.id in auto_reply_channels and message.channel.id in auto_reply_channels[message.guild.id]:
        await handle_prompt_raw(message.channel, message.content)

# Function to handle OpenAI prompt responses for interactions
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

# Function to handle raw prompt responses for auto-replies
async def handle_prompt_raw(channel, user_input):
    try:
        messages = build_prompt(user_input)
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo", messages=messages, temperature=0.8
        )
        await channel.send(response.choices[0].message.content)
    except Exception as e:
        print(f"OpenAI Error: {e}")

# Run the bot using the Discord token
bot.run(DISCORD_TOKEN)
