import logging
import re
import asyncio
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.auth import SendCodeRequest
from telethon.sessions import StringSession
from telethon.errors.rpcerrorlist import (
    PhoneNumberInvalidError, PhoneCodeInvalidError, 
    PhoneCodeExpiredError, ApiIdInvalidError
)
from database import db

logger = logging.getLogger(__name__)

class AuthState:
    REQUEST_API_ID = 'REQUEST_API_ID'
    REQUEST_API_HASH = 'REQUEST_API_HASH'
    REQUEST_PHONE_NUMBER = 'REQUEST_PHONE_NUMBER'
    OTP_SENT = 'OTP_SENT'
    VERIFY_OTP = 'VERIFY_OTP'
    REQUEST_2FA_PASSWORD = 'REQUEST_2FA_PASSWORD'
    REQUEST_SOURCE_CHANNEL = 'REQUEST_SOURCE_CHANNEL'
    REQUEST_DESTINATION_CHANNEL = 'REQUEST_DESTINATION_CHANNEL'
    FINALIZE = 'FINALIZE'

async def start_auth(event, user_id):
    await db.save_user_credentials(user_id, {'auth_state': AuthState.REQUEST_API_ID})
    await event.reply("Welcome! Please provide your Telegram API ID (must be a number).")

async def save_api_id(event, user_id):
    api_id = event.message.message
    if not api_id.isdigit():
        await event.reply("Invalid API ID. Please enter a numeric value.")
        return
    
    await db.save_user_credentials(user_id, {'api_id': int(api_id), 'auth_state': AuthState.REQUEST_API_HASH})
    await event.reply("Got it! Now, please provide your Telegram API Hash (32 character string).")

async def save_api_hash(event, user_id):
    api_hash = event.message.message
    if not re.match(r'^[a-fA-F0-9]{32}$', api_hash):
        await event.reply("Invalid API Hash. Please enter a 32 character hexadecimal string.")
        return
    
    await db.save_user_credentials(user_id, {'api_hash': api_hash, 'auth_state': AuthState.REQUEST_PHONE_NUMBER})
    await event.reply("Thank you! Please provide your phone number (with country code, e.g., +1234567890).")

async def save_phone_number(event, user_id):
    phone_number = event.message.message
    if not re.match(r'^\+\d{10,14}$', phone_number):
        await event.reply("Invalid phone number format. Please enter the number with country code (e.g., +1234567890).")
        return

    await db.save_user_credentials(user_id, {'phone_number': phone_number, 'auth_state': AuthState.OTP_SENT})
    await authenticate_user(event, user_id)

async def authenticate_user(event, user_id):
    user_data = await db.get_user_credentials(user_id)
    client = TelegramClient(StringSession(), user_data['api_id'], user_data['api_hash'])
    
    await client.connect()
    try:
        await client.send_code_request(user_data['phone_number'])
        await event.reply("OTP sent. Please enter the code:")
        
        for _ in range(3):  # Allow 3 attempts
            try:
                otp = await wait_for_otp(event)
                await client.sign_in(user_data['phone_number'], otp)
                session_string = client.session.save()
                await db.save_user_credentials(user_id, {'session_string': session_string, 'auth_state': AuthState.REQUEST_SOURCE_CHANNEL})
                await event.reply("Authentication successful! Please provide the source channel ID.")
                return True
            except PhoneCodeInvalidError:
                await event.reply("Invalid OTP. Please try again.")
            except SessionPasswordNeededError:
                await db.save_user_credentials(user_id, {'auth_state': AuthState.REQUEST_2FA_PASSWORD})
                await event.reply("Two-factor authentication is enabled. Please enter your 2FA password.")
                return await handle_2fa(event, user_id, client)
        
        await event.reply("Too many failed attempts. Please restart the process with /start.")
        return False
    
    except ApiIdInvalidError:
        await event.reply("The provided API ID/Hash combination is invalid. Please check and try again with /start.")
        await db.save_user_credentials(user_id, {'auth_state': AuthState.REQUEST_API_ID})
    except PhoneNumberInvalidError:
        await event.reply("The phone number is invalid. Please check and try again with /start.")
        await db.save_user_credentials(user_id, {'auth_state': AuthState.REQUEST_PHONE_NUMBER})
    except FloodWaitError as e:
        await event.reply(f"Too many attempts. Please try again after {e.seconds} seconds.")
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        await event.reply(f"An unexpected error occurred. Please try again later. Error: {str(e)}")
    finally:
        await client.disconnect()

async def wait_for_otp(event):
    try:
        response = await event.client.wait_for(events.NewMessage(from_users=event.sender_id), timeout=300)
        return response.message.text
    except asyncio.TimeoutError:
        await event.reply("OTP input timed out. Please restart the authentication process with /start.")
        raise

async def handle_2fa(event, user_id, client):
    try:
        password = await wait_for_otp(event)  # Reusing the wait_for_otp function for password input
        await client.sign_in(password=password)
        session_string = client.session.save()
        await db.save_user_credentials(user_id, {'session_string': session_string, 'auth_state': AuthState.REQUEST_SOURCE_CHANNEL})
        await event.reply("Two-factor authentication successful! Please provide the source channel ID.")
        return True
    except Exception as e:
        logger.error(f"2FA error: {str(e)}")
        await event.reply(f"Two-factor authentication failed. Please try again with /start. Error: {str(e)}")
        return False

async def save_source_channel(event, user_id):
    source_channel = event.message.message
    if not source_channel.lstrip('-').isdigit():
        await event.reply("Invalid channel ID. Please enter a numeric value (positive or negative).")
        return
    
    await db.save_user_credentials(user_id, {
        'source_channel': int(source_channel), 
        'auth_state': AuthState.REQUEST_DESTINATION_CHANNEL
    })
    await event.reply("Got it! Now, please provide the destination channel ID.")

async def save_destination_channel(event, user_id):
    destination_channel = event.message.message
    if not destination_channel.lstrip('-').isdigit():
        await event.reply("Invalid channel ID. Please enter a numeric value (positive or negative).")
        return
    
    await db.save_user_credentials(user_id, {
        'destination_channel': int(destination_channel), 
        'auth_state': AuthState.FINALIZE
    })
    await event.reply("Thank you! Your setup is complete. You can now use /start_forwarding to begin forwarding messages.")

async def handle_retry_otp(event, user_id):
    user_data = await db.get_user_credentials(user_id)
    if user_data.get('auth_state') in [AuthState.OTP_SENT, AuthState.VERIFY_OTP]:
        await authenticate_user(event, user_id)
    else:
        await event.reply("You're not at the OTP verification stage. Please complete the previous steps first.")
