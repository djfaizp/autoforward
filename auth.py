import logging
from telethon import TelegramClient, events
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

class AuthManager:
    def __init__(self, bot):
        self.bot = bot
        self.clients = {}  # Store active TelegramClient instances

    async def start_auth(self, event, user_id):
        await db.save_user_credentials(user_id, {'auth_state': AuthState.REQUEST_API_ID})
        await event.reply("Welcome! Please provide your Telegram API ID.")

    async def handle_auth_step(self, event, user_id):
        user_data = await db.get_user_credentials(user_id)
        auth_state = user_data.get('auth_state', AuthState.INITIAL)

        handlers = {
            AuthState.REQUEST_API_ID: self.save_api_id,
            AuthState.REQUEST_API_HASH: self.save_api_hash,
            AuthState.REQUEST_PHONE_NUMBER: self.save_phone_number,
            AuthState.VERIFY_OTP: self.verify_otp,
        }

        handler = handlers.get(auth_state)
        if handler:
            await handler(event, user_id, user_data)
        else:
            await event.reply("Unexpected state. Please start over with /start")

    async def save_api_id(self, event, user_id, user_data):
        api_id = event.message.message
        await db.save_user_credentials(user_id, {'api_id': api_id, 'auth_state': AuthState.REQUEST_API_HASH})
        await event.reply("Got it! Now, please provide your Telegram API Hash.")

    async def save_api_hash(self, event, user_id, user_data):
        api_hash = event.message.message
        await db.save_user_credentials(user_id, {'api_hash': api_hash, 'auth_state': AuthState.REQUEST_PHONE_NUMBER})
        await event.reply("Thank you! Please provide your phone number (with country code).")

    async def save_phone_number(self, event, user_id, user_data):
        phone_number = event.message.message
        api_id = user_data.get('api_id')
        api_hash = user_data.get('api_hash')

        try:
            client = TelegramClient(StringSession(), api_id, api_hash, phone=phone_number)
            await client.connect()
            self.clients[user_id] = client  # Store the client instance

            result = await client(SendCodeRequest(phone_number))
            await db.save_user_credentials(user_id, {
                'phone_number': phone_number,
                'phone_code_hash': result.phone_code_hash,
                'auth_state': AuthState.VERIFY_OTP
            })
            await event.reply("OTP sent to your phone number. Please provide the OTP.")
        except PhoneNumberInvalidError:
            await event.reply("The phone number is invalid. Please check and enter again.")
            await db.save_user_credentials(user_id, {'auth_state': AuthState.REQUEST_PHONE_NUMBER})
        except Exception as e:
            logger.error(f"Unexpected error in save_phone_number: {str(e)}", exc_info=True)
            await event.reply("An error occurred. Please try again or contact support.")
            await db.save_user_credentials(user_id, {'auth_state': AuthState.REQUEST_PHONE_NUMBER})
        finally:
            if user_id not in self.clients:
                await self.disconnect_client(user_id)

    async def verify_otp(self, event, user_id, user_data):
        otp = event.message.message
        phone_number = user_data.get('phone_number')
        phone_code_hash = user_data.get('phone_code_hash')

        client = self.clients.get(user_id)
        if not client:
            await event.reply("Session expired. Please start over with /start")
            return

        try:
            await client(SignInRequest(phone_number, phone_code_hash, otp))
            session_string = client.session.save()
            await db.save_user_credentials(user_id, {'session_string': session_string, 'auth_state': AuthState.FINALIZE})
            await event.reply("Authentication successful! You can now use the bot's features.")
        except PhoneCodeInvalidError:
            await event.reply("The OTP is invalid. Please check and enter again.")
        except PhoneCodeExpiredError:
            await event.reply("The OTP has expired. Please request a new one by sending /retry_otp.")
            await db.save_user_credentials(user_id, {'auth_state': AuthState.SEND_OTP})
        except SessionPasswordNeededError:
            await event.reply("Two-factor authentication is enabled. Please disable it temporarily to use this bot.")
            await db.save_user_credentials(user_id, {'auth_state': AuthState.REQUEST_PHONE_NUMBER})
        except Exception as e:
            logger.error(f"Unexpected error in verify_otp: {str(e)}", exc_info=True)
            await event.reply("An error occurred. Please try again or contact support.")
            await db.save_user_credentials(user_id, {'auth_state': AuthState.SEND_OTP})
        finally:
            await self.disconnect_client(user_id)

    async def retry_otp(self, event, user_id):
        user_data = await db.get_user_credentials(user_id)
        phone_number = user_data.get('phone_number')
        api_id = user_data.get('api_id')
        api_hash = user_data.get('api_hash')

        try:
            client = TelegramClient(StringSession(), api_id, api_hash, phone=phone_number)
            await client.connect()
            self.clients[user_id] = client

            result = await client(SendCodeRequest(phone_number))
            await db.save_user_credentials(user_id, {
                'phone_code_hash': result.phone_code_hash,
                'auth_state': AuthState.VERIFY_OTP
            })
            await event.reply("New OTP sent to your phone number. Please provide the OTP.")
        except Exception as e:
            logger.error(f"Unexpected error in retry_otp: {str(e)}", exc_info=True)
            await event.reply("An error occurred while sending the OTP. Please try again or contact support.")
            await self.disconnect_client(user_id)

    async def disconnect_client(self, user_id):
        client = self.clients.pop(user_id, None)
        if client:
            await client.disconnect()

def setup_auth_handlers(bot):
    auth_manager = AuthManager(bot)

    @bot.on(events.NewMessage(pattern='/start'))
    async def start_command(event):
        await auth_manager.start_auth(event, event.sender_id)

    @bot.on(events.NewMessage(pattern=r'^(?!/start|/help|/retry_otp)'))
    async def handle_auth(event):
        await auth_manager.handle_auth_step(event, event.sender_id)

    @bot.on(events.NewMessage(pattern='/retry_otp'))
    async def handle_retry_otp(event):
        await auth_manager.retry_otp(event, event.sender_id)

    logger.info("Authentication handlers set up successfully")
