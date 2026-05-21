import os
import shutil
import subprocess
import tempfile
import logging

logger = logging.getLogger(__name__)


def find_browser_path() -> str:
    """
    ค้นหา Chromium / Chrome ที่ใช้ได้บนเครื่อง
    รองรับทั้ง Linux (Docker) และ Windows (dev)
    """
    # Linux paths (Docker / Server)
    linux_candidates = [
        "chromium-browser",
        "chromium",
        "google-chrome-stable",
        "google-chrome",
    ]
    for name in linux_candidates:
        path = shutil.which(name)
        if path:
            return path

    # Windows paths (dev machine)
    windows_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    for path in windows_candidates:
        if os.path.exists(path):
            return path

    raise FileNotFoundError(
        "ไม่พบ Chromium / Chrome บนเครื่อง — "
        "กรุณาติดตั้ง chromium-browser (apt install chromium-browser)"
    )


def html_to_pdf(html_content: str) -> bytes:
    """
    แปลง HTML string → PDF bytes โดยใช้ Chromium headless --print-to-pdf

    ขั้นตอน:
      1. เขียน HTML ลง temp file
      2. เรียก chromium-browser --headless --print-to-pdf=<out.pdf> <in.html>
      3. อ่าน PDF กลับมาเป็น bytes
      4. ลบ temp files ทิ้ง

    Returns:
        bytes ของ PDF ที่ได้
    """
    browser_path = find_browser_path()

    # สร้าง temp dir เพื่อเก็บไฟล์ HTML + PDF
    tmp_dir = tempfile.mkdtemp(prefix="voucher_")
    html_path = os.path.join(tmp_dir, "voucher.html")
    pdf_path = os.path.join(tmp_dir, "voucher.pdf")

    try:
        # 1) เขียน HTML
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # 2) แปลงด้วย Chromium headless
        cmd = [
            browser_path,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",                       # CRITICAL: จำเป็นสำหรับ Docker
            "--disable-dev-shm-usage",            # CRITICAL: ป้องกัน Chrome แครชจากแชร์เมมโมรี่ไม่พอ
            "--run-all-compositor-stages-before-draw",
            f"--print-to-pdf={pdf_path}",
            "--no-pdf-header-footer",
            html_path,
        ]

        logger.info("Running: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            timeout=30,
        )
        logger.info("Chromium stdout: %s", result.stdout.decode(errors="replace"))
        logger.info("Chromium stderr: %s", result.stderr.decode(errors="replace"))

        # 3) อ่าน PDF
        if not os.path.exists(pdf_path):
            raise RuntimeError("Chromium ทำงานสำเร็จแต่ไม่พบไฟล์ PDF ที่สร้างขึ้น")

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        return pdf_bytes

    finally:
        # 4) ลบ temp files
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            logger.warning("ไม่สามารถลบ temp dir: %s", tmp_dir)
