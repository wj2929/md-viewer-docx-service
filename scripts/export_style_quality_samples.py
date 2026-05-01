import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.generator import generate_docx_from_content


STYLES = ("standard", "official", "internal", "report")


def find_soffice() -> Optional[str]:
    cli = shutil.which("soffice")
    if cli:
        return cli
    mac = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    return mac if Path(mac).exists() else None


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--out-dir", default="/tmp/mdv-docx-non-preview-style-quality")
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--to-pdf", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    source_dir = Path(args.source_dir)
    out_dir = Path(args.out_dir)
    md_files = sorted(source_dir.glob("*.md"))[: args.limit]
    if not md_files:
        raise SystemExit(f"no markdown files found in {source_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    for md_path in md_files:
        content = md_path.read_text(encoding="utf-8")
        for style in STYLES:
            target = out_dir / style / f"{md_path.stem}.docx"
            target.parent.mkdir(parents=True, exist_ok=True)
            started = time.time()
            generate_docx_from_content(content=content, output_path=str(target), style=style)
            elapsed = time.time() - started
            generated.append(target)
            print(f"{style}\t{md_path.name}\t{target}\t{elapsed:.2f}s")

    if args.to_pdf:
        soffice = find_soffice()
        if not soffice:
            raise SystemExit("soffice not found")
        for docx in generated:
            pdf_dir = out_dir / "pdf" / docx.parent.name
            pdf_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(pdf_dir), str(docx)],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )

    print(f"generated_docx={len(generated)}")


if __name__ == "__main__":
    main()
