import discord
from openai import OpenAI

client = OpenAI(api_key=OPENAI_API_KEY)
import os
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# Define Discord intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True  # Needed for forum posts and channel management
intents.dm_messages = True

# Create Discord client
client = discord.Client(intents=intents)

# BeeBot's system prompt/personality
BEEBOT_PERSONALITY = """
You are BeeBot, an AI with a warm, validating, and gently educational personality who loves bee puns.
Speak with compassion, avoid judgmental language, and remind users they are never 'too much.'
Use bee-themed emojis naturally (🐝🍯🌻) and provide concise mental health information and resources when relevant.
"""

# Sample bee facts
BEE_FACTS = [
    "🐝 Did you know? Bees communicate through dances to share where flowers are found!",
    "🍯 Bees have five eyes, two large ones and three tiny ones on top of their heads!",
    "🌻 Honey never spoils. Archaeologists found honey in ancient Egyptian tombs that is still edible today!",
    "🐝 A single bee can visit 5,000 flowers in a day while collecting nectar.",
    "🍯 Bees are essential pollinators, supporting over a third of the food we eat!"
]

# Compliments and validation messages
BEE_VALIDATION = [
    "🐝✨ You are such a bright and gentle soul, and the world is sweeter with you in it. 💛",
    "🍯 You are doing so well, even on days you doubt yourself. Your effort matters, and so do you. 🌻",
    "🐝 You carry so much wisdom and beauty within you. Please don’t ever forget how deeply loved you are. 💛",
    "🌻 Your existence brings warmth and light to those around you, like the sun nourishing flowers. 🍯",
    "🐝 Even when you feel unseen, I see your strength, courage, and kindness shining brightly. 💛",
    "🍯 You are never too much. Your feelings, your needs, your hopes – all are welcome here. 🌻",
    "🐝 You deserve rest, peace, and moments of gentle sweetness. Please be kind to yourself today. 💛",
    "You are doing your best, and that's truly amazing. 🌟",
    "Your feelings are valid, and it's okay to take care of yourself. 🌻",
    "You are worthy of love and kindness, always. 🐝",
    "It's okay to not be okay. Remember, you are not alone. 🧡",
    "Your journey is unique and important. Keep moving forward at your own pace. 🌿",
    "Your worth is not based on productivity. Rest if you need to. 💛",
    "You are enough just as you are. Don't be too hard on yourself. 🌼",
    "Your emotions matter, and it's okay to express them. 🌈",
    "You are worthy of compassion and understanding. Be gentle with yourself. 💖",
    "You are a work in progress, and that's perfectly okay. 🌸"
]

# Utility function to get or create error log channel
async def get_or_create_error_channel(guild):
    channel_name = "beebot-errors"
    for channel in guild.text_channels:
        if channel.name == channel_name:
            return channel
    # Channel does not exist, create it
    try:
        return await guild.create_text_channel(channel_name)
    except Exception as e:
        print(f"Failed to create error channel: {e}")
        return None

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord! 🐝✨')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # !venmo command
    if message.content.startswith("!venmo"):
        venmo_message = (
            "🐝✨ Here is my Venmo info, sweet human:\n\n"
            "**@TrinketGoblinTV**\n"
            "🍯 Thank you for your support and kindness that keeps me running. Remember, you are never too much. 💛"
        )
        await message.channel.send(venmo_message)
        return

    # !bee-help command
    if message.content.startswith("!bee-help"):
        help_message = (
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
        await message.channel.send(help_message)
        return

    # !bee-fact command
    if message.content.startswith("!bee-fact"):
        fact = random.choice(BEE_FACTS)
        await message.channel.send(fact)
        return

    # !bee-support command
    if message.content.startswith("!bee-support"):
        support_message = (
            "🌻 **Here are some mental health support resources:**\n\n"
            "• [988 Suicide & Crisis Lifeline (US)](https://988lifeline.org) – call or text 988 anytime\n"
            "• [Trans Lifeline](https://translifeline.org) – 877-565-8860 (US)\n"
            "• [International hotlines](https://findahelpline.com)\n\n"
            "🐝 Remember, reaching out for help is a brave and strong choice. You are never too much. 💛"
        )
        await message.channel.send(support_message)
        return

    # !bee-mood command
    if message.content.startswith("!bee-mood"):
        mood = message.content[len("!bee-mood "):].strip()
        if mood:
            response = f"🐝✨ Thank you for sharing your mood: **{mood}**.\n🍯 Sending you warmth and gentle support today, sweet human. 💛"
        else:
            response = "🐝 Please share your mood after the command, like `!bee-mood tired but hopeful`."
        await message.channel.send(response)
        return

    # !bee-gratitude command
    if message.content.startswith("!bee-gratitude"):
        gratitude = message.content[len("!bee-gratitude "):].strip()
        if gratitude:
            response = f"🌻✨ Thank you for sharing your gratitude: **{gratitude}**.\n🐝 May your heart feel nourished by this sweetness today. 💛"
        else:
            response = "🐝 Please share what you're grateful for after the command, like `!bee-gratitude my friends and morning tea`."
        await message.channel.send(response)
        return

    # !bee-validate command
    if message.content.startswith("!bee-validate"):
        validation = random.choice(BEE_VALIDATION)
        await message.channel.send(validation)
        return

    # If message is in a DM
    if isinstance(message.channel, discord.DMChannel):
        prompt = message.content.strip()

    # Or if message is in a guild and starts with !ask
    elif message.content.startswith("!ask"):
        prompt = message.content[len("!ask "):].strip()

    else:
        return  # Ignore other messages

    try:
        response = client.chat.completions.create(model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": BEEBOT_PERSONALITY
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7)
        await message.channel.send(response.choices[0].message.content)

    except Exception as e:
        print(f"Error: {e}")
        if message.guild:
            error_channel = await get_or_create_error_channel(message.guild)
            if error_channel:
                await error_channel.send(f"🐝 **BeeBot Error:** `{e}`")

@client.event
async def on_thread_create(thread):
    try:
        # Fetch the first message in the thread (forum post)
        messages = [message async for message in thread.history(limit=1)]
        first_post_content = messages[0].content if messages else "No content provided."

        # Combine thread title and post content into the prompt
        prompt = (
            f"A user has created a new forum thread titled '{thread.name}' with the following post:\n\n"
            f"{first_post_content}\n\n"
            "Please greet them warmly with BeeBot's validating style, mention bee-themed emojis, and invite them to share more if they wish."
        )

        response = client.chat.completions.create(model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": BEEBOT_PERSONALITY
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7)
        ai_message = response.choices[0].message.content

        await thread.send(ai_message)

    except Exception as e:
        print(f"Error sending AI reply to thread: {e}")
        if thread.guild:
            error_channel = await get_or_create_error_channel(thread.guild)
            if error_channel:
                await error_channel.send(f"🐝 **BeeBot Thread Error:** `{e}`")

client.run(DISCORD_TOKEN)
