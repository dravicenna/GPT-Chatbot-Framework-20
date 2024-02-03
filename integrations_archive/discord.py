"""
Setting Up Discord Integration

Integrating a Discord bot into your application involves creating a bot on Discord's Developer Portal and configuring your environment to use it. Follow these steps to set up your Discord integration:

1. Create a Discord Bot:
   - Go to the Discord Developer Portal (https://discord.com/developers/applications) and log in with your Discord account.
   - Click on 'New Application', give it a name, and create the application.
   - Within the application, navigate to the 'Bot' tab and click 'Add Bot'. Confirm the creation of the bot.
   - After creating the bot, you will see a token under the 'TOKEN' section. This is your bot's API token.

2. Add the API Key to Replit:
   - In your Replit project where the Discord bot will be used, open the 'Secrets' tab (lock icon).
   - Add a new secret with the key as `DISCORD_TOKEN` and the value as the API token from the Discord bot.
"""

import logging
import os

import discord
import openai
from flask import jsonify

import core_functions

# Configure logging for this module
logging.basicConfig(level=logging.INFO)


# Defines if a DB mapping is required
def requires_mapping():
    return False


def setup_routes(app, client, tool_data, assistant_id):
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if not DISCORD_TOKEN:
        raise ValueError("No Discord token found in environment variables")

    # Define the intents
    intents = discord.Intents.default()
    intents.messages = True
    intents.guilds = True

    # Initialize the bot with intents
    bot = discord.Client(intents=intents)

    # Mapping dictionary for Discord user IDs to OpenAI thread IDs
    user_to_thread_id = {}

    @bot.event
    async def on_ready():
        logging.info(f"{bot.user} has connected to Discord!")

    @bot.event
    async def on_message(message):
        # Avoid the bot responding to its own messages
        if message.author == bot.user:
            return

        # Respond only in private DMs
        if not isinstance(message.channel, discord.DMChannel):
            return

        discord_user_id = message.author.id
        user_input = message.content

        # Initialize an empty list to store file IDs
        file_ids = []

        # Check for attachments in the message
        if message.attachments:
            # Ensure the temp directory exists
            os.makedirs("./temp", exist_ok=True)

            for attachment in message.attachments:
                # Define a path for saving the file
                file_path = f"./temp/{attachment.filename}"

                # Save the attachment to the file system
                await attachment.save(file_path)

                # Open the saved file and upload it to the Assistant API
                with open(file_path, "rb") as file:
                    # Upload the file to the Assistant API
                    response = client.files.create(file=file, purpose="assistants")
                    file_ids.append(response.id)

                # Remove the file after uploading
                os.remove(file_path)

        # Retrieve or create OpenAI thread ID for this user
        if discord_user_id not in user_to_thread_id:
            thread = client.beta.threads.create()
            user_to_thread_id[discord_user_id] = thread.id

        thread_id = user_to_thread_id[discord_user_id]
        logging.info(
            f"Received message from Discord user ID: {discord_user_id} for OpenAI thread ID: {thread_id}"
        )

        if not thread_id:
            logging.error("Error: Missing OpenAI thread_id")
            return jsonify({"error": "Missing OpenAI thread_id"}), 400

        logging.info(
            f"Received message: {user_input} for OpenAI thread ID: {thread_id}"
        )

        # Check if there are file IDs and include them in the API call
        if file_ids:
            try:
                client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=user_input,
                    file_ids=file_ids,
                )
            except openai.error.NotFoundError:
                return False  # Thread does not exist
        else:
            try:
                client.beta.threads.messages.create(
                    thread_id=thread_id, role="user", content=user_input
                )
            except openai.error.NotFoundError:
                return False  # Thread does not exist

        run = client.beta.threads.runs.create(
            thread_id=thread_id, assistant_id=assistant_id
        )
        # This processes any possible action requests
        core_functions.process_tool_calls(client, thread_id, run.id, tool_data)

        messages = client.beta.threads.messages.list(thread_id=thread_id)
        response = messages.data[0].content[0].text.value

        # Send response back to Discord
        await message.channel.send(response)

    # Run the Discord bot in a separate thread
    from threading import Thread

    Thread(target=lambda: bot.run(DISCORD_TOKEN)).start()
