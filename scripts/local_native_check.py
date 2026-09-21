"""Exercise Windows browser and complete-document OCR without production writes."""
import io
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_v2.local_host import environment, load_config, windows_job


def checks():
    config = load_config(sys.argv[1])
    env = environment(config, 'web')
    os.environ.clear()
    os.environ.update(env)
    from PIL import Image, ImageDraw, ImageFont
    from scripts.source_ocr import extract
    pages = []
    font = ImageFont.truetype(str(Path(os.environ['SYSTEMROOT']) / 'Fonts/arial.ttf'), 48)
    for number in (1, 2):
        page = Image.new('RGB', (1200, 800), 'white')
        ImageDraw.Draw(page).text((100, 200), f'POLITITRACK LOCAL PAGE {number}', fill='black', font=font)
        pages.append(page)
    data = io.BytesIO()
    pages[0].save(data, format='PDF', save_all=True, append_images=pages[1:], resolution=150)
    result = extract(data.getvalue())
    assert result['completed_pages'] == [1, 2], result['completed_pages']
    assert 'LOCAL PAGE 1' in result['ocr_text'] and 'LOCAL PAGE 2' in result['ocr_text']
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        tab = browser.new_page()
        tab.set_content('<title>PolitiTrack local check</title>')
        assert tab.title() == 'PolitiTrack local check'
        browser.close()
    print(json.dumps({'ocr_pages': result['completed_pages'], 'ocr_status': result['ocr_status'],
                      'chromium': 'passed', 'windows_process_cleanup': 'configured'}))


if __name__ == '__main__':
    handle = windows_job()
    try:
        checks()
    finally:
        if handle is not None:
            handle.Detach()
