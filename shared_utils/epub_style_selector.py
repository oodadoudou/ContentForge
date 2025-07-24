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
    },
    "6": {
        "name": "清洁简约",
        "description": "干净简洁的设计，适合现代阅读体验",
        "file": "epub_style_clean.css",
        "features": ["简洁布局", "清晰字体", "舒适间距", "现代感"]
    },
    "7": {
        "name": "高对比度",
        "description": "高对比度设计，提升可读性，适合视力辅助",
        "file": "epub_style_contrast.css",
        "features": ["高对比度", "清晰可读", "视力友好", "强调重点"]
    },
    "8": {
        "name": "护眼专用",
        "description": "专为长时间阅读设计，减少眼部疲劳",
        "file": "epub_style_eyecare.css",
        "features": ["护眼色调", "柔和背景", "舒适字体", "减少疲劳"]
    },
    "9": {
        "name": "奇幻风格",
        "description": "富有想象力的设计，适合奇幻小说和创意作品",
        "file": "epub_style_fantasy.css",
        "features": ["奇幻装饰", "创意元素", "丰富色彩", "想象空间"]
    },
    "10": {
        "name": "几何设计",
        "description": "现代几何元素，适合设计类和技术类书籍",
        "file": "epub_style_geometric.css",
        "features": ["几何图案", "现代设计", "结构清晰", "视觉冲击"]
    },
    "11": {
        "name": "几何边框",
        "description": "带有几何边框的精美设计",
        "file": "epub_style_geometric_frame.css",
        "features": ["几何边框", "精美装饰", "现代感", "结构美"]
    },
    "12": {
        "name": "灰度经典",
        "description": "经典灰度设计，专业而优雅",
        "file": "epub_style_grayscale.css",
        "features": ["灰度色调", "经典设计", "专业外观", "优雅简约"]
    },
    "13": {
        "name": "层次分明",
        "description": "清晰的层次结构，适合学术和技术文档",
        "file": "epub_style_line_hierarchy.css",
        "features": ["层次清晰", "结构分明", "学术风格", "专业排版"]
    },
    "14": {
        "name": "线性设计",
        "description": "简洁的线性布局，现代感十足",
        "file": "epub_style_linear.css",
        "features": ["线性布局", "简洁设计", "现代风格", "流畅阅读"]
    },
    "15": {
        "name": "网格极简",
        "description": "基于网格系统的极简设计",
        "file": "epub_style_minimal_grid.css",
        "features": ["网格布局", "极简风格", "系统化", "整齐有序"]
    },
    "16": {
        "name": "线性极简",
        "description": "线性极简主义设计风格",
        "file": "epub_style_minimal_linear.css",
        "features": ["线性极简", "纯净设计", "专注内容", "无干扰"]
    },
    "17": {
        "name": "现代极简",
        "description": "现代极简主义，突出内容本质",
        "file": "epub_style_minimal_modern.css",
        "features": ["现代极简", "内容为王", "纯净体验", "专业感"]
    },
    "18": {
        "name": "单色设计",
        "description": "单色调设计，专注于内容表达",
        "file": "epub_style_monochrome.css",
        "features": ["单色调", "专注内容", "简洁纯净", "经典永恒"]
    },
    "19": {
        "name": "柔和舒适",
        "description": "柔和的色调和舒适的阅读体验",
        "file": "epub_style_soft.css",
        "features": ["柔和色调", "舒适阅读", "温和设计", "放松体验"]
    },
    "20": {
        "name": "结构极简",
        "description": "结构化的极简设计，清晰有序",
        "file": "epub_style_structured_minimal.css",
        "features": ["结构清晰", "极简有序", "逻辑分明", "专业布局"]
    }
}

def display_styles():
    """显示所有可用样式"""
    print("\n" + "="*60)
    print("📚 EPUB 电子书样式选择器")
    print("="*60)
    print("\n🎨 可用样式：\n")
    
    # 简洁的两列显示
    styles_list = list(STYLE_OPTIONS.items())
    for i in range(0, len(styles_list), 2):
        # 左列
        key1, style1 = styles_list[i]
        left_col = f"{key1:>2}. {style1['name']:<12}"
        
        # 右列（如果存在）
        if i + 1 < len(styles_list):
            key2, style2 = styles_list[i + 1]
            right_col = f"{key2:>2}. {style2['name']:<12}"
            print(f"{left_col:<30} {right_col}")
        else:
            print(left_col)

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
    """交互式样式选择，返回选择的样式键"""
    while True:
        display_styles()
        print("🔧 操作选项:")
        print("1-20: 选择样式")
        print("p: 预览所有样式")
        print("q: 退出")
        
        choice = input("\n请选择 (1-20/p/q): ").strip().lower()
        
        if choice == 'q':
            print("👋 再见！")
            return None
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
                
                # 询问是否确认选择
                confirm = input("\n确认选择此样式？(回车/y确认，n重选): ").strip().lower()
                if confirm == 'y' or confirm == '':
                    print(f"\n🎉 样式选择完成！将使用 '{style['name']}' 样式生成EPUB")
                    return choice
                elif confirm == 'n':
                    print("\n🔄 重新选择...")
                    continue
                else:
                    print("\n❌ 请输入 y 或 n（直接回车默认为确定）")
            
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