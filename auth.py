import logging
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneNumberInvalidError, PhoneCodeInvalidError, PhoneCodeExpiredError
from telethon.tl.functions.auth import SendCodeRequest, SignInRequest
from telethon.sessions import StringSession
from database import db

logger = logging.getLogger(__name__)

class AuthState:
    INITIAL = 'INITIAL'
    REQUEST_API_ID = 'REQUEST_API_ID'
    REQUEST_API_HASH = 'REQUEST_API_HASH'
    REQUEST_PHONE_NUMBER = 'REQUEST_PHONE_NUMBER'
    SEND_OTP = 'SEND_OTP'
    VERIFY_OTP = 'VERIFY_OTP'
    FINALIZE = 'FINALIZE'

async def handle_phone_number_and_otp(event, user_id):
    user_data = await db.get_user_credentials(user_id)
    auth_state = user_data.get('auth_state')

    if auth_state == AuthState.REQUEST_PHONE_NUMBER:
        await handle_phone_number(event, user_id, user_data)
    elif auth_state == AuthState.VERIFY_OTP:
        await handle_otp(event, user_id, user_data)
    else:
        await event.reply("Unexpected state. Please start over with /start")

async def handle_phone_number(event, user_id, user_data):
    phone_number = event.message.message
    api_id = user_data.get('api_id')
    api_hash = user_data.get('api_hash')

    try:
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()

        result = await client(SendCodeRequest(phone_number))
        await db.save_user_credentials(user_id, {
            'phone_number': phone_number,
            'phone_code_hash': result.phone_code_hash,
            'auth_state': AuthState.VERIFY_OTP
        })
        await event.reply("OTP sent to your phone number. Please provide the OTP.")
    except PhoneNumberInvalidError:
        await event.reply("The phone number is invalid. Please check and enter again.")
    except Exception as e:
        logger.error(f"Unexpected error in handle_phone_number: {str(e)}", exc_info=True)
        await event.reply("An error occurred. Please try again or contact support.")
    finally:
        if client:
            await client.disconnect()

async def handle_otp(event, user_id, user_data):
    otp = event.message.message
    phone_number = user_data.get('phone_number')
    phone_code_hash = user_data.get('phone_code_hash')
    api_id = user_data.get('api_id')
    api_hash = user_data.get('api_hash')

    try:
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()

        await client.sign_in(phone=phone_number, code=otp, phone_code_hash=phone_code_hash)
        session_string = client.session.save()
        await db.save_user_credentials(user_id, {'session_string': session_string, 'auth_state': AuthState.FINALIZE})
        await event.reply("Authentication successful! You can now use the bot's features.")
    except PhoneCodeInvalidError:
        await event.reply("The OTP is invalid. Please check and enter again.")
    except PhoneCodeExpiredError:
        await event.reply("The OTP has expired. Please request a new one by sending /retry_otp.")
        await db.save_user_credentials(user_id, {'auth_state': AuthState.REQUEST_PHONE_NUMBER})
    except SessionPasswordNeededError:
        await event.reply("Two-factor authentication is enabled. Please disable it temporarily to use this bot.")
        await db.save_user_credentials(user_id, {'auth_state': AuthState.REQUEST_PHONE_NUMBER})
    except Exception as e:
        logger.error(f"Unexpected error in handle_otp: {str(e)}", exc_info=True)
        await event.reply("An error occurred. Please try again or contact support.")
    finally:
        if client:
            await client.disconnect()

async def retry_otp(event, user_id):
    user_data = await db.get_user_credentials(user_id)
    phone_number = user_data.get('phone_number')
    api_id = user_data.get('api_id')
    api_hash = user_data.get('api_hash')

    try:
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()

        result = await client(SendCodeRequest(phone_number))
        await db.save_user_credentials(user_id, {
            'phone_code_hash': result.phone_code_hash,
            'auth_state': AuthState.VERIFY_OTP
        })
        await event.reply("New OTP sent to your phone number. Please provide the OTP.")
    except Exception as e:
        logger.error(f"Unexpected error in retry_otp: {str(e)}", exc_info=True)
        await event.reply("An error occurred while sending the OTP. Please try again or contact support.")
    finally:
        if client:
            await client.disconnect()

def setup_auth_handlers(bot):
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_command(event):
        user_id = event.sender_id
        await db.save_user_credentials(user_id, {'auth_state': AuthState.REQUEST_API_ID})
        await event.reply("Welcome! Please provide your Telegram API ID.")

    @bot.on(events.NewMessage(pattern=r'^(?!/start|/help|/retry_otp)'))
    async def handle_auth(event):
        user_id = event.sender_id
        user_data = await db.get_user_credentials(user_id)
        auth_state = user_data.get('auth_state')

        if auth_state == AuthState.REQUEST_API_ID:
            api_id = event.message.message
            await db.save_user_credentials(user_id, {'api_id': api_id, 'auth_state': AuthState.REQUEST_API_HASH})
            await event.reply("Got it! Now, please provide your Telegram API Hash.")
        elif auth_state == AuthState.REQUEST_API_HASH:
            api_hash = event.message.message
            await db.save_user_credentials(user_id, {'api_hash': api_hash, 'auth_state': AuthState.REQUEST_PHONE_NUMBER})
            await event.reply("Thank you! Please provide your phone number (with country code).")
        elif auth_state in [AuthState.REQUEST_PHONE_NUMBER, AuthState.VERIFY_OTP]:
            await handle_phone_number_and_otp(event, user_id)
        else:
            await event.reply("Unexpected state. Please start over with /start")

    @bot.on(events.NewMessage(pattern='/retry_otp'))
    async def handle_retry_otp(event):
        await retry_otp(event, event.sender_id)

    logger.info("Authentication handlers set up successfully")
