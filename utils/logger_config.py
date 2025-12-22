"""
統一的なログ設定モジュール
アプリケーション全体で使用するログ設定を管理
"""

import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logging(log_level=None, log_file=None):
    """
    アプリケーション全体のログ設定を初期化
    
    Args:
        log_level: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
                   デフォルトは環境変数LOG_LEVELまたはINFO
        log_file: ログファイルのパス（オプション）
    """
    # ログレベルの決定
    if log_level is None:
        log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
        log_level = getattr(logging, log_level_str, logging.INFO)
    
    # ログフォーマットの設定
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # 基本設定
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # ファイルログの設定（オプション）
    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        logging.getLogger().addHandler(file_handler)
    
    # 外部ライブラリのログレベルを調整
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.INFO)
    
    return logging.getLogger(__name__)


def get_logger(name):
    """
    モジュール用のロガーを取得
    
    Args:
        name: ロガー名（通常は__name__）
    
    Returns:
        Loggerインスタンス
    """
    return logging.getLogger(name)


# デフォルトでログ設定を初期化
setup_logging()

