import os
import sys
import zipfile
import tempfile
import shutil
import xml.etree.ElementTree as ET
import json
from urllib.parse import unquote

def get_unique_filepath(path):
    """Checks if a file path exists. If it does, appends a number to make it unique."""
    if not os.path.exists(path):
        return path
    directory, filename = os.path.split(path)
    name, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_name = f"{name} ({counter}){ext}"
        new_path = os.path.join(directory, new_name)
        if not os.path.exists(new_path):
            return new_path
        counter += 1

def load_default_path_from_settings():
    """Reads the default working directory from a shared settings file."""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        settings_path = os.path.join(project_root, 'shared_assets', 'settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            default_dir = settings.get("default_work_dir")
            return default_dir if default_dir and os.path.isdir(default_dir) else "."
        else:
             return os.path.join(os.path.expanduser("~"), "Downloads")
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Downloads")

def run_epub_cover_remover():
    """
    Scans a directory for EPUB files, removes the cover image and its associated 
    (x)html file, and saves the modified files to a 'processed_files' subdirectory.
    """
    print("=====================================================")
    print("=        EPUB Cover Remover Script (v2)           =")
    print("=====================================================")
    print("Functionality:")
    print("  - Scans a folder for all .epub files.")
    print("  - Removes the cover image (e.g., cover.jpg).")
    print("  - Removes the associated cover page (e.g., cover.xhtml).")
    print("  - Saves the modified files in a 'processed_files' subfolder.")

    default_path = load_default_path_from_settings()
    folder_path = input(f"\nPlease enter the path to the EPUB folder (default: {default_path}): ").strip() or default_path

    if not os.path.isdir(folder_path):
        sys.exit(f"\nError: The folder '{folder_path}' does not exist.")

    processed_folder_path = os.path.join(folder_path, "processed_files")
    os.makedirs(processed_folder_path, exist_ok=True)

    epub_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith('.epub')])
    if not epub_files:
        sys.exit(f"No EPUB files found in '{folder_path}'.")

    print(f"\nFound {len(epub_files)} EPUB file(s) to process.")
    print("\n--- Starting Batch Processing ---")

    for filename in epub_files:
        original_path = os.path.join(folder_path, filename)
        temp_dir = None
        print(f"\n--- Processing: {filename} ---")
        try:
            temp_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(original_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # Find the .opf file path from container.xml
            container_path = os.path.join(temp_dir, 'META-INF', 'container.xml')
            if not os.path.exists(container_path):
                raise FileNotFoundError("Could not find META-INF/container.xml")

            container_tree = ET.parse(container_path)
            container_root = container_tree.getroot()
            ns_cn = {'cn': 'urn:oasis:names:tc:opendocument:xmlns:container'}
            opf_path_element = container_root.find('cn:rootfiles/cn:rootfile', ns_cn)
            if opf_path_element is None: raise FileNotFoundError("Could not find <rootfile> tag in container.xml")
            
            opf_rel_path = opf_path_element.get('full-path')
            opf_abs_path = os.path.join(temp_dir, opf_rel_path)
            opf_dir = os.path.dirname(opf_abs_path)
            print(f"  - Found metadata file: {opf_rel_path}")

            opf_tree = ET.parse(opf_abs_path)
            opf_root = opf_tree.getroot()
            
            namespaces = {
                'opf': 'http://www.idpf.org/2007/opf',
                'dc': 'http://purl.org/dc/elements/1.1/',
                'xhtml': 'http://www.w3.org/1999/xhtml',
                'svg': 'http://www.w3.org/2000/svg',
                'xlink': 'http://www.w3.org/1999/xlink'
            }
            for prefix, uri in namespaces.items(): ET.register_namespace(prefix, uri)

            meta_cover = opf_root.find('.//opf:meta[@name="cover"]', namespaces)
            if meta_cover is None:
                print("  - No cover metadata found (<meta name='cover'>). Skipping cover removal.")
                shutil.copy(original_path, get_unique_filepath(os.path.join(processed_folder_path, filename)))
                print(f"  - Copied original file to processed folder.")
                continue

            cover_id = meta_cover.get('content')
            print(f"  - Found cover metadata ID: '{cover_id}'")

            manifest = opf_root.find('opf:manifest', namespaces)
            if manifest is None: raise ValueError("Could not find <manifest> in .opf file")
            
            # --- Find and remove cover IMAGE ---
            cover_item = manifest.find(f'opf:item[@id="{cover_id}"]', namespaces)
            if cover_item is None: raise ValueError(f"Could not find manifest item with id='{cover_id}'")

            cover_href = unquote(cover_item.get('href'))
            cover_image_path = os.path.join(opf_dir, cover_href)
            print(f"  - Found cover image reference: '{cover_href}'")

            # --- NEW: Find and remove cover XHTML file ---
            cover_html_item = None
            cover_html_path_to_delete = None
            
            html_items = manifest.findall('.//opf:item[@media-type="application/xhtml+xml"]', namespaces)
            for item in html_items:
                html_rel_path = unquote(item.get('href'))
                html_abs_path = os.path.join(opf_dir, html_rel_path)
                if not os.path.exists(html_abs_path): continue

                try:
                    html_tree = ET.parse(html_abs_path)
                    # Search for <img> or <svg:image> pointing to the cover href
                    # We compare basenames to avoid relative path complexities
                    for img in html_tree.findall('.//xhtml:img', namespaces):
                        if img.get('src') and os.path.basename(unquote(img.get('src'))) == os.path.basename(cover_href):
                            cover_html_item = item
                            break
                    if cover_html_item: break
                    for img in html_tree.findall('.//svg:image', namespaces):
                        if img.get('{http://www.w3.org/1999/xlink}href') and os.path.basename(unquote(img.get('{http://www.w3.org/1999/xlink}href'))) == os.path.basename(cover_href):
                            cover_html_item = item
                            break
                    if cover_html_item: break
                except ET.ParseError:
                    print(f"  - Warning: Could not parse {html_rel_path}, skipping.")

            if cover_html_item is not None:
                cover_html_id = cover_html_item.get('id')
                cover_html_href = unquote(cover_html_item.get('href'))
                cover_html_path_to_delete = os.path.join(opf_dir, cover_html_href)
                print(f"  - Found cover HTML page: '{cover_html_href}'")

                # Remove from manifest
                manifest.remove(cover_html_item)
                print("  - Removed cover HTML from manifest.")
                # Remove from spine
                spine = opf_root.find('opf:spine', namespaces)
                if spine is not None:
                    spine_item_to_remove = spine.find(f'opf:itemref[@idref="{cover_html_id}"]', namespaces)
                    if spine_item_to_remove is not None:
                        spine.remove(spine_item_to_remove)
                        print("  - Removed cover HTML from spine.")
                # Delete file
                if os.path.exists(cover_html_path_to_delete):
                    os.remove(cover_html_path_to_delete)
                    print("  - Deleted cover HTML file.")
            else:
                print("  - No separate cover HTML page found or linked.")

            # --- Continue with removing original cover image and metadata ---
            if os.path.exists(cover_image_path):
                os.remove(cover_image_path)
                print(f"  - Deleted image file: {os.path.basename(cover_image_path)}")
            else:
                print(f"  - Warning: Image file not found at '{cover_image_path}', but removing references.")

            manifest.remove(cover_item)
            print("  - Removed cover image from manifest.")
            
            metadata = opf_root.find('opf:metadata', namespaces)
            if metadata is not None:
                metadata.remove(meta_cover)
                print("  - Removed cover metadata tag.")

            opf_tree.write(opf_abs_path, encoding='utf-8', xml_declaration=True)

            # Re-pack the EPUB file
            destination_path = get_unique_filepath(os.path.join(processed_folder_path, filename))
            print(f"  - Repacking to: {os.path.basename(destination_path)}")
            with zipfile.ZipFile(destination_path, 'w') as zip_out:
                mimetype_path = os.path.join(temp_dir, 'mimetype')
                if os.path.exists(mimetype_path):
                    zip_out.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
                
                for root_dir, _, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root_dir, file)
                        if not os.path.exists(file_path): continue
                        arcname = os.path.relpath(file_path, temp_dir)
                        if arcname != 'mimetype':
                            zip_out.write(file_path, arcname, compress_type=zipfile.ZIP_DEFLATED)
            print("  - Successfully processed!")

        except Exception as e:
            print(f"  ! An error occurred while processing '{filename}': {e}")
            import traceback
            traceback.print_exc()
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    print("\n--- All tasks completed ---")

if __name__ == "__main__":
    run_epub_cover_remover()