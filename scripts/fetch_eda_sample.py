"""Download and extract a real FDA FAERS sample partition for EDA."""

import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

EDA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "eda_sample"


def fetch_eda_sample():
    EDA_DIR.mkdir(parents=True, exist_ok=True)
    zip_target = EDA_DIR / "openfda_2004q3_part1.json.zip"
    url = "https://download.open.fda.gov/drug/event/2004q3/drug-event-0001-of-0005.json.zip"

    # Check if already extracted
    extracted_json = list(EDA_DIR.glob("*.json"))
    if extracted_json:
        print(f"Sample JSON already extracted: {extracted_json[0]}")
        return extracted_json[0]

    print(f"Downloading real 2004 Q3 openFDA partition from {url}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, stream=True, timeout=60)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))
    with open(zip_target, "wb") as f, tqdm(
        desc="Downloading 2004 Q3 sample",
        total=total_size,
        unit="iB",
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            size = f.write(chunk)
            bar.update(size)

    print("Extracting ZIP archive...")
    with zipfile.ZipFile(zip_target, "r") as zf:
        zf.extractall(EDA_DIR)

    if zip_target.exists():
        zip_target.unlink()

    extracted = list(EDA_DIR.glob("*.json"))[0]
    print(f"Extracted sample file: {extracted} ({extracted.stat().st_size / (1024*1024):.2f} MB)")
    return extracted


if __name__ == "__main__":
    fetch_eda_sample()
