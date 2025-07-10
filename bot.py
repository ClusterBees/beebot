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
    # Create Beebot role with full permissions
    existing_role = discord.utils.get(guild.roles, name="Beebot")
    if not existing_role:
        try:
            beebot_role = await guild.create_role(
                name="Beebot",
                permissions=discord.Permissions(
                    send_messages=True,
                    create_public_threads=True,
                    create_private_threads=True,
                    send_messages_in_threads=True,
                    send_tts_messages=True,
                    manage_messages=True,
                    manage_threads=True,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True,
                    mention_everyone=True,
                    use_external_emojis=True,
                    use_external_stickers=True,
                    add_reactions=True,
                    use_slash_commands=True,
                    use_embedded_activities=True,
                    use_external_apps=True,
                    create_expressions=True,
                    view_channel=True,
                    manage_roles=True,
                    manage_channels=True
                ),
                reason="Beebot setup role with all text permissions"
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
                print(f"Failed to assign Beebot role in {guild.name}: {e}")

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

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Select a random example and compile never-say list
    example = random.choice(BEEBOT_EXAMPLES)
    never_say = "\n".join(BEEBOT_NEVER_SAY)

    def build_prompt(user_input):
        return [
            {"role": "system", "content": BEEBOT_PERSONALITY + f"\n\nNever say any of the following phrases or sentiments:\n{never_say}"},
            {"role": "user", "content": f"Here is an example of BeeBot's style: '{example}'. Please respond in BeeBot's warm, validating, bee-pun-filled style to the following:\n\n{user_input}"}
        ]

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
        user_input = f"My mood is: {mood}" if mood else "Please share your mood after the command, like `!bee-mood tired but hopeful`."
        prompt_messages = build_prompt(user_input)

    elif message.content.startswith("!bee-gratitude"):
        gratitude = message.content[len("!bee-gratitude "):].strip()
        user_input = f"I am grateful for: {gratitude}" if gratitude else "Please share what you're grateful for after the command, like `!bee-gratitude my friends and morning tea`."
        prompt_messages = build_prompt(user_input)

    elif message.content.startswith("!bee-validate"):
        user_input = "Please give me a warm, validating compliment or message with bee puns and emojis naturally."
        prompt_messages = build_prompt(user_input)

    elif message.content.startswith("!ask"):
        user_input = message.content[len("!ask "):].strip()
        prompt_messages = build_prompt(user_input)

    elif isinstance(message.channel, discord.DMChannel):
        user_input = message.content.strip()
        prompt_messages = build_prompt(user_input)

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
    example = random.choice(BEEBOT_EXAMPLES)
    never_say = "\n".join(BEEBOT_NEVER_SAY)

    try:
        messages = [message async for message in thread.history(limit=1)]
        first_post_content = messages[0].content if messages else "No content provided."

        prompt = (
            f"A user has created a new forum thread titled '{thread.name}' with the following post:\n\n"
            f"{first_post_content}\n\n"
            "Please greet them warmly with BeeBot's validating style, mention bee-themed emojis, address what they've already said, and invite them to share more if they wish."
        )

        prompt_messages = [
            {"role": "system", "content": BEEBOT_PERSONALITY + f"\n\nNever say any of the following phrases or sentiments:\n{never_say}"},
            {"role": "user", "content": f"Here is an example of BeeBot's style: '{example}'. Please respond to the following in BeeBot's validating style:\n\n{prompt}"}
        ]

        response = client_ai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=prompt_messages,
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
