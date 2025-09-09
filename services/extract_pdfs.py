import subprocess
import tempfile
from pathlib import Path
import os

class ExtractPdfs:
     
    @staticmethod
    def extraction(pdf_bytes: bytes, filename: str = "uploaded.pdf") -> dict:
        """
        Convert PDF bytes to text using `pdftotext -layout`.
        Writes the PDF to a temp file, extracts text into another temp file,
        then reads the text back into Python.
        Returns a dict with filename and extracted text.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, filename)
            txt_path = os.path.join(tmpdir, "output.txt")

            # 1. Write the incoming bytes to a temp PDF file
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)

            try:
                # 2. Run pdftotext on the temp PDF -> temp TXT
                subprocess.run(
                    ["pdftotext", "-layout", pdf_path, txt_path],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                # 3. Read back the extracted text
                with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()

                return {
                    "filename": filename,
                    "text": text
                }

            except subprocess.CalledProcessError as e:
                return {
                    "filename": filename,
                    "text": "",
                    "error": e.stderr.decode(errors="ignore")
                }
