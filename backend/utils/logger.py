import logging
import sys
import os

LOG_LEVEL = "DEBUG"

class SingletonLogger:
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SingletonLogger, cls).__new__(cls)
        return cls._instance

    def __init__(self, name='YONA_Vanguard_New', level=LOG_LEVEL, log_dir='logs'):
        if self._initialized:
            return
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        if not self.logger.hasHandlers():
            # 포매터 설정
            formatter = logging.Formatter(
                '%(asctime)s - [%(levelname)s] - %(message)s (%(filename)s:%(lineno)d)'
            )

            # 콘솔 핸들러
            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(level)
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

            # 파일 핸들러 (로그 파일 저장)
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            fh = logging.FileHandler(os.path.join(log_dir, 'app.log'), encoding='utf-8')
            fh.setLevel(level)
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)

        self._initialized = True

def setup_logger():
    return SingletonLogger().logger