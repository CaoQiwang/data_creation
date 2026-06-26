from __future__ import annotations

import argparse
import os
import shutil
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# python raw_data\parse_pdf_with_mineru.py "raw_data\pdf\国防科技"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "raw_data" / "md_from_pdf"
DEFAULT_WORK_DIR = REPO_ROOT / "raw_data" / "_mineru_work"


@dataclass(frozen=True)
class ParseResult:
    pdf: Path
    markdown: Path
    command: list[str]


class MinerUPdfParser:
    def __init__(
        self,
        output_dir: str | Path = DEFAULT_OUTPUT_DIR,
        work_dir: str | Path = DEFAULT_WORK_DIR,
        method: str = "auto",
        backend: str = "pipeline",
        mineru_cmd: str = "",
        cmd_template: str = "",
        keep_work_dir: bool = False,
        overwrite: bool = False,
    ) -> None:
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.work_root = Path(work_dir).expanduser().resolve()
        self.method = method
        self.backend = backend
        self.mineru_cmd = mineru_cmd
        self.cmd_template = cmd_template
        self.keep_work_dir = keep_work_dir
        self.overwrite = overwrite

    def parse_path(
        self,
        input_path: str | Path,
        output_name: str = "",
        recursive: bool = False,
        continue_on_error: bool = False,
    ) -> list[ParseResult]:
        path = Path(input_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Input path not found: {path}")

        if path.is_file():
            return [self.parse_pdf(path, output_name=output_name)]

        if output_name:
            raise ValueError("--output-name can only be used when parsing a single PDF file.")

        results: list[ParseResult] = []
        pdfs = self.list_pdfs(path, recursive=recursive)
        if not pdfs:
            raise FileNotFoundError(f"No PDF files found under: {path}")

        for index, pdf in enumerate(pdfs, start=1):
            print(f"[{index}/{len(pdfs)}] Parsing: {pdf}")
            try:
                result = self.parse_pdf(pdf)
            except Exception as exc:
                if not continue_on_error:
                    raise
                print(f"[{index}/{len(pdfs)}] Failed: {pdf} ({exc})")
                continue

            results.append(result)
            print(f"[{index}/{len(pdfs)}] Markdown: {result.markdown}")

        return results

    def parse_pdf(self, pdf: str | Path, output_name: str = "") -> ParseResult:
        pdf_path = Path(pdf).expanduser().resolve()
        self.validate_pdf(pdf_path)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        target = self.final_markdown_path(pdf_path, output_name)
        if target.exists() and not self.overwrite:
            raise FileExistsError(f"Output Markdown already exists. Use --overwrite to replace it: {target}")

        work_dir = self.work_root / pdf_path.stem
        if work_dir.exists():
            shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        command = self.run_mineru(self.candidate_commands(pdf_path, work_dir))
        markdown = self.choose_markdown(self.find_markdown_files(work_dir), pdf_path.stem)
        shutil.copy2(markdown, target)

        if not self.keep_work_dir:
            shutil.rmtree(work_dir)

        return ParseResult(pdf=pdf_path, markdown=target, command=command)

    @staticmethod
    def list_pdfs(directory: Path, recursive: bool = False) -> list[Path]:
        pattern = "**/*.pdf" if recursive else "*.pdf"
        return sorted(
            (path.resolve() for path in directory.glob(pattern) if path.is_file()),
            key=lambda path: str(path).casefold(),
        )

    @staticmethod
    def validate_pdf(pdf: Path) -> None:
        if not pdf.exists():
            raise FileNotFoundError(f"PDF not found: {pdf}")
        if not pdf.is_file():
            raise ValueError(f"Input path is not a file: {pdf}")
        if pdf.suffix.lower() != ".pdf":
            raise ValueError(f"Input file is not a PDF: {pdf}")

    @staticmethod
    def quote_path(path: Path) -> str:
        return str(path)

    def command_from_template(self, template: str, pdf: Path, work_dir: Path) -> list[str]:
        rendered = template.format(
            pdf=self.quote_path(pdf),
            work_dir=self.quote_path(work_dir),
            method=self.method,
            backend=self.backend,
        )
        return shlex.split(rendered, posix=False)

    def candidate_commands(self, pdf: Path, work_dir: Path) -> list[list[str]]:
        if self.cmd_template:
            return [self.command_from_template(self.cmd_template, pdf, work_dir)]

        if self.mineru_cmd:
            return [
                [self.mineru_cmd, "-p", str(pdf), "-o", str(work_dir), "-m", self.method, "-b", self.backend],
            ]

        return [
            [sys.executable, "-m", "mineru.cli.client", "-p", str(pdf), "-o", str(work_dir), "-m", self.method, "-b", self.backend],
            ["mineru", "-p", str(pdf), "-o", str(work_dir), "-m", self.method, "-b", self.backend],
            ["magic-pdf", "-p", str(pdf), "-o", str(work_dir), "-m", self.method],
        ]

    @staticmethod
    def run_mineru(commands: list[list[str]]) -> list[str]:
        errors: list[str] = []
        for command in commands:
            try:
                completed = subprocess.run(command, check=True)
            except FileNotFoundError:
                errors.append(f"Command not found: {command[0]}")
                continue
            except subprocess.CalledProcessError as exc:
                errors.append(f"Command failed ({exc.returncode}): {' '.join(command)}")
                continue

            if completed.returncode == 0:
                return command

        message = "\n".join(errors) if errors else "No MinerU command was attempted."
        install_hint = (
            "MinerU command was not available or failed.\n"
            "Install MinerU in the current Python environment, for example:\n"
            '  pip install --upgrade pip uv\n'
            '  uv pip install -U "mineru[all]"\n'
            "If your command name or arguments are different, pass --mineru-cmd or --cmd-template."
        )
        raise RuntimeError(f"MinerU parsing failed.\n{message}\n\n{install_hint}")

    @staticmethod
    def find_markdown_files(work_dir: Path) -> list[Path]:
        return [
            path
            for path in work_dir.rglob("*.md")
            if path.is_file() and "__MACOSX" not in path.parts and not path.name.startswith("._")
        ]

    @staticmethod
    def choose_markdown(markdown_files: list[Path], pdf_stem: str) -> Path:
        if not markdown_files:
            raise FileNotFoundError("MinerU completed but no Markdown file was found in the work directory.")

        stem_matches = [path for path in markdown_files if pdf_stem in path.stem or path.stem in pdf_stem]
        candidates = stem_matches or markdown_files
        return max(candidates, key=lambda path: path.stat().st_size)

    def final_markdown_path(self, pdf: Path, output_name: str) -> Path:
        filename = output_name.strip() or f"MinerU_markdown_{pdf.stem}.md"
        if not filename.lower().endswith(".md"):
            filename += ".md"
        return self.output_dir / filename


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Parse a PDF file or all PDFs in one directory with MinerU or magic-pdf, "
            "then copy generated Markdown files into raw_data/md_from_pdf."
        )
    )
    parser.add_argument("input", help="PDF file or directory containing PDF files.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for final Markdown files. Defaults to raw_data/md_from_pdf.",
    )
    parser.add_argument(
        "--work-dir",
        default=str(DEFAULT_WORK_DIR),
        help="Temporary MinerU output directory. Defaults to raw_data/_mineru_work.",
    )
    parser.add_argument(
        "--method",
        default="auto",
        choices=["auto", "ocr", "txt"],
        help="MinerU parse method passed with -m. Defaults to auto.",
    )
    parser.add_argument(
        "--mineru-cmd",
        default=os.getenv("MINERU_CMD", ""),
        help="Command executable to use, for example mineru or magic-pdf. Can also be set with MINERU_CMD.",
    )
    parser.add_argument(
        "--cmd-template",
        default=os.getenv("MINERU_CMD_TEMPLATE", ""),
        help=(
            "Full command template. Available placeholders: {pdf}, {work_dir}, {method}. "
            "Example: python -m mineru.cli.client -p {pdf} -o {work_dir} -m {method} -b {backend}"
        ),
    )
    parser.add_argument(
        "--backend",
        default="pipeline",
        choices=["pipeline", "vlm-engine", "hybrid-engine", "vlm-http-client", "hybrid-http-client"],
        help="MinerU backend passed with -b. Defaults to pipeline to avoid requiring CUDA.",
    )
    parser.add_argument(
        "--output-name",
        default="",
        help="Final Markdown filename. Only valid when input is a single PDF.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="When input is a directory, parse PDFs recursively.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="When input is a directory, continue parsing remaining PDFs if one file fails.",
    )
    parser.add_argument(
        "--keep-work-dir",
        action="store_true",
        help="Keep MinerU intermediate output directory after copying Markdown.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite final Markdown files if they already exist.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    parser = MinerUPdfParser(
        output_dir=args.output_dir,
        work_dir=args.work_dir,
        method=args.method,
        backend=args.backend,
        mineru_cmd=args.mineru_cmd,
        cmd_template=args.cmd_template,
        keep_work_dir=args.keep_work_dir,
        overwrite=args.overwrite,
    )
    results = parser.parse_path(
        args.input,
        output_name=args.output_name,
        recursive=args.recursive,
        continue_on_error=args.continue_on_error,
    )

    print()
    print(f"Parsed PDFs: {len(results)}")
    for result in results:
        print(f"- {result.pdf.name} -> {result.markdown}")


if __name__ == "__main__":
    main()
