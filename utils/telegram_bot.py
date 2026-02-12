import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from dotenv import load_dotenv
import core.config as config

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
        # 콜백 쿼리 핸들러 (버튼 클릭)
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
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
                symbol = active.get('symbol', 'Unknown')
                entry_time = active.get('entry_time', '')
                
                # 실제 현재가 조회
                current_price = self.scheduler.mexc.get_ticker(symbol)
                if current_price:
                    pnl = round((current_price - entry_price) / entry_price * 100, 2)
                    emoji = "🔴" if pnl > 0 else "🔵" # 상승: 빨강, 하락: 파랑 (국내 정서)
                    
                    msg = (
                        f"🎲 **진행 중인 게임**\n"
                        f"Symbol: `{symbol}`\n"
                        f"Entry: `${entry_price}`\n"
                        f"Curr : `${current_price}` ({emoji} {pnl:+.2f}%)\n"
                        f"Time: {entry_time}\n"
                        f"Rule: {config.CYCLE_STRING} 뒤 자동 청산"
                    )
                else:
                    msg = (
                        f"🎲 **진행 중인 게임**\n"
                        f"Symbol: `{symbol}`\n"
                        f"Entry: `${entry_price}`\n"
                        f"⚠️ 현재가 조회 실패\n"
                        f"Time: {entry_time}"
                    )
            else:
                # 쿨타임 정보 추가
                cooldown = self.scheduler.state.get_cooldown()
                if cooldown:
                    msg = f"💤 휴식 중 (쿨타임: ~{cooldown})"
                else:
                    msg = "💤 휴식 중 (진입 대기)"
        else:
            msg = "⚠️ 시스템 연결 대기 중..."
            
        # 답장으로 보내고 로그도 남기려면:
        await update.message.reply_text(msg, parse_mode="Markdown")
        
        # 로그 기록
        from utils.logger import log_telegram_message
        log_telegram_message(self.chat_id, f"[STATUS] {msg}", "REPLY")

    async def sell(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if hasattr(self, 'scheduler') and self.scheduler:
            msg = self.scheduler.force_sell()
            await update.message.reply_text(msg, reply_markup=self.markup)
        else:
            await update.message.reply_text("❌ 시스템 오류: 스케줄러가 연결되지 않았습니다.", reply_markup=self.markup)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = (
            "🎰 **Boracay Casino 사용법**\n\n"
            "**🎮 게임 방식**\n"
            f"• {config.CYCLE_STRING}마다 후보 3개 제시\n"
            f"• {config.SELECTION_TIMEOUT // 60}분 내 버튼으로 선택\n"
            "• 미선택 시 자동 랜덤 선택\n"
            f"• {config.CYCLE_STRING} 후 자동 청산\n\n"
            "**📱 메뉴**\n"
            "📊 **상태**: 현재 베팅 현황과 수익률 확인\n"
            "💰 **매도**: 진행 중인 게임 즉시 청산\n"
            "❓ **도움말**: 이 메시지 다시 보기\n\n"
            "**🎯 종목 선정 기준**\n"
            "• 24시간 변동률: +15% ~ +40%\n"
            "• 거래대금: $100만 이상\n"
            "• 모멘텀 스코어 상위권"
        )
        await update.message.reply_text(msg, reply_markup=self.markup, parse_mode="Markdown")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """버튼 클릭 콜백 처리"""
        query = update.callback_query
        await query.answer()  # 버튼 클릭 응답
        
        data = query.data
        
        if data.startswith("select_"):
            # 종목 선택 처리
            symbol = data.replace("select_", "")
            
            if hasattr(self, 'scheduler') and self.scheduler:
                # 스케줄러에 선택 전달
                success = await self.scheduler.execute_user_selection(symbol, context)
                
                if success:
                    # 버튼 메시지 수정 (선택 완료 표시)
                    await query.edit_message_text(
                        text=f"✅ 선택 완료: {symbol}\n\n진입 중..."
                    )
                else:
                    # 인라인 버튼 메시지 수정
                    await query.edit_message_text(
                        text="❌ 선택 처리 실패. 이미 시간이 초과되었거나 다른 문제가 발생했습니다."
                    )
                    # 하단 메뉴 버튼 복구를 위해 새 메시지 전송
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text="💤 다음 사이클을 기다려주세요.",
                        reply_markup=self.markup
                    )
            else:
                # 인라인 버튼 메시지 수정
                await query.edit_message_text(
                    text="❌ 시스템 오류: 스케줄러가 연결되지 않았습니다."
                )
                # 하단 메뉴 버튼 복구를 위해 새 메시지 전송
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="🔄 봇을 재시작해주세요.",
                    reply_markup=self.markup
                )
    
    async def send_candidate_selection(self, candidates, chat_id=None):
        """후보 선택 버튼과 함께 메시지 전송"""
        if not chat_id:
            chat_id = self.chat_id
        
        if not self.app or not chat_id:
            return
        
        try:
            from utils.logger import log_telegram_message, logger
            
            # 메시지 텍스트 구성
            msg_lines = [
                "🎰 **오늘의 후보 코인이 나왔습니다!**",
                "",
                "📊 아래 3개 중 하나를 선택하세요:",
                ""
            ]
            
            for idx, c in enumerate(candidates, 1):
                msg_lines.append(
                    f"{idx}. **{c['symbol']}**  |  +{c['change']:.2f}%  |  ${c['volume']/1_000_000:.1f}M"
                )
            
            msg_lines.append("")
            msg_lines.append(f"⏰ **{config.SELECTION_TIMEOUT // 60}분 내에 선택하지 않으면 랜덤 선택됩니다!**")
            
            msg = "\n".join(msg_lines)
            
            # 인라인 버튼 생성
            keyboard = []
            for idx, c in enumerate(candidates, 1):
                button_text = f"{idx}. {c['symbol']} (+{c['change']:.1f}%)"
                callback_data = f"select_{c['symbol']}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # 전송
            sent_msg = await self.app.bot.send_message(
                chat_id=chat_id,
                text=msg,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            
            logger.info(f"📤 후보 선택 메시지 전송 완료 (Message ID: {sent_msg.message_id})")
            log_telegram_message(chat_id, msg, "SENT_SELECTION")
            
            return sent_msg.message_id
            
        except Exception as e:
            from utils.logger import logger
            logger.error(f"❌ [Telegram] 후보 전송 실패: {e}")
            return None
    
    async def send_message(self, text):
        """단방향 알림 전송"""
        if self.app and self.chat_id:
            try:
                # 1. 메시지 기록 (JSONL 저장)
                from utils.logger import log_telegram_message, logger
                
                # 2. 전송
                await self.app.bot.send_message(chat_id=self.chat_id, text=text)
                
                # 3. 성공 로그 및 기록
                logger.info(f"📤 텔레그램 전송 완료")
                log_telegram_message(self.chat_id, text, "SENT")
                
            except Exception as e:
                from utils.logger import logger
                logger.error(f"❌ [Telegram] Send Error: {e}")
                log_telegram_message(self.chat_id, text, f"FAIL: {e}")

    def run(self):
        """봇 실행 (Polling)"""
        if self.app:
            print("🤖 Telegram Bot Started...")
            self.app.run_polling()
