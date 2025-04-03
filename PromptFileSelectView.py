from discord.ui import View, Button
from discord import ButtonStyle, Interaction
import prompt_manager

class PromptFileSelectView(View):
    def __init__(self, prompt_text):
        super().__init__(timeout=None)
        self.prompt_text = prompt_text

        # Add buttons for existing prompt files with prompt count
        for file_name in prompt_manager.PromptManager().list_prompt_files():
            prompt_count = prompt_manager.PromptManager().get_prompt_count(file_name)  # Get the count of prompts in the file
            button = Button(
                label=f"{file_name} ({prompt_count})",  # Include the count in the label
                style=ButtonStyle.primary
            )
            button.callback = self.create_button_callback(file_name)
            self.add_item(button)

    def create_button_callback(self, file_name):
        async def callback(interaction: Interaction):
            # Save the second-to-last message (prompt text) to the selected file
            prompt_manager.PromptManager().write_prompt(file_name, self.prompt_text)
            await interaction.response.send_message(
                f"Prompt added to {file_name}.", ephemeral=True
            )
        return callback
