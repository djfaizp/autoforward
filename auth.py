#file: auth.py
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

    async def handle_phone_number_and_otp(event, user_id):
        user_data = await db.get_user_credentials(user_id)
        phone_number = user_data.get('phone_number')
        api_id = user_data.get('api_id')
        api_hash = user_data.get('api_hash')
    
        if not phone_number or not api_id or not api_hash:
            await event.reply("Missing credentials. Please start over with /start")
            return
    
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
    
        try:
            if not await client.is_user_authorized():
                await client.send_code_request(phone_number)
                await event.reply("Please enter the code you received:")
                # Wait for the next message from the user to get the code
                response = await client.wait_event(events.NewMessage(from_users=user_id))
                code = response.message.text.strip()
                await client.sign_in(phone_number, code)
    
            # If we reach here, the client is authenticated
            session_string = client.session.save()
            await db.save_user_credentials(user_id, {'session_string': session_string})
            await event.reply("Authentication successful! You can now use the bot's features.")
    
        except Exception as e:
            logger.error(f"Error in handle_phone_number_and_otp: {str(e)}")
            await event.reply(f"An error occurred: {str(e)}")
        finally:
            await client.disconnect()
    async def retry_otp(self, event, user_id):
        user_data = await db.get_user_credentials(user_id)
        phone_number = user_data.get('phone_number')

        client = self.clients.get(user_id)
        if not client:
            await event.reply("Session expired. Please start over with /start")
            return

        try:
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
    
