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

# In-memory guild context store
guild_memory = {}

def store_message_in_memory(guild_id, message_content, max_memory=10):
    if guild_id not in guild_memory:
        guild_memory[guild_id] = []
    guild_memory[guild_id].append({"role": "user", "content": message_content})

    # Keep only the last 'max_memory' messages
    if len(guild_memory[guild_id]) > max_memory:
        guild_memory[guild_id] = guild_memory[guild_id][-max_memory:]

def fetch_memory_for_guild(guild_id):
    return guild_memory.get(guild_id, [])

# Utility function to get or create error log channel
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

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord! 🐝✨')

@client.event
async def on_guild_join(guild):
    # Create Beebot role
    existing_role = discord.utils.get(guild.roles, name="Beebot")
    if not existing_role:
        try:
            beebot_role = await guild.create_role(
                name="Beebot",
                permissions=discord.Permissions(
                    send_messages=True,
                    read_messages=True,
                    read_message_history=True,
                    embed_links=True,
                    attach_files=True,
                    use_external_emojis=True,
                    add_reactions=True,
                    view_channel=True,
                    manage_roles=True,
                    manage_channels=True,
                    manage_threads=True
                ),
                reason="Beebot setup role with necessary permissions"
            )
            print(f"Created role 'Beebot' in {guild.name}")
        except Exception as e:
            print(f"Failed to create Beebot role in {guild.name}: {e}")
            beebot_role = None
    else:
        beebot_role = existing_role
        print(f"Beebot role already exists in {guild.name}")

    # Assign role to BeeBot user
    if beebot_role:
        bot_member = guild.get_member(client.user.id)
        if bot_member:
            try:
                await bot_member.add_roles(beebot_role, reason="Assigning Beebot role to itself")
                print(f"Assigned Beebot role to {client.user.name} in {guild.name}")
            except Exception as e:
                print(f"Failed to assign Beebot role to bot user in {guild.name}: {e}")
        else:
            print(f"Could not find bot member in {guild.name}")

    # Create beebot-🐝 channel
    channel_name = "beebot-🐝"
    existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
    if not existing_channel:
        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            await guild.create_text_channel(channel_name, overwrites=overwrites, reason="Beebot main channel")
            print(f"Created channel '{channel_name}' in {guild.name}")
        except Exception as e:
            print(f"Failed to create channel {channel_name} in {guild.name}: {e}")
    else:
        print(f"Channel '{channel_name}' already exists in {guild.name}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Command handlers
    if message.content.startswith("!venmo"):
        venmo_message = (
            "🐝✨ Here is my Venmo info, sweet human:\n\n"
            "**@TrinketGoblinTV**\n"
            "🍯 Thank you for your support and kindness that keeps me running. Remember, you are never too much. 💛"
        )
        await message.channel.send(venmo_message)
        return

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

    if message.content.startswith("!bee-fact"):
        fact = random.choice(BEE_FACTS)
        await message.channel.send(fact)
        return

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

    if message.content.startswith("!bee-mood"):
        mood = message.content[len("!bee-mood "):].strip()
        if mood:
            response = f"🐝✨ Thank you for sharing your mood: **{mood}**.\n🍯 Sending you warmth and gentle support today, sweet human. 💛"
        else:
            response = "🐝 Please share your mood after the command, like `!bee-mood tired but hopeful`."
        await message.channel.send(response)
        return

    if message.content.startswith("!bee-gratitude"):
        gratitude = message.content[len("!bee-gratitude "):].strip()
        if gratitude:
            response = f"🌻✨ Thank you for sharing your gratitude: **{gratitude}**.\n🐝 May your heart feel nourished by this sweetness today. 💛"
        else:
            response = "🐝 Please share what you're grateful for after the command, like `!bee-gratitude my friends and morning tea`."
        await message.channel.send(response)
        return

    if message.content.startswith("!bee-validate"):
        prompt_messages = [
            {"role": "system", "content": BEEBOT_PERSONALITY},
            {"role": "user", "content": "Please give me a warm, validating compliment or message, as BeeBot would say, including bee puns and emojis naturally."}
        ]
        try:
            response = client_ai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=prompt_messages,
                temperature=0.8
            )
            await message.channel.send(response.choices[0].message.content)
        except Exception as e:
            print(f"Error: {e}")
            if message.guild:
                error_channel = await get_or_create_error_channel(message.guild)
                if error_channel:
                    await error_channel.send(f"🐝 **BeeBot Error:** `{e}`")
        return

    # Handling messages in 'beebot-🐝' channel, DMs, or with !ask command
    if isinstance(message.channel, discord.DMChannel):
        prompt = message.content.strip()
        prompt_messages = [
            {"role": "system", "content": BEEBOT_PERSONALITY},
            {"role": "user", "content": prompt}
        ]
    else:
        guild_id = str(message.guild.id)
        channel_name = message.channel.name

        if channel_name == "beebot-🐝":
            prompt = message.content.strip()

            store_message_in_memory(guild_id, prompt)
            context = fetch_memory_for_guild(guild_id)

            prompt_messages = [
                {"role": "system", "content": BEEBOT_PERSONALITY},
                *context,
                {"role": "user", "content": prompt}
            ]
        elif message.content.startswith("!ask"):
            prompt = message.content[len("!ask "):].strip()

            store_message_in_memory(guild_id, prompt)
            context = fetch_memory_for_guild(guild_id)

            prompt_messages = [
                {"role": "system", "content": BEEBOT_PERSONALITY},
                *context,
                {"role": "user", "content": prompt}
            ]
        else:
            return

    # OpenAI API call
    try:
        response = client_ai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=prompt_messages,
            temperature=0.8
        )
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
        messages = [message async for message in thread.history(limit=1)]
        first_post_content = messages[0].content if messages else "No content provided."

        prompt = (
            f"A user has created a new forum thread titled '{thread.name}' with the following post:\n\n"
            f"{first_post_content}\n\n"
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

        await thread.send(ai_message)

    except Exception as e:
        print(f"Error sending AI reply to thread: {e}")
        if thread.guild:
            error_channel = await get_or_create_error_channel(thread.guild)
            if error_channel:
                await error_channel.send(f"🐝 **BeeBot Thread Error:** `{e}`")

client.run(DISCORD_TOKEN)
