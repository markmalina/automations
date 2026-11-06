"""Generate 100 mixed, individual files totaling exactly 30,000,000 bytes."""
import argparse
import hashlib
import io
import json
import pathlib
import random
import zipfile
from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=pathlib.Path, default=pathlib.Path('/tmp/n8n-upload-fixtures/mixed'))
root = parser.parse_args().root
root.mkdir(parents=True, exist_ok=True)
rng = random.Random(20261106)
extensions = ['jpg', 'png', 'svg', 'pdf', 'docx', 'txt', 'js', 'csv', 'json', 'bin']
files = []
for i in range(100):
    ext = extensions[i % len(extensions)]
    rel = f'Раздел {i // 20 + 1}/вложенная папка/Файл {i + 1:03}.{ext}'
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    padding = ('fixture ' * 40000).encode()[:300000]
    if ext in ('jpg', 'png'):
        image = Image.frombytes('RGB', (384, 384), rng.randbytes(384 * 384 * 3))
        image.save(path, quality=90)
    elif ext == 'svg':
        path.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="green"/><!--' + padding + b'--></svg>')
    elif ext == 'pdf':
        from reportlab.pdfgen.canvas import Canvas
        buffer = io.BytesIO()
        c = Canvas(buffer); c.drawString(20, 800, f'Transport fixture {i}'); c.showPage(); c.save()
        path.write_bytes(buffer.getvalue() + b'\n%' + padding + b'\n')
    elif ext == 'docx':
        from docx import Document
        document = Document(); document.add_paragraph(f'Transport fixture {i}'); document.save(path)
        with zipfile.ZipFile(path, 'a', compression=zipfile.ZIP_STORED) as archive:
            archive.writestr('customXml/padding.txt', padding)
    elif ext == 'json':
        path.write_text(json.dumps({'fixture': i, 'text': padding.decode()}, ensure_ascii=False))
    elif ext == 'csv':
        path.write_bytes(b'id,text\n' + str(i).encode() + b',' + padding + b'\n')
    elif ext == 'js':
        path.write_bytes(b'// ' + padding + b'\nexport const fixture = true;\n')
    elif ext == 'txt':
        path.write_bytes('Проверка текста и имени\n'.encode() + padding)
    else:
        count = 300000 if i != 99 else 30000000 - sum((root / f['path']).stat().st_size for f in files)
        if count <= 0:
            raise SystemExit('Fixture size overflow')
        path.write_bytes(rng.randbytes(count))
    data = path.read_bytes()
    files.append({'field': f'f{i:03}', 'path': rel, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
manifest = {'files': files, 'fileCount': len(files), 'totalBytes': sum(f['bytes'] for f in files)}
assert manifest['fileCount'] == 100 and manifest['totalBytes'] == 30000000
(root.parent / 'mixed-manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'fileCount': manifest['fileCount'], 'totalBytes': manifest['totalBytes'], 'root': str(root)}))
