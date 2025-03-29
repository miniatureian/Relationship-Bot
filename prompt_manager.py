import json
import os
import random
import schedule
import time
from datetime import datetime
import pytz
import threading

class PromptManager:
    PROMPTS_FOLDER = "prompts"
    USED_PROMPTS_FILE = os.path.join(os.path.dirname(__file__), "used_prompts.json")
    INPROGRESS_PROMPTS_FILE = os.path.join(os.path.dirname(__file__), "inprogress_prompts.json")
    _schedule_lock = threading.Lock()  # Class-level lock for schedule_new_prompt

    def __init__(self):
        # Ensure the prompts folder exists
        if not os.path.exists(self.PROMPTS_FOLDER):
            os.makedirs(self.PROMPTS_FOLDER)

        # Ensure the used prompts file exists
        if not os.path.exists(self.USED_PROMPTS_FILE):
            with open(self.USED_PROMPTS_FILE, "w") as f:
                json.dump({}, f)

        # Ensure the inprogress prompts file exists
        if not os.path.exists(self.INPROGRESS_PROMPTS_FILE):
            with open(self.INPROGRESS_PROMPTS_FILE, "w") as f:
                json.dump({}, f)

        # Start the schedule function
        threading.Thread(target=self.schedule_new_prompt, daemon=True).start()

    def get_random_prompt(self):
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
            prompts = json.load(f)

        if not prompts:
            raise ValueError(f"No prompts found in {selected_file}.")

        # Randomly select a prompt
        prompt_text = random.choice(prompts)

        # Move the selected prompt to inprogress_prompts.json
        self._move_prompt_to_inprogress(selected_file, prompt_text)

        return {"filename": selected_file, "prompt": prompt_text}

    def _move_prompt_to_inprogress(self, filename, prompt_text):
        file_path = os.path.join(self.PROMPTS_FOLDER, filename)

        # Load prompts from the file
        with open(file_path, "r") as f:
            prompts = json.load(f)

        # Remove the specific prompt
        if prompt_text in prompts:
            prompts.remove(prompt_text)

        # Save the updated prompts back to the file
        with open(file_path, "w") as f:
            json.dump(prompts, f, indent=4)

        # Load inprogress prompts
        with open(self.INPROGRESS_PROMPTS_FILE, "r") as f:
            inprogress_prompts = json.load(f)

        # Add the prompt to the inprogress prompts
        if filename not in inprogress_prompts:
            inprogress_prompts[filename] = []

        inprogress_prompts[filename].append(prompt_text)

        # Save the updated inprogress prompts
        with open(self.INPROGRESS_PROMPTS_FILE, "w") as f:
            json.dump(inprogress_prompts, f, indent=4)

    def move_prompt_to_used(self, filename, prompt_text, thread_link):
        # Load inprogress prompts
        with open(self.INPROGRESS_PROMPTS_FILE, "r") as f:
            inprogress_prompts = json.load(f)

        # Remove the specific prompt from inprogress
        if filename in inprogress_prompts and prompt_text in inprogress_prompts[filename]:
            inprogress_prompts[filename].remove(prompt_text)

            # Save the updated inprogress prompts
            with open(self.INPROGRESS_PROMPTS_FILE, "w") as f:
                json.dump(inprogress_prompts, f, indent=4)

            # Load used prompts
            with open(self.USED_PROMPTS_FILE, "r") as f:
                used_prompts = json.load(f)

            # Add the prompt to the used prompts with extra data
            if filename not in used_prompts:
                used_prompts[filename] = []

            used_prompts[filename].append({
                "prompt": prompt_text,
                "origin_file": filename.replace(".json", ""),
                "thread_link": thread_link
            })

            # Save the updated used prompts
            with open(self.USED_PROMPTS_FILE, "w") as f:
                json.dump(used_prompts, f, indent=4)
        else:
            raise ValueError("Prompt not found in inprogress prompts.")

    def review_used_prompts(self):
        # Load used prompts
        with open(self.USED_PROMPTS_FILE, "r") as f:
            used_prompts = json.load(f)

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

    def schedule_new_prompt(self):
        with self._schedule_lock:  # Ensure only one thread can execute this block at a time
            def job():
                cst = pytz.timezone("US/Central")
                now = datetime.now(cst)
                print(f"Running scheduled job at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                try:
                    prompt = self.get_random_prompt()
                    print(f"New prompt scheduled: {prompt}")
                except Exception as e:
                    print(f"Error during scheduled job: {e}")

            # Schedule the job every Saturday at 7 AM CST
            schedule.every().saturday.at("07:00").do(job)

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
