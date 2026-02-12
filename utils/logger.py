import logging
import os
import json
from datetime import datetime

# 전역 시퀀스 카운터 (싱글톤처럼 사용)
class GlobalSequence:
    _seq = 0
    
    @classmethod
    def next(cls):
        cls._seq += 1
        return cls._seq
    
    @classmethod
    def current(cls):
        return cls._seq

class SequenceFilter(logging.Filter):
    def filter(self, record):
        # 로거가 호출될 때마다 시퀀스 증가 (단, 텔레그램 로깅과 맞추기 위해 조정 필요할 수 있음)
        # 하지만 여기서는 단순하게 로거 호출 순서대로 번호를 매김
        # 텔레그램 메시지 ID와 별개로, '로그 줄 번호'로 사용
        record.seq = GlobalSequence.next()
        return True

def setup_logger(name="BoracayCasino"):
    # 로그 디렉토리 생성
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 로거 설정
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    seq_filter = SequenceFilter()
    logger.addFilter(seq_filter)

    formatter = logging.Formatter(
        '%(asctime)s | [%(seq)04d] | %(levelname)-7s | %(filename)-15s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    today = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(f"{log_dir}/casino_{today}.log", encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

def log_telegram_message(chat_id, text, msg_type="SEND"):
    """텔레그램 메시지 내용을 별도 파일에 기록"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{log_dir}/telegram_history_{today}.jsonl"
    
    # 현재 로그 시퀀스 번호 (참조용)
    ref_seq = GlobalSequence.current()
    
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "log_seq": ref_seq, # 현재 로그 번호와 연결
        "type": msg_type,
        "chat_id": chat_id,
        "text": text
    }
    
    try:
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"⚠️ 메시지 로깅 실패: {e}")

# 전역 로거 인스턴스
logger = setup_logger()
