"""
ルートモジュール
各APIルートを管理
"""

from .trend_routes import trend_bp
from .data_routes import data_bp

__all__ = ['trend_bp', 'data_bp']


