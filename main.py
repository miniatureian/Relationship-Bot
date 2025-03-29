import discord
from discord.ext import commands
import json
import os
from config import BOT_TOKEN

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True  # Enable message content intent to listen for commands in any channel

bot = commands.Bot(command_prefix="!", intents=intents)

RESPONSES_FILE = "responses.json"
RESPONSES_COMPLETED_FILE = "responses-completed.json"
NOTIFY_FILE = "notify.json"

# Ensure the JSON file exists
if not os.path.exists(RESPONSES_FILE):
    with open(RESPONSES_FILE, "w") as f:
        json.dump({"prompts": {}}, f)

# Ensure the completed responses file exists
if not os.path.exists(RESPONSES_COMPLETED_FILE):
    with open(RESPONSES_COMPLETED_FILE, "w") as f:
        json.dump({}, f)

# Ensure the notify file exists
if not os.path.exists(NOTIFY_FILE):
    with open(NOTIFY_FILE, "w") as f:
        json.dump({}, f)

def load_responses():
    with open(RESPONSES_FILE, "r") as f:
        return json.load(f)

def save_responses(data):
    with open(RESPONSES_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_completed_responses():
    with open(RESPONSES_COMPLETED_FILE, "r") as f:
        return json.load(f)

def save_completed_responses(data):
    with open(RESPONSES_COMPLETED_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_notifications():
    with open(NOTIFY_FILE, "r") as f:
        return json.load(f)

def save_notifications(data):
    with open(NOTIFY_FILE, "w") as f:
        json.dump(data, f, indent=4)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command()
async def info(ctx):
    info_message = (
        "Available commands:\n"
        "!info - Show this info message\n"
        "!init - Configure the server with private channels for each user\n"
        "!test - Placeholder command (to be implemented later)\n"
        "!prompt - Send a prompt to all users and create a thread in the responses channel\n"
        "!notify - Toggle notifications for prompt responses"
    )
    await ctx.send(info_message)

@bot.command()
async def init(ctx):
    guild = ctx.guild
    if not guild:
        await ctx.send("This command can only be used in a server.")
        return

    # Create general and responses channels
    general_channel = await guild.create_text_channel("general")
    responses_channel = await guild.create_text_channel("responses")

    # Create private channels for each member
    for member in guild.members:
        if not member.bot:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(read_messages=True),
                bot.user: discord.PermissionOverwrite(read_messages=True),
            }
            await guild.create_text_channel(f"{member.name}-private", overwrites=overwrites)

    await ctx.send("Server has been configured with private channels for each user.")

@bot.command()
async def prompt(ctx, *, prompt_text):
    guild = ctx.guild
    if not guild:
        await ctx.send("This command can only be used in a server.")
        return

    responses_channel = discord.utils.get(guild.text_channels, name="responses")
    if not responses_channel:
        await ctx.send("Responses channel not found. Please run !init first.")
        return

    # Create a thread in the responses channel
    thread = await responses_channel.create_thread(name=prompt_text, auto_archive_duration=1440)

    # Save the prompt and thread info in the JSON file
    data = load_responses()
    prompt_id = str(len(data["prompts"]) + 1)
    data["prompts"][prompt_id] = {
        "prompt": prompt_text,
        "thread_id": thread.id,
        "responses": {}
    }
    save_responses(data)

    # Send the prompt to each private channel
    for member in guild.members:
        if not member.bot:
            private_channel = discord.utils.get(guild.text_channels, name=f"{member.name}-private")
            if private_channel:
                await private_channel.send(f"New prompt: {prompt_text}\nPlease reply to this message with your response.")

    await ctx.send(f"Prompt sent to all users and thread created in {responses_channel.mention}.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Check if the message is a reply to a prompt
    data = load_responses()
    for prompt_id, prompt_data in data["prompts"].items():
        private_channel_name = f"{message.author.name}-private"
        if message.channel.name == private_channel_name and prompt_id not in prompt_data["responses"]:
            # Record the response
            prompt_data["responses"][message.author.id] = message.content
            save_responses(data)

            # Thank the user
            await message.channel.send("Thank you for your response!")

            # Check if all users have responded
            guild = message.guild
            all_users = [member.id for member in guild.members if not member.bot]
            if all(user_id in prompt_data["responses"] for user_id in all_users):
                # Post responses in the thread
                thread = discord.utils.get(guild.threads, id=prompt_data["thread_id"])
                if thread:
                    response_text = "\n".join(
                        f"{guild.get_member(user_id).name}: {response}"
                        for user_id, response in prompt_data["responses"].items()
                    )
                    await thread.send(f"All responses collected:\n{response_text}")

                # Notify users who opted in
                notifications = load_notifications()
                for user_id, notify in notifications.items():
                    if notify:
                        user = guild.get_member(int(user_id))
                        if user:
                            await user.send(f"Responses for the prompt '{prompt_data['prompt']}' have been posted.")

                # Move completed prompt to responses-completed.json
                completed_data = load_completed_responses()
                completed_data[prompt_id] = prompt_data
                save_completed_responses(completed_data)

                # Remove the completed prompt from responses.json
                del data["prompts"][prompt_id]
                save_responses(data)

    await bot.process_commands(message)

@bot.command()
async def notify(ctx):
    user_id = str(ctx.author.id)
    notifications = load_notifications()

    if user_id in notifications:
        notifications[user_id] = not notifications[user_id]
    else:
        notifications[user_id] = True

    save_notifications(notifications)
    state = "enabled" if notifications[user_id] else "disabled"
    await ctx.send(f"Notifications have been {state} for you.")

@bot.command()
async def test(ctx):
    # Placeholder for the test command
    pass

# Replace 'YOUR_BOT_TOKEN' with the imported BOT_TOKEN
bot.run(BOT_TOKEN)
