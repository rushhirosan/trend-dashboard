#!/usr/bin/env python3
"""
画像ファイルを圧縮するスクリプト
適切なサイズにリサイズしてから圧縮します
"""
import os
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillowがインストールされていません。インストール中...")
    os.system("pip install Pillow")
    from PIL import Image


def compress_and_resize_image(input_path, output_path, target_size=None, quality=85, optimize=True):
    """
    画像をリサイズして圧縮する
    
    Args:
        input_path: 入力画像のパス
        output_path: 出力画像のパス
        target_size: ターゲットサイズ（タプル: (width, height)）、Noneの場合はリサイズしない
        quality: JPEG品質（1-100、PNGの場合は無視される）
        optimize: 最適化フラグ
    """
    try:
        with Image.open(input_path) as img:
            original_size = img.size
            
            # リサイズが必要な場合
            if target_size:
                # 正方形にリサイズ（中央からクロップ）
                if img.size[0] != img.size[1]:
                    # 正方形にクロップ
                    size = min(img.size[0], img.size[1])
                    left = (img.size[0] - size) // 2
                    top = (img.size[1] - size) // 2
                    right = left + size
                    bottom = top + size
                    img = img.crop((left, top, right, bottom))
                    print(f"  クロップ: {original_size[0]}x{original_size[1]} → {img.size[0]}x{img.size[1]}")
                
                # ターゲットサイズにリサイズ
                if img.size[0] != target_size[0] or img.size[1] != target_size[1]:
                    img = img.resize(target_size, Image.Resampling.LANCZOS)
                    print(f"  リサイズ: {img.size[0]}x{img.size[1]} → {target_size[0]}x{target_size[1]}")
            
            # RGBAモードの場合はRGBに変換（透過情報を保持する必要がある場合は別処理）
            if img.mode in ('RGBA', 'LA', 'P'):
                # 透過情報がある場合は背景色を白に設定してRGBに変換
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode in ('RGBA', 'LA'):
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                else:
                    img = img.convert('RGB')
            
            # PNGの場合は最適化して保存
            if input_path.lower().endswith('.png'):
                # PNGの圧縮: optimize=Trueでファイルサイズを削減
                img.save(output_path, 'PNG', optimize=optimize, compress_level=9)
            else:
                # その他の形式はJPEGとして保存
                img.save(output_path, 'JPEG', quality=quality, optimize=optimize)
            
            original_file_size = os.path.getsize(input_path)
            compressed_file_size = os.path.getsize(output_path)
            reduction = (1 - compressed_file_size / original_file_size) * 100
            
            print(f"✓ {os.path.basename(input_path)}: {original_file_size / 1024 / 1024:.2f}MB → {compressed_file_size / 1024 / 1024:.2f}MB ({reduction:.1f}%削減)")
            
            return True
    except Exception as e:
        print(f"✗ エラー: {input_path} - {str(e)}")
        return False


def main():
    """メイン処理"""
    # プロジェクトルートを取得
    project_root = Path(__file__).parent.parent
    images_dir = project_root / 'static' / 'images'
    
    if not images_dir.exists():
        print(f"エラー: {images_dir} が見つかりません")
        sys.exit(1)
    
    # ファイルごとの設定（正方形にリサイズ）
    image_configs = {
        'favicon.png': (32, 32),  # faviconは32x32で十分
        'icon-512.png': (512, 512),  # アプリアイコンは512x512
    }
    
    print("画像圧縮を開始します...\n")
    
    # 各ファイルを圧縮
    for filename, target_size in image_configs.items():
        png_file = images_dir / filename
        if not png_file.exists():
            print(f"⚠ {filename} が見つかりません。スキップします。")
            continue
        
        print(f"\n処理中: {filename} (ターゲットサイズ: {target_size[0]}x{target_size[1]})")
        # 一時ファイル名で保存
        temp_file = png_file.with_suffix('.tmp.png')
        if compress_and_resize_image(str(png_file), str(temp_file), target_size=target_size):
            # 元のファイルをバックアップ
            backup_file = png_file.with_suffix('.png.bak')
            png_file.rename(backup_file)
            # 圧縮済みファイルを元の名前に
            temp_file.rename(png_file)
            # バックアップファイルを削除
            backup_file.unlink()
    
    print("\n圧縮完了！")
    
    # 最終的なファイルサイズを表示
    print("\n最終的なファイルサイズ:")
    for filename in image_configs.keys():
        png_file = images_dir / filename
        if png_file.exists():
            size_kb = os.path.getsize(png_file) / 1024
            size_mb = size_kb / 1024
            if size_mb < 1:
                print(f"  {filename}: {size_kb:.1f}KB")
            else:
                print(f"  {filename}: {size_mb:.2f}MB")


if __name__ == '__main__':
    main()
