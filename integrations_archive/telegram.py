"""
Setting Up Telegram Integration

To integrate a Telegram bot into your application, you'll need to first create the bot on Telegram and then configure your environment (like Replit) to use it. Here's a step-by-step guide:

1. Create a Telegram Bot:
   - Start by searching for 'BotFather' on Telegram. This is an official bot that Telegram uses to create and manage other bots.
   - Send the '/newbot' command to BotFather. It will guide you through creating your bot. You'll need to choose a name and a username for your bot.
   - Upon successful creation, BotFather will provide you with an API token. This token is essential for your bot's connection to the Telegram API.

2. Add the API Key to Replit:
   - Go to your Replit project where you intend to use the Telegram bot.
   - Open the 'Secrets' tab (usually represented by a lock icon).
   - Create a new secret with the key as `TELEGRAM_TOKEN` and the value as the API token provided by BotFather.
"""

import os
import logging
import telebot
import core_functions

# Configure logging
logging.basicConfig(level=logging.INFO)


# Defines if a DB mapping is required
def requires_mapping():
  return True


def setup_routes(app, client, tool_data, assistant_id):
  # Initialize Telegram
  TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
  if not TELEGRAM_TOKEN:
    raise ValueError("No Telegram token found in environment variables")
  bot = telebot.TeleBot(TELEGRAM_TOKEN)

  @bot.message_handler(commands=['start'])
  def send_welcome(message):
    telegram_chat_id = message.chat.id
    logging.info("Starting a new conversation...")

    chat_mapping = core_functions.get_chat_mapping("telegram",
                                                   telegram_chat_id,
                                                   assistant_id)

    # Check if this chat ID already has a thread ID
    if not chat_mapping:
      thread = client.beta.threads.create()

      # Save the mapping
      core_functions.update_chat_mapping("telegram", telegram_chat_id,
                                         assistant_id, thread.id)

      logging.info(f"New thread created with ID: {thread.id}")

    bot.reply_to(message, "Howdy, how can I help you?")

  @bot.message_handler(func=lambda message: True)
  def echo_all(message):
    telegram_chat_id = message.chat.id
    user_input = message.text

    db_entry = core_functions.get_chat_mapping("telegram", telegram_chat_id,
                                               assistant_id)

    thread_id = core_functions.get_value_from_mapping(db_entry, "thread_id")

    if not thread_id:

      thread = client.beta.threads.create()

      # Save the mapping
      core_functions.update_chat_mapping("telegram", telegram_chat_id,
                                         assistant_id, thread.id)

      thread_id = thread.id

      logging.info(f"XXXXXX: {thread_id}")

      if not thread_id:
        logging.error("Error: Missing OpenAI thread_id")
        return

    logging.info(
        f"Received message: {user_input} for OpenAI thread ID: {thread_id}")

    client.beta.threads.messages.create(thread_id=thread_id,
                                        role="user",
                                        content=user_input)

    run = client.beta.threads.runs.create(thread_id=thread_id,
                                          assistant_id=assistant_id)
    # This processes any possible action requests
    core_functions.process_tool_calls(client, thread_id, run.id, tool_data)

    messages = client.beta.threads.messages.list(thread_id=thread_id)
    response = messages.data[0].content[0].text.value

    # Use the original Telegram chat ID here, not the OpenAI thread ID
    bot.send_message(telegram_chat_id, response, parse_mode='Markdown')

  # Start polling in a separate thread
  from threading import Thread
  Thread(target=bot.polling).start()
