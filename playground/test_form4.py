"""
Filter fixtures (no network), then optional live kept-vs-dropped counts:

    uv run python playground/test_form4.py
    uv run python playground/test_form4.py NVDA AAPL
"""

from __future__ import annotations

from collections import Counter

import httpx

from app.config.settings import Settings
from app.scrapers.edgar import CikIndex, FilingDocuments
from app.scrapers.form4 import collect_form4, decide_form4, parse_form4_xml


def _filing(
    *,
    owner: str = "Huang Jen-Hsun",
    title: str = "President and CEO",
    officer: str = "1",
    director: str = "1",
    doc: str = "4",
    code: str = "P",
    shares: str = "15000",
    price: str = "118.40",
    footnote: str = "",
    remarks: str = "",
) -> str:
    note = ""
    ref = ""
    if footnote:
        ref = '<footnoteId id="F1"/>'
        note = f'<footnotes><footnote id="F1">{footnote}</footnote></footnotes>'
    remark = f"<remarks>{remarks}</remarks>" if remarks else ""
    return f"""\
<ownershipDocument>
  <documentType>{doc}</documentType>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>{owner}</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>{director}</isDirector>
      <isOfficer>{officer}</isOfficer>
      <officerTitle>{title}</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>{shares}</value></transactionShares>
        <transactionPricePerShare><value>{price}</value></transactionPricePerShare>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>76000000</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
      {ref}
    </nonDerivativeTransaction>
  </nonDerivativeTable>
  {note}
  {remark}
</ownershipDocument>
"""


def _reason(xml: str) -> str:
    parsed = parse_form4_xml(xml)
    assert parsed is not None
    reason, _kept = decide_form4(parsed)
    return reason


def check_fixtures() -> None:
    buy = _filing(code="P", shares="15000", price="118.40")
    sale = _filing(code="S", shares="5000", price="200")
    plan = _filing(
        code="S",
        shares="10000",
        price="120",
        footnote="The sales reported were effected pursuant to a Rule 10b5-1 trading plan.",
    )
    award = _filing(code="A", shares="20000", price="0")
    tax = _filing(code="F", shares="800", price="120")
    exercise = _filing(code="M", shares="5000", price="4.50")
    small = _filing(code="S", shares="100", price="200")
    owner_only = _filing(code="S", shares="5000", price="200", officer="0", director="0")
    amendment = _filing(code="P", doc="4/A")
    not_plan = _filing(
        code="S",
        shares="5000",
        price="200",
        footnote="These shares were not sold pursuant to a trading plan.",
    )

    assert _reason(buy) == "kept", _reason(buy)
    assert _reason(sale) == "kept", _reason(sale)
    assert _reason(plan) == "plan", _reason(plan)
    assert _reason(award) == "code", _reason(award)
    assert _reason(tax) == "code", _reason(tax)
    assert _reason(exercise) == "code", _reason(exercise)
    assert _reason(small) == "below_floor", _reason(small)
    assert _reason(owner_only) == "not_officer", _reason(owner_only)
    assert _reason(amendment) == "amendment", _reason(amendment)
    assert _reason(not_plan) == "kept", _reason(not_plan)
    print("fixtures ok — RSU / tax / 10b5-1 / tiny sales / non-officers never kept")


def check_live(tickers: list[str] | None = None) -> None:
    settings = Settings()
    symbols = [item.upper() for item in (tickers or settings.tickers)]
    cutoff = settings.window_start().date()
    totals: Counter[str] = Counter()
    headers = {
        "User-Agent": settings.sec_user_agent,
        "Accept-Encoding": "gzip, deflate",
    }
    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        ticker_map = CikIndex(settings.data_dir).load(client)
        documents = FilingDocuments(client)
        for symbol in symbols:
            info = ticker_map.get(symbol)
            if not info:
                print(f"{symbol}: no CIK")
                continue
            items, drops = collect_form4(documents, symbol, info["cik"], cutoff)
            totals.update(drops)
            parts = " ".join(
                f"{reason}={count}" for reason, count in sorted(drops.items())
            )
            print(f"{symbol}: {parts or 'none'} kept_items={len(items)}")
            for item in items:
                print(f"  - {item['title']}")
    print("totals", " ".join(f"{k}={v}" for k, v in sorted(totals.items())) or "none")


if __name__ == "__main__":
    import sys

    check_fixtures()
    check_live(sys.argv[1:] or None)
