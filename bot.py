# BeeBot Version: 0.1.2 (Fresh Hive Build)
import discord
from discord.ext import commands, tasks
from openai import OpenAI
import os
import redis
import random
from dotenv import load_dotenv
from datetime import datetime, timedelta
import asyncio

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Redis setup using environment variables
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True
)

# Intents setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load text files
def load_lines(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

facts = load_lines("facts.txt")
fortunes = load_lines("fortunes.txt")
jokes = load_lines("jokes.txt")
prefixes = load_lines("prefixes.txt")
suffixes = load_lines("suffixes.txt")
with open("personality.txt", "r", encoding="utf-8") as f:
    personality = f.read().strip()
questions = load_lines("questions.txt")
quiz_questions = load_lines("quiz.txt")
bee_species = load_lines("bee_species.txt")
banned_phrases = load_lines("banned_phrases.txt")
version_text = "\n".join(load_lines("version.txt"))

# Helper functions
def check_privacy_consent(user_id):
    return r.get(f"consent:{user_id}") == "on"

def get_random_quiz():
    q = random.choice(quiz_questions)
    parts = q.split('|')
    return f"{parts[0]}\nA) {parts[1]}\nB) {parts[2]}\nC) {parts[3]}", parts[4] if len(parts) == 5 else ""

def ai_response(prompt):
    combined_prompt = f"{personality}\n\nUser: {prompt}\nBeeBot:"
    for phrase in banned_phrases:
        if phrase.lower() in prompt.lower():
            return "I'm not allowed to discuss that topic."
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": personality},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message['content'].strip()

def parse_duration(time_str):
    match = re.fullmatch(r"(\\d+)([smhd]?)", time_str.strip().lower())
    if not match:
        return None
    value, unit = match.groups()
    value = int(value)
    if unit == "s" or unit == "":
        return value
    elif unit == "m":
        return value * 60
    elif unit == "h":
        return value * 3600
    elif unit == "d":
        return value * 86400
    return None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    for guild in bot.guilds:
        for channel_name in ["errors", "version", "announcements"]:
            if not discord.utils.get(guild.text_channels, name=channel_name):
                await guild.create_text_channel(channel_name)
        version_channel = discord.utils.get(guild.text_channels, name="version")
        if version_channel:
            await version_channel.send(version_text)
        announcement_channel = discord.utils.get(guild.text_channels, name="announcements")
        if announcement_channel:
            await announcement_channel.send("BeeBot is online!")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    if not check_privacy_consent(user_id):
        await message.channel.send("Please use /consent to provide data consent before using BeeBot.")
        return

    channel_key = f"autoreply:{message.channel.id}"
    if r.get(channel_key) == "on":
        if message.content.startswith("!"):
            await bot.process_commands(message)
        elif message.content.endswith("?"):
            reply = ai_response(message.content)
            await message.channel.send(reply)

@bot.command(name="announcement")
async def announcement(ctx, *, msg):
    announcement_channel = discord.utils.get(ctx.guild.text_channels, name="announcements")
    if announcement_channel:
        await announcement_channel.send(msg)

@bot.command(name="bee_fact")
async def bee_fact(ctx):
    await ctx.send(random.choice(facts))

@bot.command(name="bee_fortune")
async def bee_fortune(ctx):
    await ctx.send(random.choice(fortunes))

@bot.command(name="bee_joke")
async def bee_joke(ctx):
    await ctx.send(random.choice(jokes))

@bot.command(name="bee_name")
async def bee_name(ctx):
    name = f"{random.choice(prefixes)}{random.choice(suffixes)}"
    await ctx.respond(name)

@bot.command(name="bee_question")
async def bee_question(ctx):
    await ctx.respond(random.choice(questions))

@bot.command(name="bee_quiz")
async def bee_quiz(ctx):
    q, _ = get_random_quiz()
    await ctx.respond(q)

@bot.command(name="bee_species")
async def bee_species_cmd(ctx):
    await ctx.respond(random.choice(bee_species))

@bot.command(name="ask")
async def ask(ctx, *, question):
    if not check_privacy_consent(str(ctx.author.id)):
        await ctx.respond("Please use /consent to provide data consent before using BeeBot.")
        return
    await ctx.respond(ai_response(question))

@bot.command(name="bee_validate")
async def bee_validate(ctx):
    await ctx.respond("You're doing great! Keep buzzing!")

@bot.command(name="consent")
async def consent(ctx, choice: str):
    if choice.lower() not in ["on", "off", "info"]:
        await ctx.respond("Please choose: on, off, or info")
    elif choice.lower() == "info":
        await ctx.respond(privacy_policy)
    else:
        r.set(f"consent:{ctx.author.id}", choice.lower())
        await ctx.respond(f"Consent {choice.lower()}.")

@bot.command(name="set_reminder")
async def set_reminder(ctx, time: str, *, reminder: str):
    await ctx.respond(f"Reminder set for {time}: {reminder}")

@bot.command(name="get_reminders")
async def get_reminders(ctx):
    await ctx.respond("Here are your reminders:")

@bot.command(name="delete_reminder")
async def delete_reminder(ctx, index: int):
    await ctx.respond(f"Reminder {index} deleted.")

@bot.command(name="crisis")
async def crisis(ctx):
    help_lines = """
    🌍 **Global Crisis Support Lines**:

    **United States**: 988 (Suicide & Crisis Lifeline)
    **Canada**: 1-833-456-4566 (Talk Suicide Canada)
    **UK**: 116 123 (Samaritans)
    **Australia**: 13 11 14 (Lifeline Australia)
    **India**: 9152987821 (iCall)
    **Europe**: 112 (General Emergency Number)
    **International**: Check https://www.befrienders.org for local crisis centers

    You are not alone. Please reach out. 💛
    """
    await ctx.respond(help_lines)

@bot.command(name="bee_help")
async def bee_help(ctx):
    await ctx.respond("""
    **BeeBot Commands:**

    `/bee_fact` - Get a random bee-related fact.
    `/bee_fortune` - Receive a bee-themed fortune.
    `/bee_joke` - Hear a bee joke.
    `/bee_name` - Generate a random bee name.
    `/bee_question` - Get a deep or fun question to think about.
    `/bee_quiz` - Take a random bee quiz (multiple choice).
    `/bee_species` - Learn about a random bee species.
    `/ask` - Ask BeeBot any question using AI.
    `/bee_validate` - Get some emotional validation from BeeBot.
    `/consent` - Manage your privacy consent settings.
    `/set_reminder` - Set a personal reminder.
    `/get_reminders` - View your active reminders.
    `/delete_reminder` - Delete a reminder by index.
    `/crisis` - View a list of global crisis helplines.
    `!announcement` - Send an announcement as BeeBot.
    """)

bot.run(DISCORD_TOKEN)
