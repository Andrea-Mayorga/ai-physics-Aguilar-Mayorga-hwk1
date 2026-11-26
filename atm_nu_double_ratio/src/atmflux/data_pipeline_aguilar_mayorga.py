"""Data ingestion layer (HW9): fetch -> verify -> raw cache -> normalize -> SQLite cache.

Usage, from the atm_nu_double_ratio folder:
    PYTHONPATH=src python -m atmflux.data_pipeline_aguilar_mayorga            # use the cache when valid
    PYTHONPATH=src python -m atmflux.data_pipeline_aguilar_mayorga --refresh  # force real downloads
(or `make pipeline` / `make pipeline-refresh`).

Two external sources, three datasets:
    HEPData (Super-K, Richard et al. 2016): nu_mu + nubar_mu and nu_e + nubar_e unfolded spectra (CSV).
    Honda's ICRR page (HKKM2014): predicted flux at Kamioka, 20 zenith blocks (gzipped text).
URLs and expected SHA-256 come from data/provenance.json (the input registry).

Failure modes and what the code does:
    E1  timeout, connection error, HTTP 429 or 5xx -> retry with exponential backoff (tenacity,
        3 retries = 4 attempts). If every attempt fails, fall back to the raw cache when its hash
        is valid; otherwise stop with a message naming the URL. Other HTTP errors (e.g. 404) are
        not transient and are not retried.
    E2  downloaded bytes with a different SHA-256, or a truncated .gz -> reject them and do NOT
        overwrite the raw cache.
    E3  a missing or empty field in a row -> log a warning with the field, row and source URL,
        and store the documented sentinel MISSING = NaN (NULL in SQLite, field name listed in
        the `missing` column). Never 0: a zero error would give a bin infinite weight.

Internal schema (SQLite table `measurements`), one row per (dataset, energy, flavour, zenith block):
    source, dataset, flavor, kind ("bin" | "point"), e_lo_gev, e_hi_gev, e_gev,
    cosz_min, cosz_max, quantity, value, error, unit, missing
Every flux is stored as E^2 * Phi in GeV cm^-2 s^-1 sr^-1, whatever its source unit:
    Super-K: already E^2 Phi in cm^-2; error converted from percent to absolute; nu + nubar combined.
    Honda:   Phi in (m^2 s sr GeV)^-1 -> E^2 Phi * 1e-4 (m^-2 -> cm^-2); nu and nubar separate;
             grid points (kind = "point", e_lo = e_hi = e); Honda publishes no per-point error (NULL).
Canonical identifier: (source, dataset, flavor, e_lo_gev, e_hi_gev, cosz_min, cosz_max).
"""

import argparse
import csv
import gzip
import hashlib
import io
import json
import logging
import math
import platform
import re
import socket
import sqlite3
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from tenacity import (Retrying, before_sleep_log, retry_if_exception, stop_after_attempt,
                      wait_exponential)

PROJECT = Path(__file__).resolve().parents[2]
DATA = PROJECT / "data"
CACHE_DB = DATA / "cache" / "atmflux_cache.sqlite"
PROVENANCE_OUT = PROJECT / "provenance_aguilar_mayorga.json"

MISSING = float("nan")  # documented sentinel for a missing or empty field
RETRIES = 3  # retries after the first attempt (4 attempts in total)
TIMEOUT_S = 30
UNIT_E2PHI = "GeV cm^-2 s^-1 sr^-1"
USER_AGENT = "atmflux-data-pipeline/0.1 (PHYS 7440 course project)"

log = logging.getLogger("atmflux.pipeline")

DATASETS = {
    "sk_numu": {"file": "sk_numu_flux.csv", "source": "Super-K (HEPData)", "flavor": "numu+numubar",
                "format": "hepdata_csv", "version": "HEPData record ins1401192, version 1, Table 2"},
    "sk_nue": {"file": "sk_nue_flux.csv", "source": "Super-K (HEPData)", "flavor": "nue+nuebar",
               "format": "hepdata_csv", "version": "HEPData record ins1401192, version 1, Table 1"},
    "honda": {"file": "honda2014_kamioka_cosz20_solmin.d.gz", "source": "Honda HKKM2014 (ICRR)",
              "flavor": None, "format": "honda_gz",
              "version": "HKKM2014, Kamioka, no mountain, azimuth-averaged, 20 cos(zenith) blocks, solar minimum"},
}
HONDA_FLAVORS = ["numu", "numubar", "nue", "nuebar"]  # columns 1-4 of the Honda tables

TRANSFORMATIONS = {
    "hepdata_csv": [
        "drop '#' metadata lines and the header row",
        "bin edges log10(E/GeV) -> GeV (10**x); bin centre kept as e_gev = 10**logE",
        "E^2 Phi kept as published (GeV cm^-2 s^-1 sr^-1, nu + nubar combined)",
        "total error: percent -> absolute (err% / 100 * E^2 Phi); 'error +' is used and checked "
        "to equal |error -| in every row (a warning is logged otherwise)",
        "missing or empty field -> NaN sentinel (NULL in SQLite) + warning with source URL",
    ],
    "honda_gz": [
        "split into 20 cos(zenith) blocks from the 'average flux in [cosZ = a -- b ...]' headers",
        "one row per (block, energy, flavour); nu and nubar kept separate",
        "Phi (m^2 s sr GeV)^-1 -> E^2 Phi in GeV cm^-2 s^-1 sr^-1 (multiply by E^2 and by 1e-4)",
        "no per-point error is published: error = NULL (not a sentinel)",
        "missing or non-numeric field -> NaN sentinel (NULL in SQLite) + warning with source URL",
    ],
}


# ---------------------------------------------------------------- fetch (E1) and verify (E2)

class IntegrityError(RuntimeError):
    """Downloaded or cached bytes do not match the registered SHA-256 (or the .gz is truncated)."""


def is_transient(exc):
    """True for errors worth retrying: timeouts, connection problems, HTTP 429 and 5xx."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or exc.code >= 500
    return isinstance(exc, (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError))


def _urlopen(url, timeout):
    """Request url with Python's urllib. Kept for sources that accept it; see _curl_open."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


CURL_TIMEOUT_CODES = {28}  # curl exit code: operation timed out
CURL_CONNECTION_CODES = {5, 6, 7, 35, 52, 55, 56}  # resolve/connect/SSL/empty reply/send/recv


def _curl_open(url, timeout):
    """Request url with the system curl, raising the same exceptions as urllib.

    HEPData sits behind Cloudflare, which answers HTTP 403 to Python's urllib client
    (tested 2026-11-25) but serves curl. curl is used as is, with its own user agent.
    """
    try:
        proc = subprocess.run(
            ["curl", "--silent", "--show-error", "--location", "--max-time", str(timeout),
             "--output", "-", "--write-out", "\n%{http_code}", url],
            capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("curl is required to download the inputs and was not found") from exc
    if proc.returncode in CURL_TIMEOUT_CODES:
        raise TimeoutError(f"curl timed out after {timeout} s: {url}")
    if proc.returncode in CURL_CONNECTION_CODES:
        raise ConnectionError(f"curl exit {proc.returncode}: {proc.stderr.decode().strip()}")
    if proc.returncode != 0:
        raise RuntimeError(f"curl exit {proc.returncode}: {proc.stderr.decode().strip()}")
    body, _, status = proc.stdout.rpartition(b"\n")
    code = int(status)
    if code >= 400:
        raise urllib.error.HTTPError(url, code, f"HTTP {code}", None, None)
    return body


def fetch(url, opener=None, retries=RETRIES, wait=None, timeout=TIMEOUT_S):
    """Download url and return its bytes, retrying transient errors with exponential backoff.

    opener(url, timeout) does the actual request (default: curl; replaceable in tests); wait defaults to
    1 s, 2 s, 4 s ... capped at 30 s. After retries + 1 failed attempts the last error is raised.
    """
    opener = opener or _curl_open
    retrying = Retrying(
        retry=retry_if_exception(is_transient),
        stop=stop_after_attempt(retries + 1),
        wait=wait if wait is not None else wait_exponential(multiplier=1, min=1, max=30),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )
    return retrying(opener, url, timeout)


def sha256_bytes(content):
    return hashlib.sha256(content).hexdigest()


def check_integrity(content, expected_sha256, name, url):
    """Raise IntegrityError unless content has the registered hash (and, for .gz, decompresses)."""
    digest = sha256_bytes(content)
    if digest != expected_sha256:
        raise IntegrityError(f"SHA-256 mismatch for {name} from {url}: expected {expected_sha256}, "
                             f"got {digest}. The raw cache was not modified.")
    if name.endswith(".gz"):
        try:
            gzip.decompress(content)
        except (EOFError, OSError) as exc:
            raise IntegrityError(f"Truncated or corrupt gzip for {name} from {url}: {exc}") from exc


def acquire(record, raw_dir, refresh=False, opener=None, wait=None):
    """Return (bytes, access_info) for one dataset, using the raw cache when it is valid.

    The raw cache is the file in raw_dir; it is (re)written only with bytes that passed the
    integrity check, and atomically (write to a temporary file, then rename).
    """
    name, url, expected = record["file"], record["source"], record["sha256"]
    path = raw_dir / name
    cached = path.read_bytes() if path.exists() else None
    cache_valid = cached is not None and sha256_bytes(cached) == expected
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if cache_valid and not refresh:
        log.info("cache hit: %s (no download)", name)
        return cached, {"status": "cache_hit", "checked_utc": now,
                        "originally_accessed": record.get("accessed")}

    try:
        content = fetch(url, opener=opener, wait=wait)
    except Exception as exc:  # E1 exhausted, or a non-transient HTTP error
        if cache_valid:
            log.warning("download of %s failed (%s: %s); using the valid raw cache",
                        url, type(exc).__name__, exc)
            return cached, {"status": "download_failed_used_cache", "checked_utc": now,
                            "error": f"{type(exc).__name__}: {exc}",
                            "originally_accessed": record.get("accessed")}
        raise RuntimeError(f"Could not download {name} from {url} and there is no valid "
                           f"cached copy in {raw_dir}: {type(exc).__name__}: {exc}") from exc

    check_integrity(content, expected, name, url)  # E2: raises before touching the cache
    raw_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(content)
    tmp.replace(path)
    log.info("downloaded %s (%d bytes, SHA-256 verified)", name, len(content))
    return content, {"status": "downloaded", "accessed_utc": now, "bytes": len(content)}


# ---------------------------------------------------------------- normalize (E3)

def _number(text, field, row_id, url, missing):
    """Parse one numeric field; on an empty or non-numeric value log it and return MISSING."""
    text = (text or "").strip().rstrip("%").strip()
    try:
        if text == "":
            raise ValueError("empty")
        return float(text)
    except ValueError:
        log.warning("missing field '%s' in %s (source: %s); stored sentinel NaN", field, row_id, url)
        missing.append(field)
        return MISSING


def normalize_hepdata(content, dataset, url):
    """Super-K HEPData CSV -> rows of the internal schema."""
    spec = DATASETS[dataset]
    lines = [ln for ln in content.decode("utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
    rows = []
    for i, fields in enumerate(list(csv.reader(io.StringIO("\n".join(lines))))[1:]):  # skip header
        fields = fields + [""] * (5 - len(fields))
        missing = []
        row_id = f"{dataset} row {i}"
        log_e, lo, hi, e2phi, err_pct = (
            _number(fields[j], name, row_id, url, missing)
            for j, name in enumerate(["log10_E_center", "log10_E_low", "log10_E_high",
                                      "E2Phi", "error_percent"]))
        if len(fields) > 5 and fields[5].strip():  # "error -" column: must mirror "error +"
            err_minus = fields[5].strip().rstrip("%")
            if abs(abs(float(err_minus)) - err_pct) > 1e-9:
                log.warning("asymmetric error in %s (source: %s): +%s%% / %s%%; using +",
                            row_id, url, err_pct, err_minus)
        rows.append({
            "source": spec["source"], "dataset": dataset, "flavor": spec["flavor"], "kind": "bin",
            "e_lo_gev": 10.0**lo, "e_hi_gev": 10.0**hi, "e_gev": 10.0**log_e,
            "cosz_min": None, "cosz_max": None, "quantity": "E2Phi",
            "value": e2phi, "error": err_pct / 100.0 * e2phi, "unit": UNIT_E2PHI,
            "missing": ",".join(missing),
        })
    return rows


def normalize_honda(content, dataset, url):
    """Honda HKKM2014 table -> rows of the internal schema (E^2 Phi in cm^-2)."""
    spec = DATASETS[dataset]
    rows, block = [], None
    for line in gzip.decompress(content).decode("utf-8").splitlines():
        if line.startswith("average"):
            m = re.search(r"cosZ\s*=\s*([-\d.]+)\s*--\s*([-\d.]+)", line)
            block = (float(m.group(1)), float(m.group(2)))
            continue
        parts = line.split()
        if not parts or not parts[0][0].isdigit():
            continue  # column-header lines
        parts = parts + [""] * (5 - len(parts))
        missing = []
        row_id = f"{dataset} cosZ {block} E={parts[0]}"
        energy = _number(parts[0], "E", row_id, url, missing)
        for col, flavor in enumerate(HONDA_FLAVORS, start=1):
            flavor_missing = []
            phi = _number(parts[col], flavor, row_id, url, flavor_missing)
            rows.append({
                "source": spec["source"], "dataset": dataset, "flavor": flavor, "kind": "point",
                "e_lo_gev": energy, "e_hi_gev": energy, "e_gev": energy,
                "cosz_min": min(block), "cosz_max": max(block), "quantity": "E2Phi",
                "value": energy**2 * phi * 1e-4, "error": None, "unit": UNIT_E2PHI,
                "missing": ",".join(missing + flavor_missing),
            })
    return rows


NORMALIZERS = {"hepdata_csv": normalize_hepdata, "honda_gz": normalize_honda}


# ---------------------------------------------------------------- SQLite cache

SCHEMA = """
CREATE TABLE measurements (
    source TEXT NOT NULL, dataset TEXT NOT NULL, flavor TEXT NOT NULL, kind TEXT NOT NULL,
    e_lo_gev REAL, e_hi_gev REAL, e_gev REAL, cosz_min REAL, cosz_max REAL,
    quantity TEXT NOT NULL, value REAL, error REAL, unit TEXT NOT NULL, missing TEXT NOT NULL
);
CREATE TABLE datasets (
    dataset TEXT PRIMARY KEY, source TEXT, url TEXT, sha256 TEXT, n_rows INTEGER, n_missing INTEGER
);
"""
COLUMNS = ["source", "dataset", "flavor", "kind", "e_lo_gev", "e_hi_gev", "e_gev", "cosz_min",
           "cosz_max", "quantity", "value", "error", "unit", "missing"]


def _sql_value(x):
    """NaN sentinel -> NULL (SQLite has no NaN); everything else unchanged."""
    return None if isinstance(x, float) and math.isnan(x) else x


def write_cache(db_path, rows_by_dataset, registry):
    """Rebuild the SQLite cache from scratch in one transaction."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_name(db_path.name + ".part")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    with con:
        con.executescript(SCHEMA)
        for dataset, rows in rows_by_dataset.items():
            con.executemany(f"INSERT INTO measurements VALUES ({','.join('?' * len(COLUMNS))})",
                            [[_sql_value(r[c]) for c in COLUMNS] for r in rows])
            rec = registry[dataset]
            con.execute("INSERT INTO datasets VALUES (?,?,?,?,?,?)",
                        (dataset, DATASETS[dataset]["source"], rec["source"], rec["sha256"],
                         len(rows), sum(1 for r in rows if r["missing"])))
    con.close()
    tmp.replace(db_path)


def read_cache(db_path=CACHE_DB, dataset=None):
    """Return the cached rows as a list of dicts (optionally one dataset only)."""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    query, args = "SELECT * FROM measurements", ()
    if dataset:
        query, args = query + " WHERE dataset = ?", (dataset,)
    rows = [dict(r) for r in con.execute(query, args)]
    con.close()
    return rows


# ---------------------------------------------------------------- pipeline

def _git_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT, capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=PROJECT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return {"commit": out, "uncommitted_changes_in_project": bool(dirty)}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "uncommitted_changes_in_project": None}


def run(data_dir=DATA, db_path=CACHE_DB, provenance_path=PROVENANCE_OUT, refresh=False,
        opener=None, wait=None):
    """Run the whole ingestion and return the provenance record (also written to provenance_path)."""
    data_dir = Path(data_dir)
    registry = {d: rec for rec in json.loads((data_dir / "provenance.json").read_text())
                for d, spec in DATASETS.items() if spec["file"] == rec["file"]}
    rows_by_dataset, records = {}, []
    for dataset, spec in DATASETS.items():
        rec = registry[dataset]
        content, access = acquire(rec, data_dir, refresh=refresh, opener=opener, wait=wait)
        rows = NORMALIZERS[spec["format"]](content, dataset, rec["source"])
        rows_by_dataset[dataset] = rows
        records.append({
            "dataset": dataset, "file": f"data/{spec['file']}", "source_url": rec["source"],
            "source": spec["source"], "reference": rec["reference"], "version": spec["version"],
            "sha256": rec["sha256"], "access": access,
            "transformations": TRANSFORMATIONS[spec["format"]],
            "rows_in_cache": len(rows), "rows_with_missing_fields": sum(1 for r in rows if r["missing"]),
        })
    write_cache(Path(db_path), rows_by_dataset, registry)
    provenance = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pipeline": "atmflux.data_pipeline_aguilar_mayorga",
        "code_version": _git_commit(),
        "environment": {"python": platform.python_version(), "tenacity": version("tenacity"),
                        "platform": platform.platform(terse=True)},
        "refresh_requested": refresh,
        "cache": {"raw": "data/ (files verified against data/provenance.json)",
                  "normalized": str(Path(db_path).relative_to(PROJECT)) if Path(db_path).is_relative_to(PROJECT) else str(db_path),
                  "table": "measurements", "unit": UNIT_E2PHI},
        "missing_field_sentinel": "NaN in Python, NULL in SQLite; field names listed in column 'missing'",
        "retry_policy": {"retries": RETRIES, "backoff": "exponential, 1 s doubling, max 30 s",
                         "retried_errors": "timeout, connection error, HTTP 429, HTTP 5xx"},
        "datasets": records,
    }
    Path(provenance_path).write_text(json.dumps(provenance, indent=2) + "\n")
    return provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true",
                        help="download every source again even if the raw cache is valid")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    prov = run(refresh=args.refresh)
    for d in prov["datasets"]:
        print(f"{d['dataset']:8s} {d['access']['status']:28s} rows={d['rows_in_cache']:5d} "
              f"missing={d['rows_with_missing_fields']}")
    print(f"Cache: {prov['cache']['normalized']}   Provenance: {PROVENANCE_OUT.name}")


if __name__ == "__main__":
    main()
