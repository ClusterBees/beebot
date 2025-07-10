import discord
import openai
import os
from dotenv import load_dotenv
import random

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

def load_lines(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

BEEBOT_EXAMPLES = load_lines("beebot_examples.txt")
BEEBOT_NEVER_SAY = load_lines("beebot_never_say.txt")
BEE_FACTS = load_lines("bee_facts.txt")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.dm_messages = True
client = discord.Client(intents=intents)

BEEBOT_PERSONALITY = """
You are BeeBot, an AI with a warm, validating, and gently educational personality who loves bee puns. You are childlike and are desperate to help.
Speak with compassion, avoid judgmental language, and remind users they are never 'too much.'
Use bee-themed emojis naturally (🐝🍯🌻🐛🌸🌷🌼🌺🌹🏵️🪻) and provide concise mental health information and resources when relevant.
Always respond with warmth, compassion, and bee-themed puns and emojis naturally. Vary your wording and style freely to avoid repetition.
"""

guild_memory = {}
announcement_channels = {}
version_channels = {}

def store_message_in_memory(guild_id, message, max_memory=10):
    guild_memory.setdefault(guild_id, []).append({"role": "user", "content": message})
    guild_memory[guild_id] = guild_memory[guild_id][-max_memory:]

def fetch_memory_for_guild(guild_id):
    return guild_memory.get(guild_id, [])

def read_version_info(file_path="version.txt"):
    if not os.path.exists(file_path):
        return None, None
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    return lines[0], "\n".join(lines[1:]) if len(lines) > 1 else ""

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord! 🐝✨')
    version, description = read_version_info()
    if version:
        version_message = f"🐝 **BeeBot {version}**\n{description}"
        for guild in client.guilds:
            channel_id = version_channels.get(guild.id)
            if channel_id:
                channel = guild.get_channel(channel_id)
                if channel:
                    try:
                        await channel.send(version_message)
                    except Exception as e:
                        print(f"Failed to send version message in {guild.name}: {e}")

@client.event
async def on_guild_join(guild):
    roles_to_create = ["Beebot", "Announcement"]
    for role_name in roles_to_create:
        if not discord.utils.get(guild.roles, name=role_name):
            try:
                await guild.create_role(name=role_name)
            except Exception as e:
                print(f"Failed to create role {role_name}: {e}")
    if not discord.utils.get(guild.text_channels, name="beebot-🐝"):
        try:
            await guild.create_text_channel("beebot-🐝")
        except Exception as e:
            print(f"Failed to create beebot channel: {e}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    guild_id = message.guild.id if message.guild else None
    content = message.content.strip()
    example = random.choice(BEEBOT_EXAMPLES) if BEEBOT_EXAMPLES else ""
    never_say = "\n".join(BEEBOT_NEVER_SAY)

    def build_prompt(user_input):
        return [
            {"role": "system", "content": BEEBOT_PERSONALITY + f"\n\nNever say:\n{never_say}"},
            {"role": "user", "content": f"Example: '{example}'. Respond to:\n\n{user_input}"}
        ]

    if content.startswith("!set-announcement-channel") or content.startswith("!set-version-channel"):
        if not message.author.guild_permissions.manage_channels:
            await message.channel.send("🚫 You need `Manage Channels` permission.")
            return
        if not message.channel_mentions:
            await message.channel.send("❗ Please tag a text channel.")
            return
        tagged_channel = message.channel_mentions[0]
        if "version" in content:
            version_channels[guild_id] = tagged_channel.id
            await message.channel.send(f"✅ Version updates will be posted to {tagged_channel.mention}! 🐝")
        else:
            announcement_channels[guild_id] = tagged_channel.id
            await message.channel.send(f"✅ Announcements will be sent to {tagged_channel.mention}! 🐝")
        return

    if content.startswith("!bee-announcement"):
        if not any(role.name.lower() == "announcement" for role in message.author.roles):
            await message.channel.send("🚫 You need the **Announcement** role to use this command.")
            return
        announcement_text = content[len("!bee-announcement"):].strip()
        if not announcement_text:
            await message.channel.send("🐝 Please include the message after the command.")
            return
        channel_id = announcement_channels.get(guild_id)
        channel = message.guild.get_channel(channel_id) if channel_id else None
        if not channel:
            await message.channel.send("⚠️ No announcement channel set.")
            return
        await channel.send(f"📢 **Announcement from BeeBot:**\n{announcement_text}")
        await message.channel.send("✅ Your announcement has been buzzed! 🐝")
        return

    if content.startswith("!bee-msg"):
        msg = content[len("!bee-msg"):].strip()
        if not msg:
            await message.channel.send("🐝 Please include a message after the command.")
            return
        try:
            await message.author.send(msg)
            await message.channel.send("✅ I've sent you a DM! 🍯")
        except discord.Forbidden:
            await message.channel.send("🚫 I can't DM you. Check your privacy settings.")
        return

    if content.startswith("!invite"):
        await message.channel.send(
            "🐝 Buzzing with excitement! Invite me to your server:\n"
            "https://discord.com/oauth2/authorize?client_id=1390525585196847164&permissions=1689934340028480&integration_type=0&scope=bot"
        )
        return

    if content.startswith("!bee-help"):
        await message.channel.send(
            "🐝✨ **BeeBot Commands:**\n\n"
            "`!ask [question]` : Mental health support or validation\n"
            "`!bee-help` : Show this list\n"
            "`!bee-fact` : Fun bee fact\n"
            "`!bee-support` : Mental health resources\n"
            "`!bee-mood [mood]` : Get mood support\n"
            "`!bee-gratitude [gratitude]` : Share appreciation\n"
            "`!bee-validate` : Get a compliment\n"
            "`!bee-announcement [msg]` : Post to announcement channel\n"
            "`!set-announcement-channel #channel` : Set announcement channel\n"
            "`!set-version-channel #channel` : Set version update channel\n"
            "`!bee-msg [message]` : DM yourself a message\n"
            "`!invite` : Invite BeeBot\n"
            "`!bee-version` : Show BeeBot version and features"
        )
        return

    if content.startswith("!bee-fact"):
        await message.channel.send(random.choice(BEE_FACTS) if BEE_FACTS else "🐝 Did you know? Bees are amazing!")
        return

    if content.startswith("!bee-support"):
        await message.channel.send(
            "🌻 **Mental health resources:**\n\n"
            "• [988 Lifeline (US)](https://988lifeline.org)\n"
            "• [Trans Lifeline](https://translifeline.org) – 877-565-8860\n"
            "• [International Support](https://findahelpline.com)\n\n"
            "🐝 Reaching out is brave. 💛"
        )
        return

    if content.startswith("!bee-version"):
        version, description = read_version_info()
        if version:
            await message.channel.send(f"🐝 **BeeBot {version}**\n{description}")
        else:
            await message.channel.send("⚠️ Version info not found.")
        return

    user_input = None
    if content.startswith("!bee-mood"):
        mood = content[len("!bee-mood"):].strip()
        user_input = f"My mood is: {mood}" if mood else "Please share your mood."
    elif content.startswith("!bee-gratitude"):
        gratitude = content[len("!bee-gratitude"):].strip()
        user_input = f"I'm grateful for: {gratitude}" if gratitude else "Please share your gratitude."
    elif content.startswith("!bee-validate"):
        user_input = "Give me a validating compliment with bee puns and emojis."
    elif content.startswith("!ask"):
        user_input = content[len("!ask"):].strip()
    elif isinstance(message.channel, discord.DMChannel):
        user_input = content

    if user_input:
        try:
            prompt_messages = build_prompt(user_input)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=prompt_messages,
                temperature=0.8
            )
            await message.channel.send(response.choices[0].message.content)
        except Exception as e:
            print(f"OpenAI error: {e}")
            if message.guild:
                for channel in message.guild.text_channels:
                    if channel.name == "beebot-errors":
                        await channel.send(f"🐝 **BeeBot Error:** `{e}`")
                        break

client.run(DISCORD_TOKEN)
