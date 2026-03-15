"""
pytest 設定
プロジェクトルートを sys.path に追加し、テストの import を可能にする
"""
import sys
import os

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
