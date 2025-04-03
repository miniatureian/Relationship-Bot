from discord.ui import View, Button,Select
from discord import Interaction  # Added import for Interaction
import discord  # Added import for discord
import prompt_manager

class NotificationPreferenceView(View):
    def __init__(self, member_id, callback):
        super().__init__(timeout=None)
        self.member_id = str(member_id)
        self.callback = callback  # Store the callback function

    @discord.ui.button(label="Enable Notifications", style=discord.ButtonStyle.green)
    async def enable_notifications(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Notifications have been enabled for you.", ephemeral=True)
        if self.callback:
            await self.callback(self.member_id, True)  # Invoke the callback with the member ID and value

    @discord.ui.button(label="Disable Notifications", style=discord.ButtonStyle.red)
    async def disable_notifications(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Notifications have been disabled for you.", ephemeral=True)
        if self.callback:
            await self.callback(self.member_id, False)  # Invoke the callback with the member ID and value
