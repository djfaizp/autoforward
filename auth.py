from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    PhoneCodeInvalidError, PhoneCodeExpiredError,
    SessionPasswordNeededError, PasswordHashInvalidError,
    FloodWaitError
)
from telethon.tl.custom import Button
from telethon import events
from database import db
import logging
import asyncio

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
    client = await send_otp(event, user_id)
    await verify_otp(event, user_id, client)

async def send_otp(event, user_id):
    user_data = await db.get_user_credentials(user_id)
    client = TelegramClient(StringSession(), user_data['api_id'], user_data['api_hash'])
    await client.connect()
    try:
        sent_code = await client.send_code_request(user_data['phone_number'])
        await db.save_user_credentials(user_id, {
            'phone_code_hash': sent_code.phone_code_hash,
            'auth_state': AuthState.VERIFY_OTP
        })
        await event.reply("❖ An OTP has been sent to your phone. Please enter the OTP to verify:", buttons=[
            Button.inline('Retry OTP', b'retry_otp')
        ])
        return client  # Return client to keep it connected
    except Exception as e:
        await client.disconnect()
        logger.error(f"Error sending OTP: {str(e)}")
        await event.reply(f"❖ Failed to send OTP: {str(e)}")

async def verify_otp(event, user_id, client):
    otp = event.text
    user_data = await db.get_user_credentials(user_id)
    try:
        await client.sign_in(phone=user_data['phone_number'], code=otp, phone_code_hash=user_data['phone_code_hash'])
        session_string = client.session.save()
        await db.save_user_credentials(user_id, {'session_string': session_string, 'auth_state': AuthState.REQUEST_SOURCE_CHANNEL})
        await request_source_channel(event, user_id)
    except PhoneCodeInvalidError:
        await event.reply("❖ The OTP you provided is invalid. Please try again.", buttons=[
            Button.inline('Retry OTP', b'retry_otp')
        ])
    except PhoneCodeExpiredError:
        await event.reply("❖ The OTP has expired. Please request a new OTP and try again.", buttons=[
            Button.inline('Retry OTP', b'retry_otp')
        ])
    except SessionPasswordNeededError:
        await request_2fa_password(event, user_id, client)
    except FloodWaitError as e:
        logger.warning(f"Flood wait error: must wait for {e.seconds} seconds.")
        await asyncio.sleep(e.seconds)
        await verify_otp(event, user_id, client)  # Retry after waiting
    except Exception as e:
        logger.error(f"Error verifying OTP: {str(e)}")
        await event.reply(f"❖ OTP verification failed: {str(e)}. Please try again.", buttons=[
            Button.inline('Retry OTP', b'retry_otp')
        ])

async def request_2fa_password(event, user_id, client):
    await event.reply("❖ Two-factor authentication is enabled. Please enter your 2FA password:")
    user_response = await event.get_response()
    await verify_2fa_password(event, user_id, user_response.text, client)

async def verify_2fa_password(event, user_id, password, client):
    user_data = await db.get_user_credentials(user_id)
    try:
        await client.sign_in(password=password)
        session_string = client.session.save()
        await db.save_user_credentials(user_id, {'session_string': session_string, 'auth_state': AuthState.REQUEST_SOURCE_CHANNEL})
        await request_source_channel(event, user_id)
    except PasswordHashInvalidError:
        await event.reply("❖ The password you provided is incorrect. Please try again.")
        await request_2fa_password(event, user_id, client)
    except FloodWaitError as e:
        logger.warning(f"Flood wait error: must wait for {e.seconds} seconds.")
        await asyncio.sleep(e.seconds)
        await verify_2fa_password(event, user_id, password, client)  # Retry after waiting
    except Exception as e:
        logger.error(f"Error verifying 2FA password: {str(e)}")
        await event.reply(f"❖ 2FA password verification failed: {str(e)}. Please try again.")

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

# The main function that manages the authentication process
async def authenticate(event, user_id):
    client = await send_otp(event, user_id)
    if client:
        user_data = await db.get_user_credentials(user_id)
        auth_state = user_data.get('auth_state')
        while auth_state not in [AuthState.REQUEST_SOURCE_CHANNEL, AuthState.FINALIZE]:
            if auth_state == AuthState.VERIFY_OTP:
                await verify_otp(event, user_id, client)
            elif auth_state == AuthState.REQUEST_SOURCE_CHANNEL:
                await request_source_channel(event, user_id)
            elif auth_state == AuthState.REQUEST_DESTINATION_CHANNEL:
                await request_destination_channel(event, user_id)
            elif auth_state == AuthState.FINALIZE:
                await finalize_auth(event, user_id)
            user_data = await db.get_user_credentials(user_id)
            auth_state = user_data.get('auth_state')
        await client.disconnect()

# Define handle_retry_otp function
@events.register(events.CallbackQuery(data=b'retry_otp'))
async def handle_retry_otp(event):
    user_id = event.sender_id
    client = await send_otp(event, user_id)
    if client:
        user_data = await db.get_user_credentials(user_id)
        auth_state = user_data.get('auth_state')
        if auth_state == AuthState.VERIFY_OTP:
            await verify_otp(event, user_id, client)
            
