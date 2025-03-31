from discord.ui import View, Button
from discord import Interaction  # Added import for Interaction
import discord  # Added import for discord
import prompt_manager

class NotificationPreferenceView(View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = str(member_id)

    @discord.ui.button(label="Enable Notifications", style=discord.ButtonStyle.green)
    async def enable_notifications(self, interaction: discord.Interaction, button: Button):
        prompt_manager.PromptManager().set_notification(self.member_id, True)
        await interaction.response.send_message("Notifications have been enabled for you.", ephemeral=True)

    @discord.ui.button(label="Disable Notifications", style=discord.ButtonStyle.red)
    async def disable_notifications(self, interaction: discord.Interaction, button: Button):
        prompt_manager.PromptManager().set_notification(self.member_id, False)
        await interaction.response.send_message("Notifications have been disabled for you.", ephemeral=True)
