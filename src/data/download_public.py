"""Download the public EMG datasets used to extend training (CC BY 4.0).

Files go to Dataset/public/<name>/ (ignored by git: EMG-EPN-612 alone is
5.5 GB). Downloads resume after interruptions and are checked against the
published MD5 where one exists. Archives are only unpacked, never executed.

  python -m src.data.download_public                 # UCI only (the dataset used)
  python -m src.data.download_public epn612          # optional, 5.5 GB, not used so far

Sources and licences:
  uci_gestures  UCI "EMG Data for Gestures", 36 people, Myo armband 8 ch,
                CC BY 4.0, https://archive.ics.uci.edu/dataset/481
  epn612        EMG-EPN-612 v2.1, 612 people, Myo armband 8 ch, CC BY 4.0,
                https://doi.org/10.5281/zenodo.4421500 (optional; the
                download was stopped and the project does not use it)
"""
import argparse, hashlib, subprocess, sys, zipfile
from pathlib import Path
from src.utils.config import ROOT

PUBLIC_DIR = ROOT / "Dataset/public"
DATASETS = {
    "uci_gestures": {"url": "https://archive.ics.uci.edu/static/public/481/emg+data+for+gestures.zip",
                     "file": "emg_data_for_gestures.zip", "md5": None},
    "epn612": {"url": "https://zenodo.org/api/records/4421500/files/EMG-EPN612%20Dataset.zip/content",
               "file": "EMG-EPN612_Dataset.zip", "md5": "98bd3c315efab607cc54b2ed2f8f3ada", "size": 5483385161},
}


def md5sum(path, chunk=1 << 22):
    digest = hashlib.md5()
    with open(path, "rb") as f:
        while block := f.read(chunk): digest.update(block)
    return digest.hexdigest()


def safe_extract(archive, dest):
    """Unpack a zip, refusing members that would land outside dest."""
    dest = dest.resolve()
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            target = (dest / member.filename).resolve()
            if not target.is_relative_to(dest): raise RuntimeError(f"Unsafe path in archive: {member.filename}")
        z.extractall(dest)


def download(name):
    spec = DATASETS[name]; folder = PUBLIC_DIR / name; folder.mkdir(parents=True, exist_ok=True)
    archive = folder / spec["file"]; done = folder / ".extracted"
    if done.exists():
        print(f"{name}: already downloaded and extracted in {folder.relative_to(ROOT)}"); return
    print(f"{name}: downloading {spec['url']}", flush=True)
    # Large files: servers sometimes close long transfers, so resume (-C -) until complete.
    for attempt in range(1, 31):
        result = subprocess.run(["curl", "-L", "--fail", "--retry", "10", "--retry-delay", "5", "-C", "-", "-o", str(archive), spec["url"]])
        size = archive.stat().st_size if archive.exists() else 0
        if result.returncode == 0 and (spec.get("size") is None or size >= spec["size"]): break
        print(f"{name}: attempt {attempt} stopped at {size / 1e9:.2f} GB (curl exit {result.returncode}); resuming", flush=True)
    else:
        raise SystemExit(f"{name}: download did not complete after 30 attempts")
    if spec["md5"]:
        got = md5sum(archive)
        if got != spec["md5"]: raise SystemExit(f"{name}: MD5 mismatch ({got} != {spec['md5']}); delete {archive} and retry")
        print(f"{name}: MD5 verified")
    else:
        print(f"{name}: MD5 {md5sum(archive)} (no published checksum)")
    safe_extract(archive, folder / "raw")
    done.write_text("ok\n")
    print(f"{name}: extracted to {(folder / 'raw').relative_to(ROOT)}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download public EMG datasets into Dataset/public/")
    parser.add_argument("names", nargs="*", choices=list(DATASETS), default=["uci_gestures"])
    args = parser.parse_args(argv)
    for name in args.names: download(name)

if __name__ == "__main__": main()
