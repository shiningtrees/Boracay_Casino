import asyncio
import os
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.bot = None
        
        if self.token and self.chat_id:
            self.bot = Bot(token=self.token)
        else:
            print("⚠️ 경고: 텔레그램 설정이 없습니다. 알림이 콘솔에만 출력됩니다.")

    async def send(self, message: str):
        """메시지 전송 (비동기)"""
        # 콘솔에도 항상 출력
        print(f"[Telegram] {message}")
        
        if self.bot:
            try:
                await self.bot.send_message(chat_id=self.chat_id, text=message)
            except Exception as e:
                print(f"❌ 텔레그램 전송 실패: {e}")

    async def send_error(self, error_msg: str):
        """에러 메시지 전송 (강조)"""
        await self.send(f"🚨 시스템 오류 발생:\n{error_msg}")
