import os
import glob
import sys
import markdown2
import base64
import json

def create_html_from_markdown(target_path):
    """
    Converts all Markdown files in a specified directory to self-contained HTML files.
    """
    if not os.path.isdir(target_path):
        print(f"Error: The path '{target_path}' is not a valid directory.")
        sys.exit(1)

    md_files = glob.glob(os.path.join(target_path, '*.md'))

    if not md_files:
        print(f"No .md files found in '{target_path}'.")
        sys.exit(0)
        
    print(f"\nFound {len(md_files)} Markdown files. Starting conversion...")

    output_dir = os.path.join(target_path, "processed_files")
    os.makedirs(output_dir, exist_ok=True)
    print(f"All converted HTML files will be saved in: {output_dir}\n")

    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #fff;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }}
            h1, h2, h3, h4, h5, h6 {{
                font-family: "Georgia", serif;
                font-weight: bold;
            }}
            pre {{
                position: relative;
                background-color: #f4f4f4;
                border-radius: 4px;
                padding: 1em;
                overflow-x: auto;
            }}
            code {{
                font-family: "Menlo", "Consolas", "Courier New", monospace;
            }}
            .copy-btn {{
                position: absolute;
                top: 10px;
                right: 10px;
                background-color: #007bff;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                cursor: pointer;
                opacity: 0;
                transition: opacity 0.3s;
            }}
            pre:hover .copy-btn {{
                opacity: 1;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin-bottom: 1em;
            }}
            th, td {{
                border: 1px solid #dddddd;
                text-align: left;
                padding: 8px;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            blockquote {{
                border-left: 4px solid #ccc;
                padding-left: 1em;
                color: #666;
            }}
            /* Syntax Highlighting CSS (highlight.js - GitHub theme) */
            .hljs {{ display: block; overflow-x: auto; padding: .5em; color: #333; background: #f8f8f8; }}
            .hljs-comment,.hljs-quote {{ color: #998; font-style: italic; }}
            .hljs-keyword,.hljs-selector-tag,.hljs-subst {{ color: #333; font-weight: bold; }}
            .hljs-number,.hljs-literal,.hljs-variable,.hljs-template-variable,.hljs-tag .hljs-attr {{ color: #008080; }}
            .hljs-string,.hljs-doctag {{ color: #d14; }}
            .hljs-title,.hljs-section,.hljs-selector-id {{ color: #900; font-weight: bold; }}
            .hljs-subst {{ font-weight: normal; }}
            .hljs-type,.hljs-class .hljs-title {{ color: #458; font-weight: bold; }}
            .hljs-tag,.hljs-name,.hljs-attribute {{ color: #000080; font-weight: normal; }}
            .hljs-regexp,.hljs-link {{ color: #009926; }}
            .hljs-symbol,.hljs-bullet {{ color: #990073; }}
            .hljs-built_in,.hljs-builtin-name {{ color: #0086b3; }}
            .hljs-meta {{ color: #999; font-weight: bold; }}
            .hljs-deletion {{ background: #fdd; }}
            .hljs-addition {{ background: #dfd; }}
            .hljs-emphasis {{ font-style: italic; }}
            .hljs-strong {{ font-weight: bold; }}
        </style>
        <script>
            // highlight.js - Base64 encoded to be self-contained
            const highlightJsCode = atob('{highlight_js_base64}');
            const scriptEl = document.createElement('script');
            scriptEl.textContent = highlightJsCode;
            document.head.appendChild(scriptEl);
        </script>
    </head>
    <body>
        {content}
        <script>
            document.addEventListener('DOMContentLoaded', (event) => {{
                document.querySelectorAll('pre code').forEach((block) => {{
                    hljs.highlightBlock(block);
                    const pre = block.parentElement;
                    const copyButton = document.createElement('button');
                    copyButton.innerText = 'Copy';
                    copyButton.className = 'copy-btn';
                    copyButton.addEventListener('click', () => {{
                        navigator.clipboard.writeText(block.innerText).then(() => {{
                            copyButton.innerText = 'Copied!';
                            setTimeout(() => {{
                                copyButton.innerText = 'Copy';
                            }}, 2000);
                        }});
                    }});
                    pre.appendChild(copyButton);
                }});
            }});
        </script>
    </body>
    </html>
    """

    try:
        # --- 修改：动态构建 highlight.min.js 的路径 ---
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        highlight_js_path = os.path.join(project_root, "shared_assets", "highlight.min.js")
        with open(highlight_js_path, "rb") as f:
            highlight_js_b64 = base64.b64encode(f.read()).decode('utf-8')
    except FileNotFoundError:
        print("警告: 'shared_assets/highlight.min.js' 未找到。代码高亮将无法正常工作。")
        highlight_js_b64 = ""

    for md_file_path in md_files:
        file_name = os.path.basename(md_file_path)
        print(f"-> Processing: {file_name} ...")

        try:
            with open(md_file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()

            html_content = markdown2.markdown(
                md_content,
                extras=['fenced-code-blocks', 'tables', 'strike', 'cuddled-lists', 'code-friendly']
            )
            
            title = os.path.splitext(file_name)[0]
            full_html = html_template.format(
                title=title,
                content=html_content,
                highlight_js_base64=highlight_js_b64
            )
            
            html_file_name = title + '.html'
            output_html_path = os.path.join(output_dir, html_file_name)

            with open(output_html_path, 'w', encoding='utf-8') as f:
                f.write(full_html)
            
            print(f"   ✓ Successfully converted to: {html_file_name}")

        except Exception as e:
            print(f"   ✗ An error occurred while processing {file_name}: {e}")

    print("\nAll files processed successfully!")


# --- 新增：函数用于从 settings.json 加载默认路径 ---
def load_default_path_from_settings():
    """从共享设置文件中读取默认工作目录。"""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        settings_path = os.path.join(project_root, 'shared_assets', 'settings.json')
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        default_dir = settings.get("default_work_dir")
        return default_dir if default_dir else "."
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Downloads")

# --- 修改：主程序块使用交互式输入 ---
if __name__ == '__main__':
    default_path = load_default_path_from_settings()
    
    prompt_message = (
        f"请输入包含 Markdown (.md) 文件的文件夹路径。\n"
        f"(直接按 Enter 键，将使用默认路径 '{default_path}') : "
    )
    user_input = input(prompt_message)

    target_directory = user_input.strip() if user_input.strip() else default_path
    
    if not target_directory:
        print("错误：未提供有效路径。")
        sys.exit(1)

    print(f"[*] 已选择工作目录: {os.path.abspath(target_directory)}")
    create_html_from_markdown(target_directory)
