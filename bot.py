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
Always phrase your responses differently to avoid repetition, using varied wording, sentence structures, and bee-themed expressions to maintain freshness.
"""

# Sample bee facts
BEE_FACTS = [
    "🐝 Did you know? Bees communicate through dances to share where flowers are found!",
    "🍯 Bees have five eyes, two large ones and three tiny ones on top of their heads!",
    "🌻 Honey never spoils. Archaeologists found honey in ancient Egyptian tombs that is still edible today!",
    "🐝 A single bee can visit 5,000 flowers in a day while collecting nectar.",
    "🍯 Bees are essential pollinators, supporting over a third of the food we eat!"
]

# Compliments and validation messages (kept as fallback)
BEE_VALIDATION = [
    "🐝✨ You are such a bright and gentle soul, and the world is sweeter with you in it. 💛",
    "🍯 You are doing so well, even on days you doubt yourself. Your effort matters, and so do you. 🌻",
    "🐝 You carry so much wisdom and beauty within you. Please don’t ever forget how deeply loved you are. 💛",
    "🌻 Your existence brings warmth and light to those around you, like the sun nourishing flowers. 🍯",
    "🐝 Even when you feel unseen, I see your strength, courage, and kindness shining brightly. 💛",
    "🍯 You are never too much. Your feelings, your needs, your hopes – all are welcome here. 🌻",
    "🐝 You deserve rest, peace, and moments of gentle sweetness. Please be kind to yourself today. 💛"
]

guild_memory = {}

def store_message_in_memory(guild_id, message_content, max_memory=10):
    if guild_id not in guild_memory:
        guild_memory[guild_id] = []
    guild_memory[guild_id].append({"role": "user", "content": message_content})
    if len(guild_memory[guild_id]) > max_memory:
        guild_memory[guild_id] = guild_memory[guild_id][-max_memory:]

def fetch_memory_for_guild(guild_id):
    return guild_memory.get(guild_id, [])

async def get_or_create_error_channel(guild):
    channel_name = "beebot-errors"
    for channel in guild.text_channels:
        if channel.name == channel_name:
            return channel
    try:
        return await guild.create_text_channel(channel_name)
    except Exception as e:
        print(f"Failed to create error channel: {e}")
        return None

async def get_or_create_forum_channel(guild):
    forum_name = "beebot-questions"
    for channel in guild.channels:
        if isinstance(channel, discord.ForumChannel) and channel.name == forum_name:
            return channel
    try:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        return await guild.create_forum_channel(forum_name, overwrites=overwrites, reason="Creating BeeBot forum channel")
    except Exception as e:
        print(f"Failed to create forum channel: {e}")
        error_channel = await get_or_create_error_channel(guild)
        if error_channel:
            await error_channel.send(f"🐝 **BeeBot Forum Channel Error:** `{e}`")
        return None

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord! 🐝✨')
    for guild in client.guilds:
        await get_or_create_forum_channel(guild)

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # --- Forum first post auto-response ---
    if isinstance(message.channel, discord.Thread):
        if message.id == message.channel.id:
            try:
                prompt = (
                    f"A user has created a new forum thread titled '{message.channel.name}' with the following post:\n\n"
                    f"{message.content}\n\n"
                    "Please greet them warmly with BeeBot's validating style, mention bee-themed emojis, address what they've already said, and invite them to share more if they wish."
                )

                response = client_ai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": BEEBOT_PERSONALITY},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8
                )
                ai_message = response.choices[0].message.content
                await message.channel.send(ai_message)

            except Exception as e:
                print(f"Error sending AI reply to thread: {e}")
                if message.guild:
                    error_channel = await get_or_create_error_channel(message.guild)
                    if error_channel:
                        await error_channel.send(f"🐝 **BeeBot Thread Error:** `{e}`")
            return

    # --- Existing commands ---
    if message.content.startswith("!venmo"):
        await message.channel.send(
            "🐝✨ Here is my Venmo info, sweet human:\n\n"
            "**@TrinketGoblinTV**\n"
            "🍯 Thank you for your support and kindness that keeps me running. Remember, you are never too much. 💛"
        )
        return

    if message.content.startswith("!bee-help"):
        await message.channel.send(
            "🐝✨ **BeeBot Commands:**\n\n"
            "`!ask [question]` : Ask BeeBot anything for mental health support or validation.\n"
            "`!venmo` : Get BeeBot's Venmo info to support development.\n"
            "`!bee-help` : Show this list of commands.\n"
            "`!bee-fact` : Hear a fun fact about bees 🐝.\n"
            "`!bee-support` : Receive mental health resources 🌻.\n"
            "`!bee-mood [your mood]` : Share your current mood and receive support.\n"
            "`!bee-gratitude [something you're grateful for]` – Share gratitude and positivity with the hive.\n"
            "`!bee-validate` : Receive a gentle compliment or validation message. 💛\n"
        )
        return

    if message.content.startswith("!bee-fact"):
        await message.channel.send(random.choice(BEE_FACTS))
        return

    if message.content.startswith("!bee-support"):
        await message.channel.send(
            "🌻 **Here are some mental health support resources:**\n\n"
            "• [988 Suicide & Crisis Lifeline (US)](https://988lifeline.org) – call or text 988 anytime\n"
            "• [Trans Lifeline](https://translifeline.org) – 877-565-8860 (US)\n"
            "• [International hotlines](https://findahelpline.com)\n\n"
            "🐝 Remember, reaching out for help is a brave and strong choice. You are never too much. 💛"
        )
        return

    if message.content.startswith("!bee-mood"):
        mood = message.content[len("!bee-mood "):].strip()
        if mood:
            await message.channel.send(
                f"🐝✨ Thank you for sharing your mood: **{mood}**.\n🍯 Sending you warmth and gentle support today, sweet human. 💛"
            )
        else:
            await message.channel.send("🐝 Please share your mood after the command, like `!bee-mood tired but hopeful`.")
        return

    if message.content.startswith("!bee-gratitude"):
        gratitude = message.content[len("!bee-gratitude "):].strip()
        if gratitude:
            await message.channel.send(
                f"🌻✨ Thank you for sharing your gratitude: **{gratitude}**.\n🐝 May your heart feel nourished by this sweetness today. 💛"
            )
        else:
            await message.channel.send("🐝 Please share what you're grateful for after the command, like `!bee-gratitude my friends and morning tea`.")
        return

    if message.content.startswith("!bee-validate"):
        try:
            prompt = (
                "Please create a short, warm, validating message for a user. "
                "Include bee-themed emojis naturally (🐝🍯🌻). "
                "Speak with compassion, avoid judgmental language, and remind them they are never 'too much'. "
                "Always phrase it uniquely and vary sentence structure to keep it fresh and supportive."
            )

            response = client_ai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": BEEBOT_PERSONALITY},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.9
            )
            ai_message = response.choices[0].message.content
            await message.channel.send(ai_message)

        except Exception as e:
            print(f"Error generating validation: {e}")
            # fallback to static validation
            validation = random.choice(BEE_VALIDATION)
            await message.channel.send(validation)
        return

client.run(DISCORD_TOKEN)
