import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

load_dotenv()

class CasinoBot:
    def __init__(self, post_init=None):
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.app = None
        
        # 기본 키보드 버튼 설정
        self.keyboard = [
            ["📊 상태", "💰 매도"],
            ["❓ 도움말"]
        ]
        self.markup = ReplyKeyboardMarkup(self.keyboard, resize_keyboard=True)
        
        if not self.token:
            print("⚠️ [Telegram] Token is missing!")
            return

        builder = Application.builder().token(self.token)
        if post_init:
            builder.post_init(post_init)
        self.app = builder.build()
        
        self.add_handlers()

    def add_handlers(self):
        """명령어 핸들러 등록"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("status", self.status))
        self.app.add_handler(CommandHandler("help", self.help))
        # 텍스트 메시지 핸들러
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        
        if text == "💰 매도" or text == "매도":
            await self.sell(update, context)
        elif text == "📊 상태" or text == "상태":
            await self.status(update, context)
        elif text == "❓ 도움말" or text == "도움말":
            await self.help(update, context)
        else:
            # 인식하지 못한 명령어일 경우 안내 메시지 출력
            msg = "🤔 알 수 없는 명령어입니다. 아래 버튼을 선택해주세요."
            await update.message.reply_text(msg, reply_markup=self.markup)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🎰 Boracay Casino 입장! \n하단 메뉴를 이용하여 카지노를 제어할 수 있습니다.",
            reply_markup=self.markup
        )

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # 스케줄러 상태 조회
        msg = "📊 현재 상태 조회 중..."
        
        if hasattr(self, 'scheduler') and self.scheduler:
            active = self.scheduler.state.get_active_bet()
            if active:
                entry_price = active.get('entry_price', 0)
                # 현재가 조회 시도 (스케줄러나 커넥터 통해)
                # 간단히 정보만 표시
                msg = (
                    f"🎲 **진행 중인 게임**\n"
                    f"Symbol: {active['symbol']}\n"
                    f"Entry: {entry_price}\n"
                    f"Time: {active['entry_time']}\n"
                    f"Rule: 48h Auto Exit"
                )
            else:
                msg = "💤 현재 진행 중인 베팅이 없습니다. (휴식 중)"
        else:
            msg = "⚠️ 시스템 연결 대기 중..."
            
        await update.message.reply_text(msg, reply_markup=self.markup)

    async def sell(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if hasattr(self, 'scheduler') and self.scheduler:
            msg = self.scheduler.force_sell()
            await update.message.reply_text(msg, reply_markup=self.markup)
        else:
            await update.message.reply_text("❌ 시스템 오류: 스케줄러가 연결되지 않았습니다.", reply_markup=self.markup)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = (
            "🎰 **Boracay Casino 사용법**\n\n"
            "📊 **상태**: 현재 베팅 현황과 수익률을 확인합니다.\n"
            "💰 **매도**: 진행 중인 게임을 즉시 종료하고 청산합니다. (조기 퇴근)\n"
            "❓ **도움말**: 이 메시지를 다시 봅니다.\n\n"
            "※ 매일 정오(12:00)에 자동으로 칩이 투입됩니다."
        )
        await update.message.reply_text(msg, reply_markup=self.markup)

    async def send_message(self, text):
        """단방향 알림 전송"""
        if self.app and self.chat_id:
            try:
                # 단방향 알림에는 버튼 마크업을 강제하지 않음 (사용자가 끄집어낼 수 있으므로)
                await self.app.bot.send_message(chat_id=self.chat_id, text=text)
            except Exception as e:
                print(f"❌ [Telegram] Send Error: {e}")

    def run(self):
        """봇 실행 (Polling)"""
        if self.app:
            print("🤖 Telegram Bot Started...")
            self.app.run_polling()
