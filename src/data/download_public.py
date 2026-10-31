"""Download the public EMG datasets used to extend training (CC BY 4.0).

Files go to Dataset/public/<name>/ (ignored by git: EMG-EPN-612 alone is
5.5 GB). Downloads resume after interruptions and are checked against the
published MD5 where one exists. Archives are only unpacked, never executed.

  python -m src.data.download_public                 # UCI only (the dataset used)
  python -m src.data.download_public epn612          # EMG-EPN-612, 5.5 GB (8 parallel connections)
  python -m src.data.download_public ninapro_db1     # NinaPro DB1, 27 subject zips, about 560 MB

Sources and licences:
  uci_gestures  UCI "EMG Data for Gestures", 36 people, Myo armband 8 ch,
                CC BY 4.0, https://archive.ics.uci.edu/dataset/481
  epn612        EMG-EPN-612 v2.1, 612 people, Myo armband 8 ch, CC BY 4.0,
                https://doi.org/10.5281/zenodo.4421500
  ninapro_db1   NinaPro DB1, 27 people, 10 Otto Bock electrodes (RMS envelope,
                100 Hz), https://ninapro.hevs.ch/instructions/DB1.html; cite
                Atzori et al., Scientific Data 2014 (doi:10.1038/sdata.2014.53)
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
    # One zip per subject; no published checksums.
    "ninapro_db1": {"parts": [{"url": f"https://ninapro.hevs.ch/files/DB1/Preprocessed/s{n}.zip", "file": f"s{n}.zip", "md5": None}
                              for n in range(1, 28)]},
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


def fetch_parallel(url, archive, size, parts):
    """Download in `parts` byte ranges at once (servers often limit speed per connection).

    Each range is a separate .partN file that resumes where it stopped; when all are
    complete they are joined into the archive."""
    import time
    bounds = [(i * size // parts, (i + 1) * size // parts - 1) for i in range(parts)]
    files = [archive.with_name(f"{archive.name}.part{i}") for i in range(parts)]
    for attempt in range(1, 31):
        procs = []
        for (a, b), f in zip(bounds, files):
            have = f.stat().st_size if f.exists() else 0
            if have >= b - a + 1: continue
            out = open(f, "ab")
            procs.append((subprocess.Popen(["curl", "-sS", "-L", "--fail", "-r", f"{a + have}-{b}", url], stdout=out), out))
        if not procs: break
        while any(p.poll() is None for p, _ in procs):
            done = sum(f.stat().st_size for f in files if f.exists())
            print(f"  {done / 1e9:.2f} / {size / 1e9:.2f} GB", flush=True); time.sleep(30)
        for _, out in procs: out.close()
    else:
        raise SystemExit("download did not complete after 30 attempts")
    with open(archive, "wb") as joined:
        for f in files:
            with open(f, "rb") as part:
                while block := part.read(1 << 24): joined.write(block)
    for f in files: f.unlink()


def download(name, parallel=1):
    spec = DATASETS[name]; folder = PUBLIC_DIR / name; folder.mkdir(parents=True, exist_ok=True)
    done = folder / ".extracted"
    if done.exists():
        print(f"{name}: already downloaded and extracted in {folder.relative_to(ROOT)}"); return
    for part in spec.get("parts", [spec]): fetch(name, part, folder, parallel)
    done.write_text("ok\n")
    print(f"{name}: extracted to {(folder / 'raw').relative_to(ROOT)}")


def fetch(name, spec, folder, parallel=1):
    archive = folder / spec["file"]
    print(f"{name}: downloading {spec['url']}", flush=True)
    if parallel > 1 and spec.get("size"):
        fetch_parallel(spec["url"], archive, spec["size"], parallel)
    # Large files: servers sometimes close long transfers, so resume (-C -) until complete.
    for attempt in range(1, 31):
        if archive.exists() and spec.get("size") and archive.stat().st_size >= spec["size"]: break
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download public EMG datasets into Dataset/public/")
    parser.add_argument("names", nargs="*", choices=list(DATASETS), default=["uci_gestures"])
    parser.add_argument("--parallel", type=int, default=8, help="simultaneous connections for large files")
    args = parser.parse_args(argv)
    for name in args.names: download(name, args.parallel)

if __name__ == "__main__": main()
