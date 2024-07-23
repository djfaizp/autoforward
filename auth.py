# file: auth.py

import os
import logging
from enum import Enum
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError
from database import db

logger = logging.getLogger(__name__)

class AuthState(Enum):
    INITIAL = 0
    REQUEST_API_ID = 1
    REQUEST_API_HASH = 2
    REQUEST_PHONE_NUMBER = 3
    OTP_SENT = 4
    VERIFY_OTP = 5
    REQUEST_2FA_PASSWORD = 6
    REQUEST_SOURCE_CHANNEL = 7
    REQUEST_DESTINATION_CHANNEL = 8
    COMPLETED = 9

async def send_code_request(event, user_id):
    user_data = await db.get_user_credentials(user_id)
    session_dir = f"sessions/{user_id}"
    os.makedirs(session_dir, exist_ok=True)
    client = TelegramClient(session_dir, user_data['api_id'], user_data['api_hash'])
    await client.connect()
    try:
        send_result = await client.send_code_request(user_data['phone_number'])
        phone_code_hash = send_result.phone_code_hash
        await db.save_user_credential(user_id, 'phone_code_hash', phone_code_hash)
        await db.set_user_auth_state(user_id, AuthState.OTP_SENT.value)
        await event.reply("An OTP has been sent to your phone number. Please enter the OTP:")
        logger.info(f"New phone_code_hash generated for user {user_id}: {phone_code_hash}")
    except Exception as e:
        logger.error(f"Error sending code request: {str(e)}")
        await event.reply(f"Error sending OTP: {str(e)}. Please try again or start over with /start")
    finally:
        await client.disconnect()

async def authenticate_user(event, user_id):
    otp = event.message.text.strip()
    user_data = await db.get_user_credentials(user_id)
    
    session_dir = f"sessions/{user_id}"
    os.makedirs(session_dir, exist_ok=True)
    client = TelegramClient(session_dir, user_data['api_id'], user_data['api_hash'])
    await client.connect()
    
    try:
        phone_code_hash = user_data.get('phone_code_hash')
        if not phone_code_hash:
            raise ValueError("Phone code hash is missing. Please request a new OTP.")
        
        logger.info(f"Authenticating user {user_id} with phone_code_hash: {phone_code_hash}")
        await client.sign_in(
            phone=user_data['phone_number'],
            code=otp,
            phone_code_hash=phone_code_hash
        )
        session_string = client.session.save()
        await db.save_user_credential(user_id, 'session_string', session_string)
        await db.set_user_auth_state(user_id, AuthState.REQUEST_SOURCE_CHANNEL.value)
        await event.reply("Authentication successful! Now, please enter the source channel username or ID:")
    except PhoneCodeExpiredError:
        logger.error("The confirmation code has expired.")
        await db.set_user_auth_state(user_id, AuthState.VERIFY_OTP.value)
        await event.reply("The confirmation code has expired. Please use /retry_otp to request a new OTP.")
    except SessionPasswordNeededError:
        await db.set_user_auth_state(user_id, AuthState.REQUEST_2FA_PASSWORD.value)
        await event.reply("Two-factor authentication is enabled. Please enter your 2FA password:")
    except Exception as e:
        logger.error(f"Error during authentication: {str(e)}")
        await db.set_user_auth_state(user_id, AuthState.VERIFY_OTP.value)
        await event.reply(f"Authentication failed: {str(e)}. Please try again or use /retry_otp to request a new OTP.")
    finally:
        await client.disconnect()

async def handle_retry_otp(event, user_id):
    await send_code_request(event, user_id)

async def handle_auth(event):
    user_id = event.sender_id
    user_data = await db.get_user_credentials(user_id)

    if user_data is None:
        logger.info(f"No user data found for user ID {user_id}. Skipping auth process.")
        return  # Skip processing if no user data is found

    auth_state = AuthState(user_data.get('auth_state', 0))

    if auth_state == AuthState.REQUEST_API_ID:
        await save_api_id(event, user_id)
    elif auth_state == AuthState.REQUEST_API_HASH:
        await save_api_hash(event, user_id)
    elif auth_state == AuthState.REQUEST_PHONE_NUMBER:
        await save_phone_number(event, user_id)
    elif auth_state in [AuthState.OTP_SENT, AuthState.VERIFY_OTP]:
        await authenticate_user(event, user_id)
    elif auth_state == AuthState.REQUEST_2FA_PASSWORD:
        await handle_2fa_password(event, user_id)
    elif auth_state == AuthState.REQUEST_SOURCE_CHANNEL:
        await save_source_channel(event, user_id)
    elif auth_state == AuthState.REQUEST_DESTINATION_CHANNEL:
        await save_destination_channel(event, user_id)
    else:
        await event.reply("I'm not sure what you're trying to do. Please use /help for available commands.")
            
