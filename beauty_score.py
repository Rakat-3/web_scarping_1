import requests
from bs4 import BeautifulSoup
from pathlib import Path
import csv
import re
import time

# --- CONFIG ---
IMG_DIR = Path(r"C:\Users\rakat.murshed\Documents\CFD")
OUTPUT_CSV = Path(r"C:\Users\rakat.murshed\Documents\AMFD\CFD.csv")
BASE_URL = "https://www.beautyscoretest.com"
FORM_URL = BASE_URL + "/"
#  Add/adjust image extensions as needed:
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# --- HELPERS ---
def extract_csrf_token(html: str) -> str | None:
    """Finds the hidden _token value from the page."""
    soup = BeautifulSoup(html, "html.parser")
    token_input = soup.find("input", {"name": "_token"})
    return token_input["value"] if token_input and token_input.has_attr("value") else None

def extract_beauty_score(html: str) -> str | None:
    """
    Try to pull a numeric 'beauty score' from the response.
    Heuristics: look for 'score' phrases or patterns like 'xx/100'.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    # common patterns: "Beauty Score: 78", "Score: 78/100", etc.
    patterns = [
        r"(?i)beauty\s*score[^0-9]*([0-9]+(?:\.[0-9]+)?)",
        r"(?i)score[^0-9]*([0-9]+(?:\.[0-9]+)?)\s*/\s*100",
        r"(?i)\b([0-9]+(?:\.[0-9]+)?)\s*/\s*100\b",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1)

    # Fallback: first nice-looking number between 0 and 100 near the word 'score'
    for m in re.finditer(r"(?i)(score.{0,30}?)(\b[0-9]+(?:\.[0-9]+)?\b)", text):
        try:
            val = float(m.group(2))
            if 0 <= val <= 100:
                return m.group(2)
        except:
            pass

    return None

def find_images(folder: Path):
    for p in folder.rglob("*"):
        if p.suffix.lower() in IMG_EXTS and p.is_file():
            yield p

# --- MAIN ---
def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    })

    # 1) Load homepage to get CSRF token
    resp = session.get(FORM_URL, timeout=30)
    resp.raise_for_status()
    csrf = extract_csrf_token(resp.text)
    if not csrf:
        raise RuntimeError("Could not find CSRF token (_token). Page structure may have changed.")

    # 2) Prepare CSV
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    write_header = not OUTPUT_CSV.exists()
    with OUTPUT_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["filename", "score", "status"])

        # 3) Iterate images and upload
        for img_path in find_images(IMG_DIR):
            try:
                with img_path.open("rb") as fp:
                    files = {"face": (img_path.name, fp, "application/octet-stream")}
                    data = {"_token": csrf}
                    # Submit to "/"
                    r = session.post(FORM_URL, files=files, data=data, timeout=60)
                    r.raise_for_status()

                score = extract_beauty_score(r.text)
                status = "ok" if score is not None else "no_score_found"
                writer.writerow([str(img_path), score if score else "", status])
                print(f"{img_path.name}: {score if score else 'N/A'} ({status})")

                # polite pause to avoid hammering the site
                time.sleep(1.0)

            except Exception as e:
                writer.writerow([str(img_path), "", f"error: {e.__class__.__name__}"])
                print(f"{img_path.name}: error -> {e}")

if __name__ == "__main__":
    main()
