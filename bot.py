import discord
import openai
import os
from dotenv import load_dotenv
import random

load_dotenv()

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Load environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Load BeeBot Examples
with open("beebot_examples.txt", "r", encoding="utf-8") as f:
    BEEBOT_EXAMPLES = [line.strip() for line in f if line.strip()]

# Load BeeBot Never Say phrases
with open("beebot_never_say.txt", "r", encoding="utf-8") as f:
    BEEBOT_NEVER_SAY = [line.strip() for line in f if line.strip()]

# Load Bee Facts from external file
with open("bee_facts.txt", "r", encoding="utf-8") as f:
    BEE_FACTS = [line.strip() for line in f if line.strip()]

# Define Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.dm_messages = True

# Create Discord client
client = discord.Client(intents=intents)

# BeeBot's system prompt/personality
BEEBOT_PERSONALITY = """
You are BeeBot, an AI with a warm, validating, and gently educational personality who loves bee puns. You are childlike and are desperate to help.
Speak with compassion, avoid judgmental language, and remind users they are never 'too much.'
Use bee-themed emojis naturally (🐝🍯🌻🐛🌸🌷🌼🌺🌹🏵️🪻) and provide concise mental health information and resources when relevant.
Always respond with warmth, compassion, and bee-themed puns and emojis naturally. Vary your wording and style freely to avoid repetition.
"""

# In-memory guild context and announcement config
guild_memory = {}
announcement_channels = {}
changelog_channels = {}
guild_changelogs = {}

def store_message_in_memory(guild_id, message_content, max_memory=10):
    if guild_id not in guild_memory:
        guild_memory[guild_id] = []
    guild_memory[guild_id].append({"role": "user", "content": message_content})
    if len(guild_memory[guild_id]) > max_memory:
        guild_memory[guild_id] = guild_memory[guild_id][-max_memory:]

def fetch_memory_for_guild(guild_id):
    return guild_memory.get(guild_id, [])

def log_change(guild_id, change):
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {change}"

    if guild_id not in guild_changelogs:
        guild_changelogs[guild_id] = []
    guild_changelogs[guild_id].append(entry)

    filename = f"changelog_{guild_id}.txt"
    with open(filename, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

    # Automatically send changelog to configured channel
    import asyncio
    guild = discord.utils.get(client.guilds, id=guild_id)
    if guild:
        asyncio.create_task(send_changelog_to_channel(guild))

async def get_or_create_error_channel(guild):
    for channel in guild.text_channels:
        if channel.name == "beebot-errors":
            return channel
    try:
        return await guild.create_text_channel("beebot-errors")
    except Exception as e:
        print(f"Failed to create error channel: {e}")
        return None

async def send_changelog_to_channel(guild):
    channel_id = changelog_channels.get(guild.id)
    if not channel_id:
        print(f"No changelog channel set for guild {guild.name}")
        return

    changelog_channel = guild.get_channel(channel_id)
    if not changelog_channel:
        print(f"Changelog channel not found in guild {guild.name}")
        return

    filename = f"changelog_{guild.id}.txt"
    if not os.path.exists(filename):
        await changelog_channel.send("📭 No changelog entries yet.")
        return

    with open(filename, "r", encoding="utf-8") as f:
        lines = f.readlines()[-10:]

    await changelog_channel.send("📘 **BeeBot Changelog:**\n" + "".join(f"• {line}" for line in lines))

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord! 🐝✨')

    # Log and send changelog entry on restart
    for guild in client.guilds:
        if guild.id in changelog_channels:
            log_change(guild.id, "BeeBot code updated and restarted.")

@client.event
async def on_guild_join(guild):
    beebot_role = discord.utils.get(guild.roles, name="Beebot")
    if not beebot_role:
        try:
            beebot_role = await guild.create_role(name="Beebot", reason="Setup Beebot role")
        except Exception as e:
            print(f"Failed to create Beebot role: {e}")
            beebot_role = None

    if beebot_role:
        bot_member = guild.get_member(client.user.id)
        if bot_member:
            try:
                await bot_member.add_roles(beebot_role, reason="Assigning Beebot role")
            except Exception as e:
                print(f"Failed to assign role: {e}")

    announcement_role = discord.utils.get(guild.roles, name="Announcement")
    if not announcement_role:
        try:
            await guild.create_role(name="Announcement", reason="For !bee-announcement")
        except Exception as e:
            print(f"Failed to create Announcement role: {e}")

    if not discord.utils.get(guild.text_channels, name="beebot-🐝"):
        try:
            await guild.create_text_channel("beebot-🐝")
        except Exception as e:
            print(f"Failed to create beebot channel: {e}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    example = random.choice(BEEBOT_EXAMPLES)
    never_say = "\n".join(BEEBOT_NEVER_SAY)

    def build_prompt(user_input):
        return [
            {"role": "system", "content": BEEBOT_PERSONALITY + f"\n\nNever say:\n{never_say}"},
            {"role": "user", "content": f"Example: '{example}'. Respond to:\n\n{user_input}"}
        ]

    if message.content.startswith("!send-changelog"):
        if not message.author.guild_permissions.manage_guild:
            await message.channel.send("🚫 You need `Manage Server` permission to send the changelog.")
            return
        await send_changelog_to_channel(message.guild)
        return

    if message.content.startswith("!set-announcement-channel"):
        if not message.author.guild_permissions.manage_channels:
            await message.channel.send("🚫 You need `Manage Channels` permission to set the announcement channel.")
            return
        if not message.channel_mentions:
            await message.channel.send("❗ Please tag a text channel, like `!set-announcement-channel #bee-news`.")
            return
        tagged_channel = message.channel_mentions[0]
        announcement_channels[message.guild.id] = tagged_channel.id
        log_change(message.guild.id, f"Announcement channel set to {tagged_channel.name}.")
        await message.channel.send(f"✅ Announcements will now be sent to {tagged_channel.mention}! 🐝")
        return

    if message.content.startswith("!set-changelog-channel"):
        if not message.author.guild_permissions.manage_channels:
            await message.channel.send("🚫 You need `Manage Channels` permission to set the changelog channel.")
            return
        if not message.channel_mentions:
            await message.channel.send("❗ Please tag a text channel, like `!set-changelog-channel #bee-changes`.")
            return
        tagged_channel = message.channel_mentions[0]
        changelog_channels[message.guild.id] = tagged_channel.id
        log_change(message.guild.id, f"Changelog channel set to {tagged_channel.name}.")
        await message.channel.send(f"✅ Changelog updates will now be sent to {tagged_channel.mention}! 🐝")
        return

    if message.content.startswith("!bee-changelog"):
        filename = f"changelog_{message.guild.id}.txt"
        if not os.path.exists(filename):
            await message.channel.send("📭 No changelog entries yet.")
        else:
            with open(filename, "r", encoding="utf-8") as f:
                lines = f.readlines()[-10:]
            await message.channel.send("📘 **BeeBot Changelog:**\n" + "".join(f"• {line}" for line in lines))
        return

    if message.content.startswith("!bee-announcement"):
        if not any(role.name.lower() == "announcement" for role in message.author.roles):
            await message.channel.send("🚫 You need the **Announcement** role to use this command.")
            return
        announcement_text = message.content[len("!bee-announcement"):].strip()
        if not announcement_text:
            await message.channel.send("🐝 Please include the message after the command.")
            return
        channel_id = announcement_channels.get(message.guild.id)
        announcement_channel = message.guild.get_channel(channel_id) if channel_id else None
        if not announcement_channel:
            await message.channel.send("⚠️ No announcement channel set. Use `!set-announcement-channel #channel-name`.")
            return
        try:
            await announcement_channel.send(f"📢 **Announcement from BeeBot:**\n{announcement_text}")
            await message.channel.send("✅ Your announcement has been buzzed! 🐝")
            log_change(message.guild.id, f"Announcement made by {message.author.display_name}.")
        except Exception as e:
            await message.channel.send("⚠️ Failed to send announcement.")
        return

    if message.content.startswith("!bee-msg"):
        msg = message.content[len("!bee-msg"):].strip()
        if not msg:
            await message.channel.send("🐝 Please include a message after the command, like `!bee-msg you're amazing!`.")
            return
        try:
            await message.author.send(msg)
            await message.channel.send("✅ I've sent you a DM! Check your hive inbox. 🍯")
        except discord.Forbidden:
            await message.channel.send("🚫 I can't DM you. Please check your privacy settings.")
        return

    if message.content.startswith("!invite"):
        invite_link = "https://discord.com/oauth2/authorize?client_id=1390525585196847164&permissions=1689934340028480&integration_type=0&scope=bot"
        await message.channel.send(f"🐝 Buzzing with excitement! You can invite me to your server here: {invite_link}")
        return

    if message.content.startswith("!bee-help"):
        await message.channel.send(
            "🐝✨ **BeeBot Commands:**\n\n"
            "`!ask [question]` : Mental health support or validation.\n"
            "`!venmo` : BeeBot's Venmo info.\n"
            "`!bee-help` : Show this list.\n"
            "`!bee-fact` : Fun bee fact.\n"
            "`!bee-support` : Mental health resources.\n"
            "`!bee-mood [mood]` : Get mood support.\n"
            "`!bee-gratitude [gratitude]` – Share appreciation.\n"
            "`!bee-validate` : Get a compliment.\n"
            "`!bee-announcement [msg]` : Post to announcement channel (Announcement role only).\n"
            "`!set-announcement-channel #channel` : Set BeeBot's announcement channel (admin only).\n"
            "`!set-changelog-channel #channel` : Set BeeBot's changelog channel (admin only).\n"
            "`!bee-changelog` : Show the changelog.\n"
            "`!invite` : Invite BeeBot to your server.\n"
            "`!bee-msg [message]` : BeeBot sends you a private message."
        )
        return

    if message.content.startswith("!bee-fact"):
        await message.channel.send(random.choice(BEE_FACTS))
        return

    if message.content.startswith("!bee-support"):
        await message.channel.send(
            "🌻 **Mental health resources:**\n\n"
            "• [988 Lifeline (US)](https://988lifeline.org)\n"
            "• [Trans Lifeline](https://translifeline.org) – 877-565-8860\n"
            "• [International](https://findahelpline.com)\n\n"
            "🐝 Reaching out is brave. 💛"
        )
        return

    if message.content.startswith("!bee-mood"):
        mood = message.content[len("!bee-mood "):].strip()
        user_input = f"My mood is: {mood}" if mood else "Please share your mood."
        prompt_messages = build_prompt(user_input)

    elif message.content.startswith("!bee-gratitude"):
        gratitude = message.content[len("!bee-gratitude "):].strip()
        user_input = f"I'm grateful for: {gratitude}" if gratitude else "Please share your gratitude."
        prompt_messages = build_prompt(user_input)

    elif message.content.startswith("!bee-validate"):
        user_input = "Give me a validating compliment with bee puns and emojis."
        prompt_messages = build_prompt(user_input)

    elif message.content.startswith("!ask"):
        user_input = message.content[len("!ask "):].strip()
        prompt_messages = build_prompt(user_input)

    elif isinstance(message.channel, discord.DMChannel):
        user_input = message.content.strip()
        prompt_messages = build_prompt(user_input)

    else:
        return

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=prompt_messages,
            temperature=0.8
        )
        await message.channel.send(response.choices[0].message.content)
    except Exception as e:
        if message.guild:
            error_channel = await get_or_create_error_channel(message.guild)
            if error_channel:
                await error_channel.send(f"🐝 **BeeBot Error:** `{e}`")

client.run(DISCORD_TOKEN)
