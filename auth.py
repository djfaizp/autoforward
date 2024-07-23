# file: auth.py
import logging
from enum import Enum
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
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

async def start_auth(event, user_id):
    await db.set_user_auth_state(user_id, AuthState.REQUEST_API_ID.value)
    await event.reply("Welcome! Let's start the authentication process. Please enter your API ID:")

async def save_api_id(event, user_id):
    api_id = event.message.text.strip()
    if not api_id.isdigit():
        await event.reply("Invalid API ID. Please enter a valid numeric API ID:")
        return

    await db.save_user_credential(user_id, 'api_id', int(api_id))
    await db.set_user_auth_state(user_id, AuthState.REQUEST_API_HASH.value)
    await event.reply("Great! Now, please enter your API Hash:")

async def save_api_hash(event, user_id):
    api_hash = event.message.text.strip()
    await db.save_user_credential(user_id, 'api_hash', api_hash)
    await db.set_user_auth_state(user_id, AuthState.REQUEST_PHONE_NUMBER.value)
    await event.reply("Excellent! Now, please enter your phone number (including country code):")

async def save_phone_number(event, user_id):
    phone_number = event.message.text.strip()
    await db.save_user_credential(user_id, 'phone_number', phone_number)
    await send_code_request(event, user_id)

async def send_code_request(event, user_id):
    user_data = await db.get_user_credentials(user_id)
    client = TelegramClient(f"sessions/{user_id}", user_data['api_id'], user_data['api_hash'])
    await client.connect()
    try:
        send_result = await client.send_code_request(user_data['phone_number'])
        await db.save_user_credential(user_id, 'phone_code_hash', send_result.phone_code_hash)
        await db.set_user_auth_state(user_id, AuthState.OTP_SENT.value)
        await event.reply("An OTP has been sent to your phone number. Please enter the OTP:")
    except Exception as e:
        logger.error(f"Error sending code request: {str(e)}")
        await event.reply(f"Error sending OTP: {str(e)}. Please try again or start over with /start")
    finally:
        await client.disconnect()

async def authenticate_user(event, user_id):
    otp = event.message.text.strip()
    user_data = await db.get_user_credentials(user_id)
    
    client = TelegramClient(f"sessions/{user_id}", user_data['api_id'], user_data['api_hash'])
    await client.connect()
    
    try:
        await client.sign_in(
            phone=user_data['phone_number'],
            code=otp,
            phone_code_hash=user_data.get('phone_code_hash')
        )
        session_string = client.session.save()
        await db.save_user_credential(user_id, 'session_string', session_string)
        await db.set_user_auth_state(user_id, AuthState.REQUEST_SOURCE_CHANNEL.value)
        await event.reply("Authentication successful! Now, please enter the source channel username or ID:")
    except SessionPasswordNeededError:
        await db.set_user_auth_state(user_id, AuthState.REQUEST_2FA_PASSWORD.value)
        await event.reply("Two-factor authentication is enabled. Please enter your 2FA password:")
    except Exception as e:
        logger.error(f"Error during authentication: {str(e)}")
        await db.set_user_auth_state(user_id, AuthState.VERIFY_OTP.value)
        await event.reply(f"Authentication failed: {str(e)}. Please try again or use /retry_otp to request a new OTP.")
    finally:
        await client.disconnect()

async def handle_2fa_password(event, user_id):
    password = event.message.text.strip()
    user_data = await db.get_user_credentials(user_id)
    
    client = TelegramClient(f"sessions/{user_id}", user_data['api_id'], user_data['api_hash'])
    await client.connect()
    
    try:
        await client.sign_in(password=password)
        session_string = client.session.save()
        await db.save_user_credential(user_id, 'session_string', session_string)
        await db.set_user_auth_state(user_id, AuthState.REQUEST_SOURCE_CHANNEL.value)
        await event.reply("Authentication successful! Now, please enter the source channel username or ID:")
    except Exception as e:
        logger.error(f"Error during 2FA authentication: {str(e)}")
        await event.reply(f"2FA authentication failed: {str(e)}. Please try again.")
    finally:
        await client.disconnect()

async def save_source_channel(event, user_id):
    source_channel = event.message.text.strip()
    await db.save_user_credential(user_id, 'source_channel', source_channel)
    await db.set_user_auth_state(user_id, AuthState.REQUEST_DESTINATION_CHANNEL.value)
    await event.reply("Source channel saved. Now, please enter the destination channel username or ID:")

async def save_destination_channel(event, user_id):
    destination_channel = event.message.text.strip()
    await db.save_user_credential(user_id, 'destination_channel', destination_channel)
    await db.set_user_auth_state(user_id, AuthState.COMPLETED.value)
    await event.reply("Destination channel saved. Authentication process completed. You can now use /start_forwarding to begin forwarding messages.")

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
        
