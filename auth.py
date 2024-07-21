# file: auth.py
import logging
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.auth import SendCodeRequest, SignInRequest
from telethon.sessions import StringSession
from telethon.errors.rpcerrorlist import PhoneNumberInvalidError, PhoneCodeInvalidError, PhoneCodeExpiredError
from database import db

logger = logging.getLogger(__name__)

class AuthState:
    REQUEST_API_ID = 'REQUEST_API_ID'
    REQUEST_API_HASH = 'REQUEST_API_HASH'
    REQUEST_PHONE_NUMBER = 'REQUEST_PHONE_NUMBER'
    VERIFY_OTP = 'VERIFY_OTP'
    REQUEST_SOURCE_CHANNEL = 'REQUEST_SOURCE_CHANNEL'
    REQUEST_DESTINATION_CHANNEL = 'REQUEST_DESTINATION_CHANNEL'
    FINALIZE = 'FINALIZE'

async def start_auth(event, user_id):
    await db.save_user_credentials(user_id, {'auth_state': AuthState.REQUEST_API_ID})
    await event.reply("Welcome! Please provide your Telegram API ID.")

async def save_api_id(event, user_id):
    api_id = event.message.message
    await db.save_user_credentials(user_id, {'api_id': api_id, 'auth_state': AuthState.REQUEST_API_HASH})
    await event.reply("Got it! Now, please provide your Telegram API Hash.")

async def save_api_hash(event, user_id):
    api_hash = event.message.message
    await db.save_user_credentials(user_id, {'api_hash': api_hash, 'auth_state': AuthState.REQUEST_PHONE_NUMBER})
    await event.reply("Thank you! Please provide your phone number (with country code).")

async def save_phone_number(event, user_id):
    phone_number = event.message.message
    user_data = await db.get_user_credentials(user_id)
    api_id = user_data.get('api_id')
    api_hash = user_data.get('api_hash')

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    try:
        result = await client(SendCodeRequest(phone_number))
        await db.save_user_credentials(user_id, {'phone_number': phone_number, 'phone_code_hash': result.phone_code_hash, 'auth_state': AuthState.VERIFY_OTP})
        await event.reply("OTP sent to your phone number. Please provide the OTP.")
    except PhoneNumberInvalidError:
        await event.reply("The phone number is invalid. Please check and enter again.")
    finally:
        await client.disconnect()

async def verify_otp(event, user_id, client=None):
    otp = event.message.message
    user_data = await db.get_user_credentials(user_id)
    phone_number = user_data.get('phone_number')
    phone_code_hash = user_data.get('phone_code_hash')

    if client is None:
        api_id = user_data.get('api_id')
        api_hash = user_data.get('api_hash')
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()

    try:
        await client(SignInRequest(phone_number, phone_code_hash, otp))
        session_string = client.session.save()
        await db.save_user_credentials(user_id, {'session_string': session_string, 'auth_state': AuthState.REQUEST_SOURCE_CHANNEL})
        await event.reply("You are authenticated! Please provide the source channel ID.")
    except PhoneCodeInvalidError:
        await event.reply("The OTP is invalid. Please check and enter again.")
    except PhoneCodeExpiredError:
        await event.reply("The OTP has expired. Please request a new one by sending /start.")
    finally:
        await client.disconnect()

async def send_otp(event, user_id):
    user_data = await db.get_user_credentials(user_id)
    phone_number = user_data.get('phone_number')
    api_id = user_data.get('api_id')
    api_hash = user_data.get('api_hash')

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    try:
        result = await client(SendCodeRequest(phone_number))
        await db.save_user_credentials(user_id, {'phone_code_hash': result.phone_code_hash, 'auth_state': AuthState.VERIFY_OTP})
        await event.reply("OTP sent to your phone number. Please provide the OTP.")
    except PhoneNumberInvalidError:
        await event.reply("The phone number is invalid. Please check and enter again.")
    finally:
        await client.disconnect()

    return client

async def handle_retry_otp(event):
    user_id = event.sender_id
    user_data = await db.get_user_credentials(user_id)
    if user_data.get('auth_state') == AuthState.VERIFY_OTP:
        client = await send_otp(event, user_id)
        await event.reply("OTP sent to your phone number again. Please provide the OTP.")
    else:
        await event.reply("Your current state does not allow resending OTP. Please complete the previous steps first.")

async def save_source_channel(event, user_id):
    source_channel = event.message.message
    await db.save_user_credentials(user_id, {'source_channel': source_channel, 'auth_state': AuthState.REQUEST_DESTINATION_CHANNEL})
    await event.reply("Got it! Now, please provide the destination channel ID.")

async def save_destination_channel(event, user_id):
    destination_channel = event.message.message
    await db.save_user_credentials(user_id, {'destination_channel': destination_channel, 'auth_state': AuthState.FINALIZE})
    await event.reply("Thank you! Your setup is complete. You can now use /start_forwarding to begin forwarding messages.")
    
