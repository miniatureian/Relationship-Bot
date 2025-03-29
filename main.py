# Import necessary modules
import discord
from discord.ext import commands
import os
from config import BOT_TOKEN
from discord.ui import View, Button, Select, SelectOption
import prompt_manager

# Debug levels: 0 = Silent, 1 = Errors only, 2 = Info, 3 = Verbose
DEBUG_LEVEL = 0

# Function to log debug messages
async def log_debug(guild, message, level=1):
    if DEBUG_LEVEL >= level:
        bot_messages_channel = discord.utils.get(guild.text_channels, name="bot-messages")
        if bot_messages_channel:
            await bot_messages_channel.send(message)

# Initialize bot with intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True  # Enable message content intent to listen for commands in any channel

bot = commands.Bot(command_prefix="!", intents=intents)
manager = prompt_manager.PromptManager()  # Initialize the prompt manager

PROMPT_FILES_DIR = "prompts"

# Ensure the prompts directory exists
if not os.path.exists(PROMPT_FILES_DIR):
    os.makedirs(PROMPT_FILES_DIR)

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

    # Create necessary channels
    general_channel = await guild.create_text_channel("general")
    responses_channel = await guild.create_text_channel("responses")
    add_prompts_channel = await guild.create_text_channel("add-prompts")
    bot_messages_channel = await guild.create_text_channel("bot-messages")

    # Add server admins to the bot-messages channel
    for member in guild.members:
        if member.guild_permissions.administrator:
            overwrites = bot_messages_channel.overwrites_for(member)
            overwrites.read_messages = True
            await bot_messages_channel.set_permissions(member, overwrite=overwrites)

    # Create private channels for each member
    for member in guild.members:
        if not member.bot:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(read_messages=True),
                bot.user: discord.PermissionOverwrite(read_messages=True),
            }
            await guild.create_text_channel(f"{member.name}-private", overwrites=overwrites)

    await ctx.send("Server has been configured with private channels and the 'add-prompts' channel.")
    await log_debug(guild, "Server initialization completed.", level=2)

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

    # Save the prompt and thread info using the manager
    prompt_id = manager.add_prompt(prompt_text, thread.id)

    # Send the prompt to each private channel
    for member in guild.members:
        if not member.bot:
            private_channel = discord.utils.get(guild.text_channels, name=f"{member.name}-private")
            if private_channel:
                await private_channel.send(f"New prompt: {prompt_text}\nPlease reply to this message with your response.")

    await ctx.send(f"Prompt sent to all users and thread created in {responses_channel.mention}.")
    await log_debug(guild, f"Prompt '{prompt_text}' sent and thread created.", level=2)

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
                await message.channel.send(f"New prompt file '{prompt_text}' created.")
            else:
                await message.channel.send(f"File '{prompt_text}' already exists.")
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

        # Add a dropdown for existing prompt files
        options = []
        for file_name in manager.list_prompt_files():
            prompt_data = manager.load_prompt_file(file_name)
            options.append(
                SelectOption(
                    label=file_name,
                    description=f"{len(prompt_data.get('prompts', []))} prompts",
                    value=file_name
                )
            )

        if options:
            select = Select(
                placeholder="Select a prompt file to add to...",
                options=options
            )
            select.callback = self.select_callback
            self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_file = interaction.data["values"][0]
        manager.add_prompt_to_file(selected_file, self.prompt_text)
        await interaction.response.send_message(
            f"Prompt added to {selected_file}.", ephemeral=True
        )

@bot.event
async def on_member_join(member):
    guild = member.guild
    if not guild:
        return

    # Create a private channel for the new member
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        member: discord.PermissionOverwrite(read_messages=True),
        bot.user: discord.PermissionOverwrite(read_messages=True),
    }
    private_channel = await guild.create_text_channel(f"{member.name}-private", overwrites=overwrites)

    # Notify the general channel if it exists
    general_channel = discord.utils.get(guild.text_channels, name="general")
    if general_channel:
        await general_channel.send(f"Welcome {member.mention}! A private channel has been created for you.")

    # Send a message with notification preference buttons in the private channel
    if private_channel:
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
    await log_debug(ctx.guild, f"Debug level changed to {DEBUG_LEVEL} by {ctx.author.name}.", level=3)

@bot.command()
async def test(ctx):
    # Placeholder for the test command
    pass

# Replace 'YOUR_BOT_TOKEN' with the imported BOT_TOKEN
bot.run(BOT_TOKEN)
