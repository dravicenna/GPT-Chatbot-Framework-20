"""
Setting Up Twilio Integration

To integrate a Twilio SMS service into your application, you'll need to first set up a Twilio account and get your credentials. Here's a step-by-step guide:

1. Set Up Twilio:
   - Sign up for a Twilio account at twilio.com.

2. Configure your account:
 - Once your account is set up, head to Message > Services and create a new service
 - Setup your values, continue, and set up your senders. This template currently support SMS and WhatsApp
 - On the integration tab under "Incoming Messages", select "Send a webhook" and add your Replit endpoint URL to the "Request URL" field.  The Endpoint URL depends on the service you want to integrate. Here are the two possibilities: 
 - SMS: https://YOUR_REPLIT_URL.replit.dev/twilio/sms
- WhatsApp: https://YOUR_REPLIT_URL.replit.dev/twilio/whatsapp
- If you struggle to find your Replit URL, simply run it and you will see the "Open in new tab" button.
- Then continue to Add Compliance info and finalize the setup

3. Add the Twilio Credentials to Replit:
   - In your Replit project, open the 'Secrets' tab.
   - Add two new secrets: one with the key as `TWILIO_ACCOUNT_SID` and the value as your Twilio Account SID, and another with the key as `TWILIO_AUTH_TOKEN` and the value as your Auth Token.
   - You will find the SID and auth token via the following link: https://console.twilio.com/?frameUrl=%2Fconsole%3Fx-target-region%3Dus1
   - To read more about it, check out this article: https://support.twilio.com/hc/en-us/articles/223136027-Auth-Tokens-and-How-to-Change-Them
   - Add another secret with the key `TWILIO_PHONE_NUMBER` and the value as your Twilio phone number. Make sure to add it with the + at the beginning.

"""

import os
import logging
from twilio.rest import Client
import openai
from flask import request
import core_functions

# Configure logging
logging.basicConfig(level=logging.INFO)


def requires_mapping():
  return True


def setup_routes(app, client, tool_data, assistant_id):
  # Initialize Twilio
  TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
  TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
  TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')

  if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
    raise ValueError("Twilio credentials not found in environment variables")

  twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

  @app.route('/twilio/sms', methods=['POST'])
  def receive_sms():
    # Extract the message and sender's phone number from the incoming SMS
    from_number = request.values.get('From', None)
    incoming_msg = request.values.get('Body', '')

    logging.info(f"Received SMS from {from_number}: {incoming_msg}")

    db_entry = core_functions.get_chat_mapping("twilio", from_number,
                                               assistant_id)

    thread_id = core_functions.get_value_from_mapping(db_entry, "thread_id")

    if not thread_id:
      thread = client.beta.threads.create()
      thread_id = thread.id

      core_functions.update_chat_mapping("twilio", from_number, assistant_id,
                                         thread.id)
      logging.info(f"New thread created with ID: {thread.id}")

    thread_id = thread_id

    if not thread_id:
      logging.error("Error: Missing OpenAI thread_id")
      return "Error", 400

    try:
      client.beta.threads.messages.create(thread_id=thread_id,
                                          role="user",
                                          content=incoming_msg)
    except openai.error.NotFoundError:
      return "Thread not found", 404

    run = client.beta.threads.runs.create(thread_id=thread_id,
                                          assistant_id=assistant_id)
    core_functions.process_tool_calls(client, thread_id, run.id, tool_data)

    messages = client.beta.threads.messages.list(thread_id=thread_id)
    response = messages.data[0].content[0].text.value

    # Send the response back to the user's phone number
    twilio_client.messages.create(body=response,
                                  from_=TWILIO_PHONE_NUMBER,
                                  to=from_number)

    return "OK", 200

  @app.route('/twilio/whatsapp', methods=['POST'])
  def receive_whatsapp():
    # Extract the message and sender's phone number from the incoming SMS
    from_number = request.values.get('From', None)
    incoming_msg = request.values.get('Body', '')

    logging.info(f"Received SMS from {from_number}: {incoming_msg}")

    db_entry = core_functions.get_chat_mapping("twilio", from_number,
                                               assistant_id)

    thread_id = core_functions.get_value_from_mapping(db_entry, "thread_id")

    if not thread_id:
      thread = client.beta.threads.create()
      thread_id = thread.id

      core_functions.update_chat_mapping("twilio", from_number, assistant_id,
                                         thread_id)

      logging.info(f"New thread created with ID: {thread_id}")

    if not thread_id:
      logging.error("Error: Missing OpenAI thread_id")
      return "Error", 400

    client.beta.threads.messages.create(thread_id=thread_id,
                                        role="user",
                                        content=incoming_msg)

    run = client.beta.threads.runs.create(thread_id=thread_id,
                                          assistant_id=assistant_id)
    core_functions.process_tool_calls(client, thread_id, run.id, tool_data)

    messages = client.beta.threads.messages.list(thread_id=thread_id)
    response = messages.data[0].content[0].text.value

    # Send the response back to the user's phone number
    twilio_client.messages.create(body=response,
                                  from_='whatsapp:' + TWILIO_PHONE_NUMBER,
                                  to=from_number)

    return "OK", 200
