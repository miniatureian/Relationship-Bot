# Import necessary modules
import discord
from discord.ext import commands
import os
from config import BOT_TOKEN
from discord.ui import View, Button, Select
import prompt_manager
import json
from NotificationPreferenceView import NotificationPreferenceView
from PromptFileSelectView import PromptFileSelectView

# Debug levels: 0 = Silent, 1 = Errors only, 2 = Info, 3 = Verbose
DEBUG_LEVEL = 3

# Function to log debug messages
async def log_debug(guild, message, level=1):
    if DEBUG_LEVEL >= level:
        print(f"[DEBUG] {message}")

# Initialize bot with intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True  # Enable message content intent to listen for commands in any channel

bot = commands.Bot(command_prefix="!", intents=intents)
manager = prompt_manager.PromptManager()  # Initialize the prompt manager

PROMPT_FILES_DIR = "prompts"
NOTIFY_FILE = "notify.json"

# Ensure the prompts directory exists
if not os.path.exists(PROMPT_FILES_DIR):
    os.makedirs(PROMPT_FILES_DIR)

# Load notify.json data with validation
def load_notify_data():
    if os.path.exists(NOTIFY_FILE):
        try:
            with open(NOTIFY_FILE, "r") as f:
                data = json.load(f)
                return data
        except (json.JSONDecodeError, KeyError):
            pass

notify_data = load_notify_data()

def save_notify_data():
    with open(NOTIFY_FILE, "w") as f:
        json.dump(notify_data, f)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    for guild in bot.guilds:
        # Automatically run the init command for each guild the bot is in
        ctx = await bot.get_context(await guild.text_channels[0].send("Initializing server..."))
        await init(ctx)

@bot.command()
async def info(ctx):
    # Provide information about available commands
    info_message = (
        "Available commands:\n"
        "!info - Show this info message\n"
        "!init - Configure the server with private channels for each user\n"
        "!test - Placeholder command (to be implemented later)\n"
        "!prompt - Send a prompt to all users and create a thread in the responses channel\n"
        "!notify - Toggle notifications for prompt responses\n"
        "!debug (number) - Set the debug level (0 = Silent, 1 = Errors, 2 = Info, 3 = Verbose)"
    )
    await ctx.send(info_message)

@bot.command()
async def init(ctx):
    guild = ctx.guild
    if not guild:
        await ctx.send("This command can only be used in a server.")
        return

    # Ensure necessary channels exist
    channel_names = ["general", "responses", "add-prompts", "bot-messages"]
    for channel_name in channel_names:
        if not discord.utils.get(guild.text_channels, name=channel_name):
            await guild.create_text_channel(channel_name)

    # Create private channels for each member
    private_channels = getPrivateChannels(guild)  # Get existing private channels to avoid duplicates
    for member in guild.members:
        if not member.bot:
            for existing_channel, members in private_channels.items():
                # Check if the member already has a private channel
                if member in members:
                    break
            else:  # This else corresponds to the for loop, it executes if the loop is not broken
                # Create a new private channel for the member if it doesn't exist
                private_channel_name = f"{member.name.replace('.', '')}-private"
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    member: discord.PermissionOverwrite(read_messages=True),
                    bot.user: discord.PermissionOverwrite(read_messages=True),
                }
                await guild.create_text_channel(private_channel_name, overwrites=overwrites)
                for channel in getPrivateChannels(guild).keys():
                    if private_channel_name in channel.name:
                        # send the prompt to query the member if they would like notifications in their private channel
                        view = NotificationPreferenceView(member.id)
                        await channel.send(
                            "Welcome to your private channel! Would you like to receive notifications for prompt responses?",
                            view=view
                        )
    print("Server initialization completed.")

@bot.command()
async def test(ctx):
    # Use the prompt manager to get a random prompt
    promptdict = manager.get_random_prompt()
    prompt = promptdict["filename"] + ": " + promptdict["prompt"] if promptdict else None
    if not prompt:
        await ctx.send("No prompts available.")
        return

    guild = ctx.guild
    if not guild:
        await ctx.send("This command can only be used in a server.")
        return

    # Send the prompt to private channels and store message IDs
    private_channels = getPrivateChannels(guild)
    message_ids = {}
    for channel, members in private_channels.items():
        for member in members:
            if manager.get_notifications().get(str(member.id), False):
                mention_text = f"Hello {member.mention},\n"
            else:
                mention_text = ""

            message = await channel.send(
                f"{mention_text}"
                f"This week's prompt is:\n\n"
                f"**{prompt}**\n\n"
                f"Please reply directly to this message with your response."
            )
            message_ids[message.id] = {"user_id": member.id, "username": member.name}

    # Add the prompt and message IDs to in-progress prompts
    manager.add_prompt(promptdict["prompt"], message_ids)
    await ctx.send("Prompt has been sent to all members' private channels.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Check if the message is a reply to a prompt
    if message.reference and message.reference.message_id:
        prompt_id, prompt_data = manager.get_prompt_by_message_id(message.reference.message_id)
        if prompt_id and message.author.id not in prompt_data["responses"]:
            # Record the response
            manager.add_response(prompt_id, message.author.name, message.content)

            # Thank the user
            await message.channel.send("Thank you for your response!")

            # Check if all users have responded
            guild = message.guild
            if manager.all_responses_collected(prompt_id):
                print("All responses collected for prompt ID:", prompt_id)
                # Create a thread in the responses channel
                responses_channel = discord.utils.get(guild.text_channels, name="responses")
                if responses_channel:
                    print(f"Creating a thread in the 'responses' channel for prompt ID {prompt_id}.")
                    thread = await responses_channel.create_thread(
                        name=f"Responses to: {prompt_data['prompt_text']}"
                    )
                    await thread.send(f"**Prompt:** {prompt_data['prompt_text']}")
                    for user_id, response_data in prompt_data["responses"].items():
                        # Send each user's response as a reply to the thread
                        await thread.send(f"**{response_data['username']}**: {response_data['response']}")

                # Mark the prompt as completed
                manager.complete_prompt(prompt_id)
                print(f"Prompt ID {prompt_id} has been completed and all responses have been processed.")

    # Handle messages in the "add-prompts" channel
    if message.channel.name == "add-prompts" and not message.author.bot:
        prompt_text = message.content.strip()

        # Check if the input is a new file name
        if prompt_text.endswith(".json"):
            if manager.create_prompt_file(prompt_text):
                # Save the second-to-last message (prompt text) to the new file
                messages = await message.channel.history(limit=2).to_list()
                previous_message = messages[1]  # Get the second-to-last message
                manager.add_prompt_to_file(prompt_text, previous_message.content.strip())
                await message.channel.send(f"New prompt file '{prompt_text}' created and prompt added.")
            else:
                await message.channel.send(f"File '{prompt_text}' already exists. Prompt not added.")
        else:
            # Provide buttons for existing files
            view = PromptFileSelectView(prompt_text)
            await message.channel.send(
                f"Select a file to add the prompt '{prompt_text}' or create a new file by typing its name.",
                view=view
            )

    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    guild = member.guild
    if not guild:
        return

    private_channel_name = f"{member.name.replace('.', '')}-private"
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        member: discord.PermissionOverwrite(read_messages=True),
        bot.user: discord.PermissionOverwrite(read_messages=True),
    }
    private_channel = await guild.create_text_channel(private_channel_name, overwrites=overwrites)

    # Notify the general channel if it exists
    general_channel = discord.utils.get(guild.text_channels, name="general")
    if general_channel:
        await general_channel.send(f"Welcome {member.mention}! A private channel has been created for you.")

    view = NotificationPreferenceView(member.id)
    await private_channel.send(
        "Welcome to your private channel! Would you like to receive notifications for prompt responses?",
        view=view
    )

    await log_debug(guild, f"Private channel created for new member {member.name}.", level=2)

@bot.command()
async def notify(ctx):
    # Toggle notification preferences for the user
    user_id = str(ctx.author.id)
    state = manager.toggle_notification(user_id)
    await ctx.send(f"Notifications have been {'enabled' if state else 'disabled'} for you.")

def getPrivateChannels(guild):
    # Helper function to get all private channels in a guild
    private_channels = {}
    for channel in guild.text_channels:
        if "private" in channel.name:
            members = []
            for member in channel.members:  # Iterate over members in the private channel
                if member.bot:
                    continue
                members.append(member)  # Add non-bot members to the list
            #create the channel and list of members as a key-value pair in the dictionary
            private_channels[channel] = members
                
    return private_channels  # Return both private channels and members for further use

# Replace 'YOUR_BOT_TOKEN' with the imported BOT_TOKEN
bot.run(BOT_TOKEN)
