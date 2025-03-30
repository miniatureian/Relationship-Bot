# Import necessary modules
import discord
from discord.ext import commands
import os
from config import BOT_TOKEN
from discord.ui import View, Button, Select
import prompt_manager
import json

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
                    print(f"Private channel already exists for {member.name}. Skipping creation.")
                    break
            else:  # This else corresponds to the for loop, it executes if the loop is not broken
                # Create a new private channel for the member if it doesn't exist
                private_channel_name = f"{member.name}-private"
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    member: discord.PermissionOverwrite(read_messages=True),
                    bot.user: discord.PermissionOverwrite(read_messages=True),
                }
                await guild.create_text_channel(private_channel_name, overwrites=overwrites)
                for channel in getPrivateChannels(guild).keys():
                    if member.name in channel.name:
                        # send the prompt to query the member if they would like notifications in their private channel
                        view = NotificationPreferenceView(member.id)
                        await channel.send(
                            "Welcome to your private channel! Would you like to receive notifications for prompt responses?",
                            view=view
                        )
    await ctx.send("Server has been configured")
    print("Server initialization completed.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Check if the message is a reply to a prompt
    prompt_id, prompt_data = manager.get_prompt_for_channel(message.channel.name)
    if prompt_id and message.author.id not in prompt_data["responses"]:
        # Record the response
        manager.add_response(prompt_id, message.author.id, message.content)

        # Thank the user
        await message.channel.send("Thank you for your response!")

        # Check if all users have responded
        guild = message.guild
        all_users = [member.id for member in guild.members if not member.bot]
        if manager.all_responses_collected(prompt_id, all_users):
            # Post responses in the thread
            thread = discord.utils.get(guild.threads, id=prompt_data["thread_id"])
            if thread:
                response_text = "\n".join(
                    f"{guild.get_member(user_id).name}: {response}"
                    for user_id, response in prompt_data["responses"].items()
                )
                await thread.send(f"All responses collected:\n{response_text}")

            # Notify users who opted in
            for user_id, notify in manager.get_notifications().items():
                if notify:
                    user = guild.get_member(int(user_id))
                    if user:
                        await user.send(f"Responses for the prompt '{prompt_data['prompt']}' have been posted.")

            # Mark the prompt as completed
            manager.complete_prompt(prompt_id)

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

class NotificationPreferenceView(View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = str(member_id)

    @discord.ui.button(label="Enable Notifications", style=discord.ButtonStyle.green)
    async def enable_notifications(self, interaction: discord.Interaction, button: Button):
        manager.set_notification(self.member_id, True)
        await interaction.response.send_message("Notifications have been enabled for you.", ephemeral=True)

    @discord.ui.button(label="Disable Notifications", style=discord.ButtonStyle.red)
    async def disable_notifications(self, interaction: discord.Interaction, button: Button):
        manager.set_notification(self.member_id, False)
        await interaction.response.send_message("Notifications have been disabled for you.", ephemeral=True)

class PromptFileSelectView(View):
    def __init__(self, prompt_text):
        super().__init__(timeout=None)
        self.prompt_text = prompt_text

        # Add buttons for existing prompt files
        for file_name in manager.list_prompt_files():
            button = Button(
                label=file_name,
                style=discord.ButtonStyle.primary
            )
            button.callback = self.create_button_callback(file_name)
            self.add_item(button)

    def create_button_callback(self, file_name):
        
        async def callback(interaction: discord.Interaction):
            # Save the second-to-last message (prompt text) to the selected file
            manager.add_prompt_to_file(file_name, self.prompt_text)
            await interaction.response.send_message(
                f"Prompt added to {file_name}.", ephemeral=True
            )
        return callback

@bot.event
async def on_member_join(member):
    guild = member.guild
    if not guild:
        return

    private_channel_name = f"{member.name}-private"
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

@bot.command()
async def debug(ctx, level: int):
    # Set the debug level
    global DEBUG_LEVEL
    DEBUG_LEVEL = max(0, min(level, 3))  # Clamp the level between 0 and 3
    await ctx.send(f"Debug level set to {DEBUG_LEVEL}.")
    print(f"Debug level changed to {DEBUG_LEVEL} by {ctx.author.name}.")

@bot.command()
async def test(ctx):
    # Use the prompt manager to get a random prompt
    # prompt = manager.get_random_prompt()
    prompt = "test"  # Placeholder for testing purposes, replace with actual logic if needed
    if not prompt:
        await ctx.send("No prompts available.")
        return

    guild = ctx.guild
    if not guild:
        await ctx.send("This command can only be used in a server.")
        return

    # Debug: Log the names of all channels the bot has access to
    channel_names = [channel.name for channel in guild.text_channels]
    print(f"Accessible channels: {channel_names}")  # Debugging output

    # Test sending command to the private channels
    for channel in getPrivateChannels(guild):  # Get all private channels in the guild
        #find the list of non bot members of the private channel:
        for member in getPrivateChannels(guild)[channel]:
            # mention this member when you send the prompt in the private channel
            print(f"Sending prompt to {member.name} in {channel.name}.")  # Debugging output
            await channel.send(
                f"Hello {member.mention},\n"
                f"This week's prompt is:\n\n"
                f"**{prompt}**\n\n"
                f"Please reply directly to this message with your response."
            )

    await ctx.send("Prompt has been sent to all members' private channels.")

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
