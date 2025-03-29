import json
import os
import random

class PromptManager:
    PROMPTS_FOLDER = "prompts"
    USED_PROMPTS_FILE = "used_prompts.json"

    def __init__(self):
        # Ensure the prompts folder exists
        if not os.path.exists(self.PROMPTS_FOLDER):
            os.makedirs(self.PROMPTS_FOLDER)

        # Ensure the used prompts file exists
        if not os.path.exists(self.USED_PROMPTS_FILE):
            with open(self.USED_PROMPTS_FILE, "w") as f:
                json.dump({}, f)

    def get_random_prompt(self):
        # Get all JSON files in the prompts folder, excluding used_prompts.json
        files = [
            f for f in os.listdir(self.PROMPTS_FOLDER)
            if f.endswith(".json") and f != self.USED_PROMPTS_FILE
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

        return {"filename": selected_file, "prompt": prompt_text}

    def save_prompt(self, filename, prompt_text):
        file_path = os.path.join(self.PROMPTS_FOLDER, filename)

        # Ensure the file exists
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                json.dump([], f)

        # Load existing prompts and add the new one
        with open(file_path, "r") as f:
            prompts = json.load(f)

        prompts.append(prompt_text)

        # Save the updated prompts
        with open(file_path, "w") as f:
            json.dump(prompts, f, indent=4)

    def move_prompt_to_used(self, filename, prompt_text, thread_link):
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
