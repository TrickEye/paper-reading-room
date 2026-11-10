#!/usr/bin/env python3
"""Extract explicitly mapped original figures. Requires pypdf; vector rendering needs pdftoppm.

Plan: [{"figure": 1, "page": 1, "image_index": 0},
       {"figure": 2, "page": 3, "bbox": [70, 80, 520, 340]}]
Page numbers are 1-based, image_index is 0-based, bbox uses top-left PDF points.
No automatic claim that a PDF image is a complete numbered figure is made.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def extract(pdf_path, plan, out, dpi=216, source_url=None):
    from pypdf import PdfReader, PdfWriter

    if not isinstance(plan, list) or not plan:
        raise ValueError('Plan must be a nonempty list of explicitly mapped figures.')
    reader = PdfReader(pdf_path)
    seen = set()
    # Validate the complete plan before writing any output.
    for item in plan:
        number = str(item['figure'])
        if not number or not all(c.isalnum() or c in '-_' for c in number):
            raise ValueError(f'Invalid figure identifier: {number!r}')
        if number in seen:
            raise ValueError(f'Duplicate figure identifier: {number}')
        seen.add(number)
        page_number = item['page']
        if not isinstance(page_number, int) or not 1 <= page_number <= len(reader.pages):
            raise ValueError(f'Figure {number}: page out of range')
        page = reader.pages[page_number - 1]
        if ('image_index' in item) == ('bbox' in item):
            raise ValueError(f'Figure {number}: specify exactly one of image_index or bbox')
        if 'image_index' in item:
            idx = item['image_index']
            if not isinstance(idx, int) or not 0 <= idx < len(page.images):
                raise ValueError(f'Figure {number}: image_index out of range')
        else:
            if page.rotation:
                raise ValueError(f'Figure {number}: rotated page; establish unrotated coordinates first')
            box = item['bbox']
            if not isinstance(box, list) or len(box) != 4:
                raise ValueError(f'Figure {number}: bbox must have four coordinates')
            x0, y0, x1, y1 = map(float, box)
            width, height = float(page.mediabox.width), float(page.mediabox.height)
            if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
                raise ValueError(f'Figure {number}: bbox outside page')
            if x0 == 0 and y0 == 0 and x1 == width and y1 == height:
                raise ValueError(f'Figure {number}: whole-page rendering is not a figure extraction')
            if not shutil.which('pdftoppm'):
                raise ValueError('Vector rendering requires pdftoppm on PATH.')
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory is not empty; use a new staging directory, then review and merge.')
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    source_sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='paper-figures-') as temporary:
        for item in plan:
            number = str(item['figure'])
            name = f'figure-{number.zfill(2)}'
            page = reader.pages[item['page'] - 1]
            record = dict(figure=item['figure'], page=item['page'], source_pdf=pdf_path.name,
                          source_pdf_sha256=source_sha)
            if source_url:
                record['source_url'] = source_url
            if 'image_index' in item:
                image = page.images[item['image_index']]
                suffix = Path(image.name).suffix.lower()
                if suffix not in {'.png', '.jpg', '.jpeg', '.jp2', '.tif', '.tiff'}:
                    raise ValueError(f'Unsupported image wrapper {suffix!r}; inspect source manually.')
                file = out / (name + suffix)
                file.write_bytes(image.data)
                record.update(method='original embedded image; unchanged extracted bytes',
                              image_index=item['image_index'], pdf_image=image.name,
                              width=image.image.width, height=image.image.height)
            else:
                from PIL import Image
                x0, y0, x1, y1 = map(float, item['bbox'])
                ox, oy = float(page.mediabox.left), float(page.mediabox.bottom)
                height = float(page.mediabox.height)
                writer = PdfWriter()
                writer.add_page(page)
                copied = writer.pages[0]
                for box_name in ['mediabox', 'cropbox']:
                    box = getattr(copied, box_name)
                    box.lower_left = (ox + x0, oy + height - y1)
                    box.upper_right = (ox + x1, oy + height - y0)
                clipped = Path(temporary) / (name + '.pdf')
                writer.write(clipped)
                subprocess.run(['pdftoppm', '-r', str(dpi), '-png', '-singlefile',
                                str(clipped), str(out / name)], check=True, capture_output=True)
                file = out / (name + '.png')
                with Image.open(file) as image:
                    width, height = image.size
                record.update(method='original PDF figure rendered in isolation',
                              bbox_top_left_points=item['bbox'], dpi=dpi, width=width, height=height)
            record.update(file=file.name, sha256=hashlib.sha256(file.read_bytes()).hexdigest())
            manifest.append(record)
    (out / 'assets.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--dpi', type=int, default=216)
    parser.add_argument('--source-url')
    args = parser.parse_args()
    if not 72 <= args.dpi <= 600:
        parser.error('--dpi must be between 72 and 600')
    try:
        result = extract(args.pdf, json.loads(args.plan.read_text(encoding='utf-8')),
                         args.out, args.dpi, args.source_url)
    except (ValueError, OSError, KeyError, ImportError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Extraction failed: {error}\n')
    print(f'Extracted {len(result)} mapped figures. Visually review every asset and its crop boundary.')


if __name__ == '__main__':
    main()
