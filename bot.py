version = "3.1.0"

import os
import random
import json
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from openai import OpenAI
from dotenv import load_dotenv
import redis

# Load environment variables
load_dotenv()

# Init OpenAI with your API key
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Discord bot token
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Redis DB setup
db = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True
)

# Discord Intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
intents.dm_messages = True
intents.messages = True
intents.typing = False  # Optional
intents.message_content = True

# Create bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Memory and settings storage
guild_memory = {}
consent_cache = {}  # Guild-user consent pairs

def load_lines(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    return []

# Personality config
BEEBOT_PERSONALITY = """
You are BeeBot, a validating, kind, bee-themed support bot. You speak with compassion, warmth, and gentle encouragement.
Avoid judgment, use bee puns and emojis naturally, and never say anything from the "never say" list.
"""
def load_quiz_questions(filename):
    questions = []
    if not os.path.exists(filename):
        return questions

    with open(filename, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    for i in range(0, len(lines), 5):
        if i + 4 <= len(lines):
            question_line = lines[i]
            a = lines[i + 1]
            b = lines[i + 2]
            c = lines[i + 3]
            answer_line = lines[i + 4]

            if question_line.startswith("QUESTION:") and answer_line.startswith("ANSWER:"):
                questions.append({
                    "question": question_line[9:].strip(),
                    "options": [a, b, c],
                    "answer": answer_line[7:].strip()
                })

    return questions

BEEBOT_EXAMPLES = load_lines("beebot_examples.txt")
BEEBOT_NEVER_SAY = load_lines("beebot_never_say.txt")
BEE_FACTS = load_lines("bee_facts.txt")
BEE_QUESTIONS = load_lines("bee_questions.txt")
BEE_JOKES = load_lines("bee_jokes.txt")
BEE_NAME_PREFIXES = load_lines("bee_name_prefixes.txt")
BEE_NAME_SUFFIXES = load_lines("bee_name_suffixes.txt")
BEE_FORTUNES = load_lines("bee_fortunes.txt")
BEE_QUIZZES = load_quiz_questions("bee_quiz.txt")

### --- Redis-Based Settings Management ---

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

def save_settings(auto_reply_channels, announcement_channels, version_channels):
    for guild_id in auto_reply_channels:
        db.set(f"guild:{guild_id}:auto_reply_channels", json.dumps(list(auto_reply_channels[guild_id])))
        db.set(f"guild:{guild_id}:announcement_channel", announcement_channels.get(guild_id, 0))
        db.set(f"guild:{guild_id}:version_channel", version_channels.get(guild_id, 0))
    print("✅ Settings saved to Redis.")

settings = load_settings()
auto_reply_channels = settings["auto_reply_channels"]
announcement_channels = settings["announcement_channels"]
version_channels = settings["version_channels"]

### --- Consent System ---

def has_user_consented(guild_id: int, user_id: int) -> bool:
    key = f"consent:{guild_id}:{user_id}"
    return db.get(key) == "yes"

def set_user_consent(guild_id: int, user_id: int):
    key = f"consent:{guild_id}:{user_id}"
    db.set(key, "yes")

async def ensure_consent(interaction: discord.Interaction) -> bool:
    guild_id = interaction.guild.id
    user_id = interaction.user.id
    if has_user_consented(guild_id, user_id):
        return True

    # Prompt user for consent
    await interaction.response.send_message(
        "🐝 Before I can process your request, please consent to me sending your message to OpenAI (your message will be processed securely and not stored).\n\n"
        "Reply with `/consent` to agree.",
        ephemeral=True
    )
    return False

### --- Prompt Handling ---

def store_message_in_memory(guild_id, message, max_memory=20):
    if guild_id not in guild_memory:
        guild_memory[guild_id] = []
    guild_memory[guild_id].append({"role": "user", "content": message})
    guild_memory[guild_id] = guild_memory[guild_id][-max_memory:]

def build_prompt(user_input: str):
    return [
        {
            "role": "system",
            "content": BEEBOT_PERSONALITY + f"\n\nNever say:\n{chr(10).join(BEEBOT_NEVER_SAY)}"
        },
        {
            "role": "user",
            "content": f"Example: '{random.choice(BEEBOT_EXAMPLES)}'\n\nRespond to:\n{user_input}"
        }
    ]

async def handle_prompt(interaction: discord.Interaction, user_input: str):
    guild_id = interaction.guild.id
    user_id = interaction.user.id

    if not has_user_consented(guild_id, user_id):
        await ensure_consent(interaction)
        return

    try:
        messages = build_prompt(user_input)
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.8
        )
        await interaction.response.send_message(response.choices[0].message.content)
    except Exception as e:
        print(f"OpenAI Error: {e}")
        await interaction.response.send_message("⚠️ An error occurred.", ephemeral=True)

async def handle_prompt_raw(channel: discord.TextChannel, user_input: str, user_id: int, guild_id: int):
    if not has_user_consented(guild_id, user_id):
        try:
            user = await channel.guild.fetch_member(user_id)
            await user.send(
                "🐝 I need your consent before responding to your public message in a channel.\n"
                "Please type `/consent` in the server to allow me to reply."
            )
        except:
            print(f"❌ Couldn't send DM to user {user_id} for consent request.")
        return

    try:
        messages = build_prompt(user_input)
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.8
        )
        await channel.send(response.choices[0].message.content)
    except Exception as e:
        print(f"OpenAI Error: {e}")

### --- Slash Commands ---
@bot.tree.command(name="bee_quiz", description="Test your bee knowledge!")
async def bee_quiz(interaction: discord.Interaction):
    if not BEE_QUIZZES:
        await interaction.response.send_message("🐝 Hmm... I don't have any quizzes right now.", ephemeral=True)
        return

    q = random.choice(BEE_QUIZZES)
    formatted_options = "\n".join(q["options"])
    await interaction.response.send_message(
        f"🧠 **{q['question']}**\n\n{formatted_options}\n\n*(Answer: {q['answer']})*"
    )

@bot.tree.command(name="fortune", description="Get some validating buzzword messages for your day!")
async def fortune(interaction: discord.Interaction):
    if not BEE_FORTUNES:
        await interaction.response.send_message(
            "🐝 Hmm... I can’t think of any fortunes right now!", ephemeral=True
        )
        return

    selection = random.sample(BEE_FORTUNES, min(4, len(BEE_FORTUNES)))
    response = "🌼 Your fortunes today are:\n" + "\n".join(f"*{line}*" for line in selection)
    await interaction.response.send_message(response)

@bot.tree.command(name="bee_match", description="Find your bee buddy match!")
async def bee_match(interaction: discord.Interaction):
    members = [
        m for m in interaction.guild.members
        if not m.bot and m != interaction.user
    ]

    if not members:
        await interaction.response.send_message("🐝 Hmm... no one to match you with right now!", ephemeral=True)
        return

    match = random.choice(members)
    compatibility = random.randint(25, 100)

    await interaction.response.send_message(
        f"💛 You and {match.mention} have a **{compatibility}%** pollen-ship compatibility! 🐝✨"
    )

@bot.tree.command(name="bee_name", description="Get a cute bee-themed nickname!")
async def bee_name(interaction: discord.Interaction):
    if not BEE_NAME_PREFIXES or not BEE_NAME_SUFFIXES:
        await interaction.response.send_message("🐝 Hmm... I can't come up with a bee name right now!", ephemeral=True)
        return

    name = random.choice(BEE_NAME_PREFIXES) + random.choice(BEE_NAME_SUFFIXES)
    await interaction.response.send_message(f"🐝 Your bee name is: **{name}**!")

@bot.tree.command(name="consent", description="Give BeeBot permission to send your messages to OpenAI.")
async def consent(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    user_id = interaction.user.id
    set_user_consent(guild_id, user_id)
    await interaction.response.send_message(
        "🐝 Thanks for consenting! I’ll now be able to process your requests safely and respectfully. 💛",
        ephemeral=True
    )

@bot.tree.command(name="bee_help", description="List BeeBot commands.")
async def bee_help(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🐝✨ **BeeBot Slash Commands:**\n\n"
        "**Support & Wellbeing**\n"
        "/ask [question] – Ask BeeBot anything\n"
        "/bee_validate – Get a validating compliment 💛\n"
        "/bee_support – Mental health resources\n"
        "/crisis [country] – Get a crisis line\n"
        "/bee_mood [text] – Share your mood\n"
        "/bee_gratitude [text] – Share something you're grateful for\n"
        "/consent – Grant permission for BeeBot to reply using OpenAI\n\n"
        "**Fun & Encouragement**\n"
        "/bee_fact – Get a fun bee fact 🐝\n"
        "/bee_question – Reflective prompt for the hive\n"
        "/buzzwords – Get 4 validating affirmations 📝\n"
        "/bee_joke – Hear a bee-themed joke 😄\n"
        "/bee_name – Get a fun bee-themed nickname 🎉\n"
        "/bee_match – Match with another bee buddy 🐝💛\n"
        "/bee_quiz – Test your bee knowledge 📚\n"
        "**Setup & Admin**\n"
        "/set_autoreply [channel] [on/off] – Enable or disable auto-replies\n"
        "/bee_autoreply [on/off] – Toggle auto-reply in the current channel\n"
        "/set_announcement_channel – Set a channel for announcements 📢\n"
        "/set_version_channel – Set a channel for version updates 🆕\n"
        "/announcement [message] – Send a formatted announcement (requires 'Announcement' role)\n\n"
        "🌻 Need help? Just buzz! I'm always here to support you. 💛"
    )

@bot.tree.command(name="bee_support", description="Get mental health resources.")
async def bee_support(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🌻 **Mental health resources:**\n\n"
        "• [988 Lifeline (US)](https://988lifeline.org)\n"
        "• [Trans Lifeline](https://translifeline.org) – 877-565-8860\n"
        "• [International Support](https://findahelpline.com)\n\n"
        "🐝 You're not alone. 💛"
    )

@bot.tree.command(name="bee_fact", description="Get a fun bee fact!")
async def bee_fact(interaction: discord.Interaction):
    fact = random.choice(BEE_FACTS) if BEE_FACTS else "🐝 Bees are amazing!"
    await interaction.response.send_message(fact)

@bot.tree.command(name="bee_question", description="Get everyone's experiences with different things.")
async def bee_question(interaction: discord.Interaction):
    question = random.choice(BEE_QUESTIONS) if BEE_QUESTIONS else "🐝 Hmm... I can't think of a question, but I love yours!"
    await interaction.response.send_message(question)

@bot.tree.command(name="bee_validate", description="Get a validating compliment.")
async def bee_validate(interaction: discord.Interaction):
    await handle_prompt(interaction, "Give me a validating compliment with bee puns and emojis.")

@bot.tree.command(name="bee_mood", description="Share your mood with BeeBot.")
async def bee_mood(interaction: discord.Interaction, mood: str):
    await handle_prompt(interaction, f"My mood is: {mood}")

@bot.tree.command(name="bee_gratitude", description="Share something you're grateful for.")
async def bee_gratitude(interaction: discord.Interaction, gratitude: str):
    await handle_prompt(interaction, f"I'm grateful for: {gratitude}")

@bot.tree.command(name="ask", description="Ask BeeBot a question.")
async def ask(interaction: discord.Interaction, question: str):
    await handle_prompt(interaction, question)

# Crisis Line Command
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
    return [choice for choice in CRISIS_CHOICES if current in choice.name.lower() or current in choice.value.lower()][:25]

@bot.tree.command(name="crisis", description="Get a crisis line for your country.")
@app_commands.describe(country="Choose a country or 'all'")
@app_commands.autocomplete(country=crisis_autocomplete)
async def crisis(interaction: discord.Interaction, country: str):
    lines = {
        "us": "🇺🇸 **US**: 988",
        "uk": "🇬🇧 **UK**: 116 123 (Samaritans)",
        "canada": "🇨🇦 **Canada**: 1-833-456-4566",
        "australia": "🇦🇺 **Australia**: 13 11 14",
        "global": "🌐 **Global**: https://www.befrienders.org/"
    }

    country = country.lower()
    if country == "all":
        msg = "💛 Please reach out to a professional crisis line:\n\n" + "\n".join(lines.values())
    elif country in lines:
        msg = f"💛 You're not alone. Here's help:\n{lines[country]}"
    else:
        msg = (
            "⚠️ I don't recognize that country. Try one of these:\n"
            "`us`, `uk`, `canada`, `australia`, `global`, or `all`"
        )

    await interaction.response.send_message(msg)

@bot.tree.command(name="bee_autoreply", description="Toggle BeeBot autoreply in this channel.")
async def bee_autoreply(interaction: discord.Interaction, mode: str):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("🚫 You need `Manage Channels` permission.", ephemeral=True)
        return

    guild_id = interaction.guild.id
    channel_id = interaction.channel.id

    if mode.lower() == "on":
        auto_reply_channels.setdefault(guild_id, set()).add(channel_id)
        save_settings(auto_reply_channels, announcement_channels, version_channels)
        await interaction.response.send_message("✅ Auto-reply enabled in this channel! 🐝")
    elif mode.lower() == "off":
        if guild_id in auto_reply_channels and channel_id in auto_reply_channels[guild_id]:
            auto_reply_channels[guild_id].remove(channel_id)
            if not auto_reply_channels[guild_id]:
                del auto_reply_channels[guild_id]
            save_settings(auto_reply_channels, announcement_channels, version_channels)
        await interaction.response.send_message("❌ Auto-reply disabled.")
    else:
        await interaction.response.send_message("❗ Use `/bee_autoreply on` or `/bee_autoreply off`", ephemeral=True)

@bot.tree.command(name="set_autoreply", description="Enable or disable auto-reply for a specific channel (text or forum).")
@app_commands.describe(channel="The channel (text or forum)", mode="on or off")
async def set_autoreply(interaction: discord.Interaction, channel: discord.abc.GuildChannel, mode: str):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("🚫 You need `Manage Channels` permission.", ephemeral=True)
        return

    if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
        await interaction.response.send_message("⚠️ Only text or forum channels are supported.", ephemeral=True)
        return

    guild_id = interaction.guild.id
    channel_id = channel.id

    if mode.lower() == "on":
        auto_reply_channels.setdefault(guild_id, set()).add(channel_id)
        save_settings(auto_reply_channels, announcement_channels, version_channels)
        await interaction.response.send_message(f"✅ Auto-reply enabled for {channel.mention} (type: {channel.type.name})")
    elif mode.lower() == "off":
        if guild_id in auto_reply_channels and channel_id in auto_reply_channels[guild_id]:
            auto_reply_channels[guild_id].remove(channel_id)
            if not auto_reply_channels[guild_id]:
                del auto_reply_channels[guild_id]
            save_settings(auto_reply_channels, announcement_channels, version_channels)
        await interaction.response.send_message(f"❌ Auto-reply disabled for {channel.mention}")
    else:
        await interaction.response.send_message("❗ Use 'on' or 'off'", ephemeral=True)

@bot.tree.command(name="set_version_channel", description="Set the channel for version updates.")
async def set_version_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("🚫 You need `Manage Channels` permission.", ephemeral=True)
        return

    version_channels[interaction.guild.id] = interaction.channel.id
    save_settings(auto_reply_channels, announcement_channels, version_channels)
    await interaction.response.send_message(f"✅ Version updates will post in {interaction.channel.mention}")

@bot.tree.command(name="set_announcement_channel", description="Set the channel for announcements.")
async def set_announcement_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("🚫 You need `Manage Channels` permission.", ephemeral=True)
        return

    announcement_channels[interaction.guild.id] = interaction.channel.id
    save_settings(auto_reply_channels, announcement_channels, version_channels)
    await interaction.response.send_message(f"✅ Announcements will post in {interaction.channel.mention}")

@bot.tree.command(name="bee_joke", description="Get a fun bee-themed joke!")
async def bee_joke(interaction: discord.Interaction):
    if BEE_JOKES:
        joke = random.choice(BEE_JOKES)
    else:
        joke = "🐝 Hmm... I couldn’t think of a joke, but I hope you’re smiling anyway!"
    await interaction.response.send_message(joke)

@bot.tree.command(name="announcement", description="Send an announcement to the configured announcement channel.")
@app_commands.describe(message="The announcement message to send.")
async def announcement(interaction: discord.Interaction, message: str):
    guild_id = interaction.guild.id
    announcement_channel_id = announcement_channels.get(guild_id)
    announcement_role = discord.utils.get(interaction.guild.roles, name="Announcement")

    if not announcement_role or announcement_role not in interaction.user.roles:
        await interaction.response.send_message("🚫 You need the Announcement role to use this command.", ephemeral=True)
        return

    if not announcement_channel_id:
        await interaction.response.send_message("⚠️ No announcement channel set for this server.", ephemeral=True)
        return

    channel = interaction.guild.get_channel(announcement_channel_id)
    if not channel:
        await interaction.response.send_message("⚠️ Announcement channel not found.", ephemeral=True)
        return

    await channel.send(message)
    await interaction.response.send_message(f"✅ Announcement sent to {channel.mention}", ephemeral=True)

@bot.event
async def on_guild_join(guild):
    for role_name in ["Beebot", "Announcement"]:
        if not discord.utils.get(guild.roles, name=role_name):
            try:
                await guild.create_role(name=role_name)
            except Exception as e:
                print(f"Error creating role '{role_name}': {e}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    guild_id = message.guild.id
    channel_id = message.channel.id

    if guild_id in auto_reply_channels and channel_id in auto_reply_channels[guild_id]:
        if message.channel.type != discord.ChannelType.forum:
            await handle_prompt_raw(message.channel, message.content, message.author.id, guild_id)

@bot.event
async def on_thread_create(thread):
    try:
        print(f"🧵 Thread created: {thread.name} (ID: {thread.id}) in guild: {thread.guild.name}")

        if getattr(thread.parent, "type", None) != discord.ChannelType.forum:
            print(f"🔕 Skipped: Thread parent is not a forum (Type: {thread.parent.type})")
            return

        guild_id = thread.guild.id
        forum_channel_id = thread.parent.id

        print(f"🔍 Checking if auto-reply is enabled for: {thread.parent.name} (ID: {forum_channel_id})")
        if forum_channel_id not in auto_reply_channels.get(guild_id, set()):
            print(f"❌ Auto-reply not enabled for {thread.parent.name}")
            return

        await thread.join()
        print("✅ Joined thread successfully")

        await asyncio.sleep(1)

        # Collect recent messages
        messages = []
        print("📥 Collecting thread messages...")
        async for msg in thread.history(limit=10, oldest_first=True):
            if msg.content.strip():
                messages.append(f"{msg.author.display_name}: {msg.content.strip()}")

        if not messages:
            print(f"❌ No message content found in thread: {thread.name}")
            return

        convo = "\n".join(messages)
        print(f"📝 Collected conversation:\n{convo}")

        # Get thread starter
        thread_starter = thread.owner
        if not thread_starter:
            async for msg in thread.history(limit=1, oldest_first=True):
                thread_starter = msg.author
                break

        if not thread_starter:
            print(f"⚠️ Unable to determine thread starter.")
            return

        user_id = thread_starter.id
        user_mention = thread_starter.mention
        print(f"👤 Thread starter: {thread_starter.display_name} (ID: {user_id})")

        if not has_user_consented(guild_id, user_id):
            print(f"🔒 User {user_id} has not given consent.")
            await thread.send(
                f"{user_mention} 🐝 I’d love to help, but I need your permission first.\n"
                f"Please type `/consent` in the server. 💛"
            )
            return

        # Build and send prompt to OpenAI
        prompt = (
            f"A user started a thread titled:\n"
            f"**{thread.name}**\n\n"
            f"Conversation so far:\n{convo}\n\n"
            f"Reply with warmth, bee puns, emojis, and kindness. Validate the user's feelings."
        )

        print("🤖 Sending prompt to OpenAI...")
        messages_for_openai = build_prompt(prompt)
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages_for_openai,
            temperature=0.8
        )

        reply_text = f"{user_mention} 🐝\n\n" + response.choices[0].message.content
        await thread.send(reply_text)
        print(f"✅ Responded in thread: {thread.name}")

    except Exception as e:
        print(f"🐛 Error in thread handler: {e}")

### --- Version Handling ---

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
    print(f"✅ Logged in as {bot.user} and synced slash commands.")

    version, description = read_version_info()
    if not version:
        return

    version_msg = f"🐝 **BeeBot {version}**\n{description}"
    for guild in bot.guilds:
        channel_id = version_channels.get(guild.id)
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(version_msg)
                except Exception as e:
                    print(f"❌ Couldn't post version in {guild.name}: {e}")

# Run the bot
bot.run(DISCORD_TOKEN)
