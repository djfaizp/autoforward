# auth.py
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from database import db
import logging

logger = logging.getLogger(__name__)

class AuthState:
    REQUEST_API_ID = "REQUEST_API_ID"
    REQUEST_API_HASH = "REQUEST_API_HASH"
    REQUEST_PHONE_NUMBER = "REQUEST_PHONE_NUMBER"
    SEND_OTP = "SEND_OTP"
    VERIFY_OTP = "VERIFY_OTP"
    REQUEST_SOURCE_CHANNEL = "REQUEST_SOURCE_CHANNEL"
    REQUEST_DESTINATION_CHANNEL = "REQUEST_DESTINATION_CHANNEL"
    FINALIZE = "FINALIZE"

async def start_auth(event, user_id):
    await request_api_id(event, user_id)

async def request_api_id(event, user_id):
    await event.reply("❖ Please enter your API_ID to proceed:")
    await db.save_user_credentials(user_id, {'auth_state': AuthState.REQUEST_API_ID})

async def save_api_id(event, user_id):
    api_id = event.text
    await db.save_user_credentials(user_id, {'api_id': api_id, 'auth_state': AuthState.REQUEST_API_HASH})
    await request_api_hash(event, user_id)

async def request_api_hash(event, user_id):
    await event.reply("❖ Now enter your API_HASH to proceed √")

async def save_api_hash(event, user_id):
    api_hash = event.text
    await db.save_user_credentials(user_id, {'api_hash': api_hash, 'auth_state': AuthState.REQUEST_PHONE_NUMBER})
    await request_phone_number(event, user_id)

async def request_phone_number(event, user_id):
    await event.reply("❖ Please send your phone number in international format like +9113138737832:")

async def save_phone_number(event, user_id):
    phone_number = event.text
    await db.save_user_credentials(user_id, {'phone_number': phone_number, 'auth_state': AuthState.SEND_OTP})
    await send_otp(event, user_id)

async def send_otp(event, user_id):
    user_data = await db.get_user_credentials(user_id)
    client = TelegramClient(StringSession(), user_data['api_id'], user_data['api_hash'])
    await client.connect()
    await client.send_code_request(user_data['phone_number'])
    await client.disconnect()
    await db.save_user_credentials(user_id, {'auth_state': AuthState.VERIFY_OTP})
    await event.reply("❖ An OTP has been sent to your phone. Please enter the OTP to verify:")

async def verify_otp(event, user_id):
    otp = event.text
    user_data = await db.get_user_credentials(user_id)
    client = TelegramClient(StringSession(), user_data['api_id'], user_data['api_hash'])
    await client.connect()
    try:
        await client.sign_in(user_data['phone_number'], otp)
        session_string = client.session.save()
        await db.save_user_credentials(user_id, {'session_string': session_string, 'auth_state': AuthState.REQUEST_SOURCE_CHANNEL})
        await request_source_channel(event, user_id)
    except Exception as e:
        await event.reply(f"❖ OTP verification failed: {str(e)}. Please try again.")
    await client.disconnect()

async def request_source_channel(event, user_id):
    await event.reply("❖ Please enter the source channel ID:")

async def save_source_channel(event, user_id):
    source_channel = event.text
    await db.save_user_credentials(user_id, {'source_channel': source_channel, 'auth_state': AuthState.REQUEST_DESTINATION_CHANNEL})
    await request_destination_channel(event, user_id)

async def request_destination_channel(event, user_id):
    await event.reply("❖ Please enter the destination channel ID:")

async def save_destination_channel(event, user_id):
    destination_channel = event.text
    await db.save_user_credentials(user_id, {'destination_channel': destination_channel, 'auth_state': AuthState.FINALIZE})
    await finalize_auth(event, user_id)

async def finalize_auth(event, user_id):
    await db.save_user_credentials(user_id, {'auth_state': None})
    await event.reply("❖ Authentication complete. You are now ready to use the bot!")
