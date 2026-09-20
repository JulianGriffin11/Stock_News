"""SEC Form 4: parse ownership XML and keep officer/director open-market buys and large discretionary sales."""

from __future__ import annotations

import logging
import re
from collections import Counter
from collections.abc import Collection
from datetime import UTC, date, datetime
from xml.etree import ElementTree

import feedparser

from app.scrapers.edgar import FilingDocuments, archive_url
from app.scrapers.schemas import RawItem

FORM4_ATOM = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcompany&CIK={cik10}&type=4&dateb=&owner=only&count=100&output=atom"
)
FORM4_KEEP_CODES = frozenset({"P", "S"})
FORM4_SALE_FLOOR = 100_000.0
FORM4_PER_TICKER_CAP = 2
_ACCESSION_RE = re.compile(r"(\d{10}-\d{2}-\d{6})")
_PLAN_RE = re.compile(
    r"10b5[-–\s]?1|pursuant to.{0,60}trading plan|rule\s+10b-?5-?1",
    re.IGNORECASE,
)
_NOT_PLAN_RE = re.compile(
    r"not\s+(?:\w+\s+){0,4}(?:pursuant to|under).{0,60}"
    r"(?:10b5|trading plan)",
    re.IGNORECASE,
)

log = logging.getLogger("digest.scrapers.form4")


def is_10b5_1_text(text: str) -> bool:
    if not text or _NOT_PLAN_RE.search(text):
        return False
    return _PLAN_RE.search(text) is not None


def parse_form4_xml(xml_text: str) -> dict | None:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return None
    remarks = _xtext(root, ".//{*}remarks")
    footnotes = {
        node.get("id") or "": (node.text or "")
        for node in root.findall(".//{*}footnote")
        if node.get("id")
    }
    txs: list[dict] = []
    for node in root.findall(".//{*}nonDerivativeTransaction"):
        code = _xtext(node, ".//{*}transactionCode").upper()
        if not code:
            continue
        shares = _num(_xtext(node, ".//{*}transactionShares"))
        price = _num(_xtext(node, ".//{*}transactionPricePerShare"))
        after = _xtext(node, ".//{*}sharesOwnedFollowingTransaction")
        notes = [
            footnotes.get(fid.get("id") or "", "")
            for fid in node.findall(".//{*}footnoteId")
        ]
        notes.append(remarks)
        txs.append(
            {
                "code": code,
                "shares": shares,
                "price": price,
                "value": shares * price,
                "shares_after": _num(after) if after else None,
                "is_plan": any(is_10b5_1_text(note) for note in notes if note),
            }
        )
    owner = _xtext(root, ".//{*}rptOwnerName")
    if not owner and not txs:
        return None
    return {
        "document_type": _xtext(root, ".//{*}documentType") or "4",
        "owner": owner,
        "title": _xtext(root, ".//{*}officerTitle"),
        "is_officer": _xtrue(root, ".//{*}isOfficer"),
        "is_director": _xtrue(root, ".//{*}isDirector"),
        "txs": txs,
    }


def decide_form4(
    filing: dict,
    *,
    sale_floor: float = FORM4_SALE_FLOOR,
) -> tuple[str, list[dict]]:
    if "/A" in str(filing.get("document_type") or "").upper():
        return "amendment", []
    if not (filing.get("is_officer") or filing.get("is_director")):
        return "not_officer", []

    kept: list[dict] = []
    saw_keep = saw_plan = saw_floor = False
    for tx in filing.get("txs") or []:
        if tx["code"] not in FORM4_KEEP_CODES:
            continue
        saw_keep = True
        if tx["code"] == "S":
            if tx["is_plan"]:
                saw_plan = True
                continue
            if tx["value"] < sale_floor:
                saw_floor = True
                continue
        kept.append(tx)
    if kept:
        return "kept", kept
    if not saw_keep:
        return "code", []
    if saw_plan and not saw_floor:
        return "plan", []
    if saw_floor:
        return "below_floor", []
    return "code", []


def fetch_form4(
    documents: FilingDocuments,
    ticker: str,
    cik: int,
    cutoff: date,
    skip_ids: Collection[str] | None = None,
) -> list[RawItem]:
    items, drops = collect_form4(documents, ticker, cik, cutoff, skip_ids)
    if drops:
        parts = " ".join(f"{reason}={count}" for reason, count in sorted(drops.items()))
        log.debug("ticker=%s form4 %s", ticker, parts)
    return items


def collect_form4(
    documents: FilingDocuments,
    ticker: str,
    cik: int,
    cutoff: date,
    skip_ids: Collection[str] | None = None,
) -> tuple[list[RawItem], Counter[str]]:
    body = documents.get(FORM4_ATOM.format(cik10=f"{cik:010d}"))
    if not body:
        return [], Counter()
    known = set(skip_ids) if skip_ids else set()
    drops: Counter[str] = Counter()
    ranked: list[tuple[RawItem, float, bool]] = []
    for entry in feedparser.parse(body).entries:
        reason, item, value, has_buy = _form4_entry(
            documents, entry, ticker, cutoff, known
        )
        if reason is None:
            continue
        if item is None:
            drops[reason] += 1
            continue
        ranked.append((item, value, has_buy))
    ranked.sort(key=lambda row: (row[2], row[1]), reverse=True)
    kept_rows = ranked[:FORM4_PER_TICKER_CAP]
    extra = len(ranked) - len(kept_rows)
    if extra:
        drops["capped"] += extra
    if kept_rows:
        drops["kept"] += len(kept_rows)
    return [item for item, _value, _buy in kept_rows], drops


def _form4_entry(
    documents: FilingDocuments,
    entry: object,
    ticker: str,
    cutoff: date,
    known: set[str],
) -> tuple[str | None, RawItem | None, float, bool]:
    title = str(getattr(entry, "title", "") or "")
    form = ""
    for tag in getattr(entry, "tags", None) or []:
        term = str(tag.get("term") or "")
        if term:
            form = term
            break
    form = form or (title.split()[0] if title else "4")
    if "/A" in form.upper():
        return "amendment", None, 0.0, False
    parsed_date = getattr(entry, "updated_parsed", None) or getattr(
        entry, "published_parsed", None
    )
    if not parsed_date:
        return None, None, 0.0, False
    filed = date(int(parsed_date[0]), int(parsed_date[1]), int(parsed_date[2]))
    if filed < cutoff:
        return None, None, 0.0, False
    link = str(getattr(entry, "link", "") or "")
    match = _ACCESSION_RE.search(f"{getattr(entry, 'id', '')} {link} {title}")
    if not match:
        return "parse_error", None, 0.0, False
    accession = match.group(1)
    if accession in known:
        return "skipped_known", None, 0.0, False
    cik_match = re.search(r"/data/(\d+)/", link)
    filer_cik = int(cik_match.group(1)) if cik_match else int(accession.split("-")[0])
    xml_url = _form4_xml_url(documents, filer_cik, accession)
    xml_text = documents.get(xml_url) if xml_url else None
    parsed = parse_form4_xml(xml_text) if xml_text else None
    if parsed is None:
        return "parse_error", None, 0.0, False
    reason, kept = decide_form4(parsed)
    if reason != "kept":
        return reason, None, 0.0, False
    owner = parsed["owner"] or "insider"
    item: RawItem = {
        "source": "sec",
        "ticker": ticker,
        "title": _form4_title(ticker, owner, kept),
        "url": link or xml_url or "",
        "published_at": datetime(
            filed.year, filed.month, filed.day, tzinfo=UTC
        ).isoformat(),
        "raw_text": _form4_raw_text(ticker, filed, parsed, kept),
        "external_id": accession,
    }
    value = sum(tx["value"] for tx in kept)
    return "kept", item, value, any(tx["code"] == "P" for tx in kept)


def _form4_title(ticker: str, owner: str, kept: list[dict]) -> str:
    verbs = [
        f"{'bought' if tx['code'] == 'P' else 'sold'} {tx['shares']:,.0f} shares"
        for tx in kept
    ]
    return f"{ticker} Form 4 — {owner} {', '.join(verbs)}"


def _form4_raw_text(
    ticker: str,
    filed: date,
    parsed: dict,
    kept: list[dict],
) -> str:
    bits = [_tx_line(tx) for tx in kept]
    after = next(
        (tx["shares_after"] for tx in reversed(kept) if tx["shares_after"] is not None),
        None,
    )
    roles = ", ".join(
        label
        for label, flag in (
            ("officer", parsed["is_officer"]),
            ("director", parsed["is_director"]),
        )
        if flag
    )
    title_bit = f", {parsed['title']}" if parsed["title"] else ""
    after_bit = f" Shares after: {after:,.0f}." if after is not None else ""
    owner = parsed["owner"] or "insider"
    return (
        f"{ticker} Form 4 filed {filed.isoformat()}. "
        f"Reporting owner: {owner}{title_bit} ({roles or 'reporting owner'}). "
        f"{' '.join(bits)}{after_bit} Not a Rule 10b5-1 plan."
    )


def _tx_line(tx: dict) -> str:
    kind = (
        "Open-market purchase (P)" if tx["code"] == "P" else "Open-market sale (S)"
    )
    price = f"${tx['price']:,.2f}" if tx["price"] else "unreported price"
    return f"{kind}: {tx['shares']:,.0f} shares at {price} (${tx['value']:,.0f})."


def _form4_xml_url(
    documents: FilingDocuments, cik: int, accession: str
) -> str | None:
    xmls = [
        name
        for name in documents.directory_names(cik, accession)
        if name.lower().endswith(".xml")
        and not name.lower().startswith("xsl")
        and "xsd" not in name.lower()
    ]
    for name in xmls:
        if "form4" in name.lower() or "form-4" in name.lower():
            return archive_url(cik, accession, name)
    return archive_url(cik, accession, xmls[0]) if xmls else None


def _xtext(el: ElementTree.Element | None, path: str) -> str:
    if el is None:
        return ""
    node = el.find(path)
    if node is None:
        return ""
    inner = node.find("{*}value")
    return ((inner.text if inner is not None else None) or node.text or "").strip()


def _xtrue(el: ElementTree.Element | None, path: str) -> bool:
    return _xtext(el, path).lower() in {"1", "true", "yes"}


def _num(text: str) -> float:
    cleaned = text.replace(",", "").replace("$", "").strip()
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0
