#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EPUB样式选择器
提供多种精美的中文电子书样式选择
"""

import os
import sys
from pathlib import Path

# 获取当前脚本所在目录
CURRENT_DIR = Path(__file__).parent
SHARED_ASSETS_DIR = CURRENT_DIR.parent / "shared_assets"
EPUB_CSS_DIR = SHARED_ASSETS_DIR / "epub_css"

# 样式配置
STYLE_OPTIONS = {
    "1": {
        "name": "经典简约",
        "description": "标准电子书排版，适合大多数小说和文学作品",
        "file": "epub_style_classic.css",
        "features": ["居中标题", "蓝色装饰线", "标准行距", "适中字体"]
    },
    "2": {
        "name": "温馨护眼",
        "description": "温暖色调，舒适行距，减少眼部疲劳，适合长时间阅读",
        "file": "epub_style_warm.css",
        "features": ["护眼设计", "温暖色调", "舒适行距", "装饰性分割线"]
    },
    "3": {
        "name": "现代清新",
        "description": "左对齐标题，现代感强，适合技术文档和现代文学",
        "file": "epub_style_modern.css",
        "features": ["彩色边框", "现代排版", "清晰层次", "无衬线字体"]
    },
    "4": {
        "name": "优雅古典",
        "description": "古典风格，适合古典文学、诗词和传统文化类书籍",
        "file": "epub_style_elegant.css",
        "features": ["古典装饰", "首字下沉", "优雅边框", "传统色调"]
    },
    "5": {
        "name": "简洁现代",
        "description": "极简设计，适合商务文档和学术论文",
        "file": "epub_style_minimal.css",
        "features": ["极简设计", "大写标题", "字母间距", "专业外观"]
    }
}

def display_styles():
    """显示所有可用样式"""
    print("\n" + "="*60)
    print("📚 EPUB 电子书样式选择器")
    print("="*60)
    print("\n🎨 可用样式：\n")
    
    for key, style in STYLE_OPTIONS.items():
        print(f"{key}. {style['name']}")
        print(f"   📖 {style['description']}")
        print(f"   ✨ 特色：{' | '.join(style['features'])}")
        print()

def get_style_content(style_key):
    """获取指定样式的CSS内容"""
    if style_key not in STYLE_OPTIONS:
        return None
    
    style_file = EPUB_CSS_DIR / STYLE_OPTIONS[style_key]["file"]
    
    if not style_file.exists():
        print(f"❌ 样式文件不存在: {style_file}")
        return None
    
    try:
        with open(style_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"❌ 读取样式文件失败: {e}")
        return None

def preview_style():
    """预览样式效果"""
    preview_file = SHARED_ASSETS_DIR / "epub_styles_preview.html"
    
    if preview_file.exists():
        print(f"\n🌐 样式预览文件已创建: {preview_file}")
        print("💡 请在浏览器中打开此文件查看所有样式效果")
        
        # 尝试在默认浏览器中打开预览文件
        try:
            import webbrowser
            webbrowser.open(f"file://{preview_file.absolute()}")
            print("✅ 已在默认浏览器中打开预览")
        except Exception as e:
            print(f"⚠️  无法自动打开浏览器: {e}")
            print(f"请手动打开: {preview_file.absolute()}")
    else:
        print("❌ 预览文件不存在")

def select_style():
    """交互式样式选择"""
    while True:
        display_styles()
        print("🔧 操作选项:")
        print("1-5: 选择样式")
        print("p: 预览所有样式")
        print("q: 退出")
        
        choice = input("\n请选择 (1-5/p/q): ").strip().lower()
        
        if choice == 'q':
            print("👋 再见！")
            break
        elif choice == 'p':
            preview_style()
            input("\n按回车键继续...")
        elif choice in STYLE_OPTIONS:
            style = STYLE_OPTIONS[choice]
            print(f"\n✅ 已选择样式: {style['name']}")
            print(f"📄 样式文件: {style['file']}")
            
            # 获取样式内容
            css_content = get_style_content(choice)
            if css_content:
                print(f"\n📋 CSS内容预览 (前200字符):")
                print("-" * 50)
                print(css_content[:200] + "..." if len(css_content) > 200 else css_content)
                print("-" * 50)
                
                # 询问是否应用到默认样式
                apply = input("\n是否将此样式设为默认样式？(y/n): ").strip().lower()
                if apply == 'y':
                    apply_default_style(choice)
            
            input("\n按回车键继续...")
        else:
            print("❌ 无效选择，请重试")
            input("按回车键继续...")

def apply_default_style(style_key):
    """将选择的样式应用为默认样式"""
    try:
        # 复制选择的样式到默认样式文件
        source_file = EPUB_CSS_DIR / STYLE_OPTIONS[style_key]["file"]
        target_file = SHARED_ASSETS_DIR / "new_style.css"
        
        with open(source_file, 'r', encoding='utf-8') as src:
            css_content = src.read()
        
        with open(target_file, 'w', encoding='utf-8') as dst:
            dst.write(css_content)
        
        print(f"✅ 已将 '{STYLE_OPTIONS[style_key]['name']}' 设为默认样式")
        print(f"📁 默认样式文件: {target_file}")
        
    except Exception as e:
        print(f"❌ 应用默认样式失败: {e}")

def main():
    """主函数"""
    print("\n🎨 EPUB样式管理工具")
    print("为您的中文电子书选择最适合的排版样式")
    
    # 检查样式文件是否存在
    missing_files = []
    for style in STYLE_OPTIONS.values():
        style_file = EPUB_CSS_DIR / style["file"]
        if not style_file.exists():
            missing_files.append(style["file"])
    
    if missing_files:
        print(f"\n⚠️  以下样式文件缺失: {', '.join(missing_files)}")
        print("请确保所有样式文件都在 shared_assets/epub_css 目录中")
        return
    
    select_style()

if __name__ == "__main__":
    main()