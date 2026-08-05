# -*- coding: utf-8 -*-
"""
extract_text.py — extrai texto de .docx e .pdf para .txt (deterministico, sem IA).
Uso: python _build/extract_text.py <arquivo_in> <arquivo_out.txt>
.docx -> junta paragrafos (word/document.xml). .pdf -> pdfplumber.
"""
import sys, os, re, zipfile, html


def docx_to_text(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml').decode('utf-8', 'ignore')
    # quebra por paragrafo e por <w:tab/>, remove tags
    xml = xml.replace('</w:p>', '\n').replace('<w:tab/>', '\t')
    txt = re.sub(r'<[^>]+>', '', xml)
    txt = html.unescape(txt)
    # normaliza linhas em branco
    lines = [ln.rstrip() for ln in txt.split('\n')]
    out, blank = [], 0
    for ln in lines:
        if ln.strip() == '':
            blank += 1
            if blank <= 1:
                out.append('')
        else:
            blank = 0
            out.append(ln)
    return '\n'.join(out).strip()


def pdf_to_text(path):
    import pdfplumber
    parts = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            t = page.extract_text() or ''
            parts.append(f"----- PAGINA {i+1} -----\n{t}")
    return '\n\n'.join(parts)


def main():
    src, out = sys.argv[1], sys.argv[2]
    ext = os.path.splitext(src)[1].lower()
    if ext == '.docx':
        txt = docx_to_text(src)
    elif ext == '.pdf':
        txt = pdf_to_text(src)
    else:
        raise SystemExit(f"ext nao suportada: {ext}")
    with open(out, 'w', encoding='utf-8') as f:
        f.write(txt)
    print(f"OK {out}  ({len(txt)} chars)")


if __name__ == '__main__':
    main()
