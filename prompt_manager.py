import json
import os
import random
import schedule
import time
from datetime import datetime
import pytz
import threading

class PromptManager:
    # Constants for folder and file paths
    PROMPTS_FOLDER = "prompts"  # Folder where prompt files are stored
    USED_PROMPTS_FILE = os.path.join(os.path.dirname(__file__), "used_prompts.json")  # File to track used prompts
    INPROGRESS_PROMPTS_FILE = os.path.join(os.path.dirname(__file__), "inprogress_prompts.json")  # File to track in-progress prompts
    _schedule_lock = threading.Lock()  # Lock to ensure thread-safe scheduling
    _scheduled_time = "07:00"  # Default scheduled time for new prompts

    def __init__(self):
        """
        Initializes the PromptManager by ensuring necessary folders and files exist,
        and starts the scheduling thread for new prompts.
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

        # Start the scheduling thread
        threading.Thread(target=self.schedule_new_prompt, daemon=True).start()

    def _safe_load_json(self, file_path):
        """
        Safely loads JSON data from a file, returning an empty dictionary or list if the file is invalid.

        :param file_path: The path to the JSON file.
        :return: The loaded JSON data, or an empty dictionary/list if invalid.
        """
        if not os.path.exists(file_path):
            return {} if file_path.endswith(".json") else []

        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return {} if file_path.endswith(".json") else []

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
        prompts = self._safe_load_json(file_path)

        if not prompts:
            raise ValueError(f"No prompts found in {selected_file}.")

        # Randomly select a prompt
        prompt_text = random.choice(prompts)

        # Move the selected prompt to in-progress
        self._move_prompt_to_inprogress(selected_file, prompt_text)

        return {"filename": selected_file, "prompt": prompt_text}

    def _move_prompt_to_inprogress(self, filename, prompt_text):
        """
        Moves a selected prompt from its file to the in-progress prompts file.

        :param filename: The name of the file containing the prompt.
        :param prompt_text: The text of the prompt to move.
        """
        file_path = os.path.join(self.PROMPTS_FOLDER, filename)

        # Load prompts from the file
        prompts = self._safe_load_json(file_path)

        # Remove the specific prompt
        if prompt_text in prompts:
            prompts.remove(prompt_text)

        # Save the updated prompts back to the file
        with open(file_path, "w") as f:
            json.dump(prompts, f, indent=4)

        # Load in-progress prompts
        inprogress_prompts = self._safe_load_json(self.INPROGRESS_PROMPTS_FILE)

        # Add the prompt to the in-progress prompts
        if filename not in inprogress_prompts:
            inprogress_prompts[filename] = []

        inprogress_prompts[filename].append(prompt_text)

        # Save the updated in-progress prompts
        with open(self.INPROGRESS_PROMPTS_FILE, "w") as f:
            json.dump(inprogress_prompts, f, indent=4)

    def move_prompt_to_used(self, filename, prompt_text, thread_id, thread_link):
        """
        Moves a prompt from in-progress to used prompts, adding metadata.

        :param filename: The name of the file containing the prompt.
        :param prompt_text: The text of the prompt to move.
        :param thread_id: The ID of the thread where the prompt was used.
        :param thread_link: A link to the thread where the prompt was used.
        """
        # Load in-progress prompts
        inprogress_prompts = self._safe_load_json(self.INPROGRESS_PROMPTS_FILE)

        # Remove the specific prompt from in-progress
        if "thread_prompts" in inprogress_prompts and thread_id in inprogress_prompts["thread_prompts"]:
            prompt_data = inprogress_prompts["thread_prompts"].pop(thread_id)

            # Save the updated in-progress prompts
            with open(self.INPROGRESS_PROMPTS_FILE, "w") as f:
                json.dump(inprogress_prompts, f, indent=4)

            # Load used prompts
            used_prompts = self._safe_load_json(self.USED_PROMPTS_FILE)

            # Add the prompt to the used prompts with extra data
            if filename not in used_prompts:
                used_prompts[filename] = []

            used_prompts[filename].append({
                "prompt": prompt_text,
                "origin_file": filename.replace(".json", ""),
                "thread_id": thread_id,
                "thread_link": thread_link,
                "author": prompt_data.get("author", "Unknown")
            })

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
        used_prompts = self._safe_load_json(self.USED_PROMPTS_FILE)

        if not used_prompts:
            return "No used prompts available."

        # Format the used prompts beautifully
        review_message = "Used Prompts:\n"
        for filename, prompts in used_prompts.items():
            review_message += f"\n**From File:** {filename}\n"
            for prompt_data in prompts:
                review_message += (
                    f"- **Prompt:** {prompt_data['prompt']}\n"
                    f"  **Origin File:** {prompt_data['origin_file']}\n"
                    f"  **Thread Link:** {prompt_data['thread_link']}\n"
                )
        return review_message

    def update_scheduled_time(self, new_time):
        """
        Updates the scheduled time for the new prompt job.

        :param new_time: The new time in "HH:MM" format.
        """
        with self._schedule_lock:
            self._scheduled_time = new_time
            print(f"Scheduled time updated to {new_time}.")
            schedule.clear()  # Clear all scheduled jobs
            self._schedule_new_prompt_job()  # Reschedule the job with the new time

    def _schedule_new_prompt_job(self):
        """
        Schedules the new prompt job based on the current scheduled time.
        """
        def job():
            # Get the current time in CST
            cst = pytz.timezone("US/Central")
            now = datetime.now(cst)
            print(f"Running scheduled job at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            try:
                prompt = self.get_random_prompt()
                print(f"New prompt scheduled: {prompt}")
            except Exception as e:
                print(f"Error during scheduled job: {e}")

        # Schedule the job every Saturday at the specified time
        schedule.every().saturday.at(self._scheduled_time).do(job)

    def schedule_new_prompt(self):
        """
        Starts the scheduling thread for new prompts.
        """
        with self._schedule_lock:  # Ensure only one thread can execute this block at a time
            self._schedule_new_prompt_job()  # Schedule the job initially

            print("Scheduler started. Waiting for the next scheduled job...")
            while True:
                # Run pending jobs
                schedule.run_pending()

                # Calculate the time until the next job
                next_run = schedule.idle_seconds()
                if next_run is None:
                    break  # No more jobs scheduled
                elif next_run > 0:
                    time.sleep(next_run)

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

    def add_prompt(self, prompt_text, message_ids):
        """
        Adds a prompt and initializes its structure with message IDs and responses.

        :param prompt_text: The text of the prompt.
        :param message_ids: A dictionary mapping message IDs to user data.
        """
        inprogress_prompts = self._safe_load_json(self.INPROGRESS_PROMPTS_FILE)

        prompt_id = str(random.randint(100000, 999999))  # Generate a unique prompt ID
        inprogress_prompts[prompt_id] = {
            "prompt_text": prompt_text,
            "message_ids": message_ids,
            "responses": {}
        }

        with open(self.INPROGRESS_PROMPTS_FILE, "w") as f:
            json.dump(inprogress_prompts, f, indent=4)

    def add_response(self, prompt_id, username, response):
        """
        Records a user's response to a prompt.

        :param prompt_id: The ID of the prompt.
        :param user_id: The ID of the user responding to the prompt.
        :param username: The username of the user responding to the prompt.
        :param response: The response text provided by the user.
        """
        inprogress_prompts = self._safe_load_json(self.INPROGRESS_PROMPTS_FILE)

        if prompt_id in inprogress_prompts:
            inprogress_prompts[prompt_id]["responses"][username] =  response
            
            with open(self.INPROGRESS_PROMPTS_FILE, "w") as f:
                json.dump(inprogress_prompts, f, indent=4)
        else:
            raise ValueError("Prompt ID not found.")

    def get_prompt_by_message_id(self, message_id):
        """
        Retrieves the prompt associated with a specific message ID.

        :param message_id: The ID of the message.
        :return: A tuple containing the prompt ID and its data, or (None, None) if not found.
        """
        inprogress_prompts = self._safe_load_json(self.INPROGRESS_PROMPTS_FILE)

        for prompt_id, prompt_data in inprogress_prompts.items():
            # Ensure prompt_data is a dictionary and contains "message_ids"
            if isinstance(prompt_data, dict) and "message_ids" in prompt_data:
                if str(message_id) in prompt_data["message_ids"]:
                    return prompt_id, prompt_data

        return None, None

    def all_responses_collected(self, prompt_id):

        """Compares sorted lists of usernames from message_ids and responses for a given prompt_id.

        :param prompt_id: The ID of the prompt to compare.
        :return: True if the sorted lists of usernames are the same, False otherwise.
        """
        inprogress_prompts = self._safe_load_json(self.INPROGRESS_PROMPTS_FILE)

        if prompt_id not in inprogress_prompts:
            raise ValueError(f"Prompt ID '{prompt_id}' not found.")

        prompt_data = inprogress_prompts[prompt_id]

        # Extract and sort usernames from message_ids
        message_ids_usernames = sorted(
            user_data["username"]
            for user_data in prompt_data.get("message_ids", {}).values()
        )

        # Extract and sort usernames from responses
        responses_usernames = sorted(prompt_data.get("responses", {}).keys())

        # Compare the two sorted lists
        return message_ids_usernames == responses_usernames

    def get_notifications(self):
        """
        Retrieves notification preferences for users.
        """
        notifications_file = os.path.join(os.path.dirname(__file__), "notifications.json")
        return self._safe_load_json(notifications_file)

    def complete_prompt(self, prompt_id):
        """
        Marks a prompt as completed and removes it from in-progress prompts.

        :param prompt_id: The ID of the prompt to mark as completed.
        """
        inprogress_prompts = self._safe_load_json(self.INPROGRESS_PROMPTS_FILE)

        if prompt_id in inprogress_prompts:
            del inprogress_prompts[prompt_id]

            with open(self.INPROGRESS_PROMPTS_FILE, "w") as f:
                json.dump(inprogress_prompts, f, indent=4)

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

    def load_prompt_file(self, file_name):
        """
        Loads the content of a specific prompt file.
        """
        file_path = os.path.join(self.PROMPTS_FOLDER, file_name)
        return self._safe_load_json(file_path)

    def add_prompt_to_file(self, file_name, prompt_text):
        """
        Adds a prompt to a specific file.
        """
        file_path = os.path.join(self.PROMPTS_FOLDER, file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File '{file_name}' not found.")

        with open(file_path, "r") as f:
            prompts = json.load(f)

        if prompt_text not in prompts:
            prompts.append(prompt_text)

        with open(file_path, "w") as f:
            json.dump(prompts, f, indent=4)

    def set_notification(self, user_id, state):
        """
        Sets notification preferences for a user.
        """
        notifications_file = os.path.join(os.path.dirname(__file__), "notifications.json")
        notifications = self._safe_load_json(notifications_file)

        notifications[str(user_id)] = state

        with open(notifications_file, "w") as f:
            json.dump(notifications, f, indent=4)

    def toggle_notification(self, user_id):
        """
        Toggles notification preferences for a user.
        """
        notifications_file = os.path.join(os.path.dirname(__file__), "notifications.json")
        notifications = self._safe_load_json(notifications_file)

        current_state = notifications.get(str(user_id), False)
        notifications[str(user_id)] = not current_state

        with open(notifications_file, "w") as f:
            json.dump(notifications, f, indent=4)

        return not current_state

    def get_prompt_count(self, file_name):
        """
        Returns the number of prompts in the specified file.

        :param file_name: The name of the file to count prompts in.
        :return: The count of prompts in the file.
        """
        file_path = os.path.join(self.PROMPTS_FOLDER, file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File '{file_name}' not found.")

        prompts = self._safe_load_json(file_path)
        return len(prompts)

