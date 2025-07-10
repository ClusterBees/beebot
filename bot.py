import discord
from openai import OpenAI
import os
from dotenv import load_dotenv
import random

load_dotenv()

# Initialize OpenAI client
client_ai = OpenAI()

# Load environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Load BeeBot Examples
with open("beebot_examples.txt", "r", encoding="utf-8") as f:
    BEEBOT_EXAMPLES = [line.strip() for line in f if line.strip()]

# Load BeeBot Never Say phrases
with open("beebot_never_say.txt", "r", encoding="utf-8") as f:
    BEEBOT_NEVER_SAY = [line.strip() for line in f if line.strip()]

# Define Discord intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.dm_messages = True

# Create Discord client
client = discord.Client(intents=intents)

# BeeBot's system prompt/personality
BEEBOT_PERSONALITY = """
You are BeeBot, an AI with a warm, validating, and gently educational personality who loves bee puns.
Speak with compassion, avoid judgmental language, and remind users they are never 'too much.'
Use bee-themed emojis naturally (🐝🍯🌻) and provide concise mental health information and resources when relevant.
Always respond with warmth, compassion, and bee-themed puns and emojis naturally. Vary your wording and style freely to avoid repetition.
"""

# Sample bee facts
BEE_FACTS = [
    "🐝 Did you know? Bees communicate through dances to share where flowers are found!",
    "🍯 Bees have five eyes, two large ones and three tiny ones on top of their heads!",
    "🌻 Honey never spoils. Archaeologists found honey in ancient Egyptian tombs that is still edible today!",
    "🐝 A single bee can visit 5,000 flowers in a day while collecting nectar.",
    "🍯 Bees are essential pollinators, supporting over a third of the food we eat!",
    "🌸 The queen bee can lay up to 2,000 eggs in a single day to grow the hive.",
    "🐝 Male bees are called drones, and their only job is to mate with a queen.",
    "🍯 Bees beat their wings about 200 times per second, creating their signature buzzing sound!",
    "🌻 A bee produces only about 1/12th of a teaspoon of honey in its entire lifetime.",
    "🐝 Bees can recognize human faces, remembering them like we remember each other’s faces.",
    "🍯 The hexagon shape of honeycombs is the strongest and most efficient shape in nature.",
    "🌸 Bees have been around for about 100 million years, evolving alongside flowering plants.",
    "🐝 When bees find a good food source, they perform a ‘waggle dance’ to show its distance and direction.",
    "🍯 Honey has natural antibacterial properties and was used to treat wounds in ancient times.",
    "🌻 Worker bees are all female, doing every job in the hive except mating and laying fertilized eggs."
]

# In-memory guild context and announcement config
guild_memory = {}
announcement_channels = {}

def store_message_in_memory(guild_id, message_content, max_memory=10):
    if guild_id not in guild_memory:
        guild_memory[guild_id] = []
    guild_memory[guild_id].append({"role": "user", "content": message_content})
    if len(guild_memory[guild_id]) > max_memory:
        guild_memory[guild_id] = guild_memory[guild_id][-max_memory:]

def fetch_memory_for_guild(guild_id):
    return guild_memory.get(guild_id, [])

async def get_or_create_error_channel(guild):
    for channel in guild.text_channels:
        if channel.name == "beebot-errors":
            return channel
    try:
        return await guild.create_text_channel("beebot-errors")
    except Exception as e:
        print(f"Failed to create error channel: {e}")
        return None

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord! 🐝✨')

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

    if message.content.startswith("!set-announcement-channel"):
        if not message.author.guild_permissions.manage_channels:
            await message.channel.send("🚫 You need `Manage Channels` permission to set the announcement channel.")
            return
        if not message.channel_mentions:
            await message.channel.send("❗ Please tag a text channel, like `!set-announcement-channel #bee-news`.")
            return
        tagged_channel = message.channel_mentions[0]
        announcement_channels[message.guild.id] = tagged_channel.id
        await message.channel.send(f"✅ Announcements will now be sent to {tagged_channel.mention}! 🐝")
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

    # OpenAI command inputs
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
        response = client_ai.chat.completions.create(
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
