import os
import random
import json
import discord
from discord.ext import commands
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

SETTINGS_FILE = "guild_settings.json"

def load_lines(filename):
    return [line.strip() for line in open(filename, "r", encoding="utf-8") if line.strip()] if os.path.exists(filename) else []

BEEBOT_PERSONALITY = """
You are BeeBot, an AI with a warm, validating, and gently educational personality who loves bee puns. You are childlike and are desperate to help.
Speak with compassion, avoid judgmental language, and remind users they are never 'too much.'
Use bee-themed emojis naturally (🐝🍯🌻🐛🌸🌷🌼🌺🌹🏵️🪻) and provide concise mental health information and resources when relevant.
Always respond with warmth, compassion, and bee-themed puns and emojis naturally. Vary your wording and style freely to avoid repetition.
"""

BEEBOT_EXAMPLES = load_lines("beebot_examples.txt")
BEEBOT_NEVER_SAY = load_lines("beebot_never_say.txt")
BEE_FACTS = load_lines("bee_facts.txt")

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            return {
                "auto_reply_channels": {int(k): set(v) for k, v in data.get("auto_reply_channels", {}).items()},
                "announcement_channels": {int(k): v for k, v in data.get("announcement_channels", {}).items()},
                "version_channels": {int(k): v for k, v in data.get("version_channels", {}).items()}
            }
    return {
        "auto_reply_channels": {},
        "announcement_channels": {},
        "version_channels": {}
    }

def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump({
            "auto_reply_channels": {str(k): list(v) for k, v in auto_reply_channels.items()},
            "announcement_channels": {str(k): v for k, v in announcement_channels.items()},
            "version_channels": {str(k): v for k, v in version_channels.items()}
        }, f, indent=2)

settings = load_settings()
auto_reply_channels = settings["auto_reply_channels"]
announcement_channels = settings["announcement_channels"]
version_channels = settings["version_channels"]

guild_memory = {}

def store_message_in_memory(guild_id, message, max_memory=10):
    guild_memory.setdefault(guild_id, []).append({"role": "user", "content": message})
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
    return lines[0], "\n".join(lines[1:]) if len(lines) > 1 else ""

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord! 🐝✨')
    version, description = read_version_info()
    if version:
        version_msg = f"🐝 **BeeBot {version}**\n{description}"
        for guild in bot.guilds:
            if (channel_id := version_channels.get(guild.id)):
                channel = guild.get_channel(channel_id)
                if channel:
                    try:
                        await channel.send(version_msg)
                    except Exception as e:
                        print(f"Failed to send version message in {guild.name}: {e}")

@bot.event
async def on_guild_join(guild):
    for role_name in ["Beebot", "Announcement"]:
        if not discord.utils.get(guild.roles, name=role_name):
            try:
                await guild.create_role(name=role_name)
            except Exception as e:
                print(f"Error creating role {role_name}: {e}")

@bot.tree.command(name="bee_fact", description="Get a fun bee fact!")
async def bee_fact(interaction: discord.Interaction):
    fact = random.choice(BEE_FACTS) if BEE_FACTS else "🐝 Bees are amazing!"
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
        "/bee_announcement [text]\n"
        "/set_announcement_channel\n"
        "/set_version_channel\n"
        "/bee_msg [text]\n"
        "/bee_autoreply [on|off]\n"
        "/invite\n"
        "/bee_version"
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
    await interaction.response.send_message(
        f"🐝 **BeeBot {version}**\n{description}" if version else "⚠️ Version info not found."
    )

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
    if (channel := interaction.guild.get_channel(channel_id)) if channel_id else None:
        await channel.send(f"📢 **Announcement from BeeBot:**\n{message}")
        await interaction.response.send_message("✅ Your announcement has been buzzed! 🐝", ephemeral=True)
    else:
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
        "https://discord.com/oauth2/authorize?client_id=1390525585196847164&permissions=1689934340028480&integration_type=0&scope=bot"
    )

@bot.tree.command(name="bee_autoreply", description="Toggle BeeBot autoreply in this channel.")
async def bee_autoreply(interaction: discord.Interaction, mode: str):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("🚫 You need `Manage Channels` permission.", ephemeral=True)
        return
    guild_id = interaction.guild.id
    channel_id = interaction.channel.id
    if mode.lower() == "on":
        auto_reply_channels.setdefault(guild_id, set()).add(channel_id)
        save_settings()
        await interaction.response.send_message("✅ Auto-reply enabled here! 🐝")
    elif mode.lower() == "off":
        auto_reply_channels.get(guild_id, set()).discard(channel_id)
        if not auto_reply_channels[guild_id]:
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

bot.run(DISCORD_TOKEN)
