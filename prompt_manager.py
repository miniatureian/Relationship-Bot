import json
import os
import random
import time
from datetime import datetime
import pytz

class PromptManager:
    # Constants for folder and file paths
    PROMPTS_FOLDER = "prompts"  # Folder where prompt files are stored
    USED_PROMPTS_FILE = os.path.join(os.path.dirname(__file__), "used_prompts.json")  # File to track used prompts
    INPROGRESS_PROMPTS_FILE = os.path.join(os.path.dirname(__file__), "inprogress_prompts.json")  # File to track in-progress prompts

    def __init__(self):
        """
        Initializes the PromptManager by ensuring necessary folders and files exist.
        """
        # Ensure the prompts folder exists
        if not os.path.exists(self.PROMPTS_FOLDER):
            os.makedirs(self.PROMPTS_FOLDER)

        # Ensure the used prompts file exists
        if not os.path.exists(self.USED_PROMPTS_FILE):
            with open(self.USED_PROMPTS_FILE, "w") as f:
                json.dump({}, f)

        # Ensure the in-progress prompts file exists
        if not os.path.exists(self.INPROGRESS_PROMPTS_FILE):
            with open(self.INPROGRESS_PROMPTS_FILE, "w") as f:
                json.dump({}, f)

    def get_random_prompt(self):
        """
        Selects a random prompt from the available prompt files and moves it to in-progress.

        :return: A dictionary containing the filename and the selected prompt text.
        """
        # Get all JSON files in the prompts folder
        files = [
            f for f in os.listdir(self.PROMPTS_FOLDER)
            if f.endswith(".json")
        ]
        if not files:
            raise FileNotFoundError("No prompt files found in the prompts folder.")

        # Randomly select a file
        selected_file = random.choice(files)
        file_path = os.path.join(self.PROMPTS_FOLDER, selected_file)

        # Load prompts from the selected file
        with open(file_path, "r") as f:
            try:
                prompts = json.load(f)
                prompt_text = random.choice(prompts)
                prompts.remove(prompt_text)

            except json.JSONDecodeError:
                raise ValueError(f"No prompts found in {selected_file}.")
            
        with open(file_path, "w") as f:
            json.dump(prompts, f, indent=4)
        # Load in-progress prompts

        with open(self.INPROGRESS_PROMPTS_FILE, "r") as f:
            try:
                inprogress_prompts = json.load(f)
            except json.JSONDecodeError:
                raise ValueError("Failed to load in-progress prompts.")
            
        prompt_id = str(random.randint(100000, 999999))  # Generate a unique prompt ID
        if prompt_id not in inprogress_prompts:
            inprogress_prompts[prompt_id] = {}
        inprogress_prompts[prompt_id] = {
            "prompt_id": prompt_id,
            "selected_file": selected_file,
            "prompt_text": prompt_text,
            "message_ids": {},
            "responses": {}
        }
        with open(self.INPROGRESS_PROMPTS_FILE, "w") as f:
            json.dump(inprogress_prompts, f, indent=4)

        return prompt_text,prompt_id
    
    def add_message_id(self, prompt_id, message_id, user_id):
        """
        Adds a message ID and username to the in-progress
        :prompt_id: The ID of the prompt.
        :message_id: The ID of the message.
        :username: The username of the user.
        """
        with open(self.INPROGRESS_PROMPTS_FILE, "r") as f:
            inprogress_prompts = json.load(f)

        if prompt_id in inprogress_prompts:
            inprogress_prompts[prompt_id]["message_ids"][message_id] = {
                "user_id": user_id,
                "timestamp": time.time()
            }

            with open(self.INPROGRESS_PROMPTS_FILE, "w") as f:
                json.dump(inprogress_prompts, f, indent=4)
        else:
            raise ValueError("Prompt ID not found.")
        
    def move_prompt_to_used(self, prompt_id, comment_link):
        """
        Moves a prompt from in-progress to used prompts, adding metadata.

        :param filename: The name of the file containing the prompt.
        :param prompt_text: The text of the prompt to move.
        :param thread_id: The ID of the thread where the prompt was used.
        :param thread_link: A link to the thread where the prompt was used.
        """
        # Load in-progress prompts
        with open(self.INPROGRESS_PROMPTS_FILE, "r") as f:
            inprogress_prompts = json.load(f)

        # Remove the specific prompt from in-progress
        if prompt_id in inprogress_prompts:
            prompt_data = inprogress_prompts.pop(prompt_id)
            prompt_data["comment_link"] = comment_link
            prompt_data["timestamp"] = datetime.now(pytz.timezone("UTC")).strftime("%Y-%m-%d %H:%M:%S")

            # Save the updated in-progress prompts
            with open(self.INPROGRESS_PROMPTS_FILE, "w") as f:
                json.dump(inprogress_prompts, f, indent=4)

            # Load used prompts
            with open(self.USED_PROMPTS_FILE, "r") as f:
                used_prompts = json.load(f)

            # Add the prompt to the used prompts with extra data
            if prompt_id not in used_prompts:
                used_prompts[prompt_id] = []
                
            used_prompts[prompt_id] = prompt_data

            # Save the updated used prompts
            with open(self.USED_PROMPTS_FILE, "w") as f:
                json.dump(used_prompts, f, indent=4)
        else:
            raise ValueError("Prompt not found in in-progress prompts.")

    def review_used_prompts(self):
        """
        Returns a formatted string of all used prompts for review.

        :return: A string containing the review of used prompts.
        """
        # Load used prompts
        with open(self.USED_PROMPTS_FILE, "r") as f:
            used_prompts = json.load(f)

        if not used_prompts:
            return "No used prompts available."

        # Format the used prompts beautifully
        review_message = "Used Prompts:\n"
        for prompt_id, prompts in used_prompts.items():
            for prompt_data in prompts:
                review_message += (
                    f"- **Prompt:** {prompt_data['prompt']}\n"
                    f"  **Origin File:** {prompt_data['selected_file']}\n"
                    f"  **Comment Link:** {prompt_data['comment_link']}\n"
                )
        return review_message
    def get_prompt(self, prompt_id):
        """
        Retrieves a specific prompt by its ID.

        :param prompt_id: The ID of the prompt to retrieve.
        :return: The prompt text and metadata.
        """
        with open(self.INPROGRESS_PROMPTS_FILE, "r") as f:
            inprogress_prompts = json.load(f)

        if prompt_id in inprogress_prompts:
            return inprogress_prompts[prompt_id]
        else:
            raise ValueError(f"Prompt ID '{prompt_id}' not found.")
    def get_prompt_by_message_id(self, message_id):
        """
        Retrieves a prompt by its message ID.

        :param message_id: The message ID to search for.
        :return: The prompt text and metadata.
        """
        with open(self.INPROGRESS_PROMPTS_FILE, "r") as f:
            inprogress_prompts = json.load(f)

        for prompt_id, prompt_data in inprogress_prompts.items():
            if str(message_id) in prompt_data["message_ids"]:
                print("message_id:",message_id, " prompt_id:",prompt_id)
                return prompt_id,prompt_data
        return None,None
        
    def write_prompt(self, filename, prompt_text):
        """
        Writes a new prompt to the specified file in the prompts folder.

        :param filename: The name of the file (without path) to write the prompt to.
        :param prompt_text: The prompt string to be added.
        """
        file_path = os.path.join(self.PROMPTS_FOLDER, filename)

        # Ensure the file exists
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                json.dump([], f)

        # Load existing prompts
        with open(file_path, "r") as f:
            prompts = json.load(f)

        # Add the new prompt
        if prompt_text not in prompts:
            prompts.append(prompt_text)

        # Save the updated prompts
        with open(file_path, "w") as f:
            json.dump(prompts, f, indent=4)

    def add_response(self, prompt_id, user_id, response):
        """
        Records a user's response to a prompt.

        :param prompt_id: The ID of the prompt.
        :param username: The username of the user responding to the prompt.
        :param response: The response text provided by the user.
        """
        with open(self.INPROGRESS_PROMPTS_FILE, "r") as f:
            inprogress_prompts = json.load(f)

        if prompt_id in inprogress_prompts:
            inprogress_prompts[prompt_id]["responses"][user_id] =  response
            
            with open(self.INPROGRESS_PROMPTS_FILE, "w") as f:
                json.dump(inprogress_prompts, f, indent=4)
        else:
            raise ValueError("Prompt ID not found.")

    def all_responses_collected(self, prompt_id, guild_members):

        """Compares sorted lists of usernames from message_ids and responses for a given prompt_id.

        :param prompt_id: The ID of the prompt to compare.
        :return: True if the sorted lists of usernames are the same, False otherwise.
        """
        with open(self.INPROGRESS_PROMPTS_FILE, "r") as f:
            inprogress_prompts = json.load(f)

        if prompt_id not in inprogress_prompts:
            raise ValueError(f"Prompt ID '{prompt_id}' not found.")

        prompt_data = inprogress_prompts[prompt_id]
        for member in guild_members:
            if member.bot:
                continue
            if str(member.id) not in prompt_data["responses"]:
                return False
        return True

    def get_notifications(self):
        """
        Retrieves notification preferences for users.
        """
        notifications_file = os.path.join(os.path.dirname(__file__), "notifications.json")
        with open(notifications_file, "r") as f:
            return json.load(f)

    def create_prompt_file(self, file_name):
        """
        Creates a new prompt file.
        """
        file_path = os.path.join(self.PROMPTS_FOLDER, file_name)
        if os.path.exists(file_path):
            return False

        with open(file_path, "w") as f:
            json.dump([], f)
        return True

    def list_prompt_files(self):
        """
        Lists all available prompt files.
        """
        return [
            f for f in os.listdir(self.PROMPTS_FOLDER)
            if f.endswith(".json")
        ]

    def get_prompt_count(self, file_name):
        """
        Returns the number of prompts in the specified file.

        :param file_name: The name of the file to count prompts in.
        :return: The count of prompts in the file.
        """
        file_path = os.path.join(self.PROMPTS_FOLDER, file_name)
        with open(file_path, "r") as f:
            prompts = json.load(f)

        return len(prompts)

