#!/usr/bin/env python3
"""
customs-doc-classifier — shipping documents → HS tariff codes, customs classification,
duty estimates, compliance flags, restricted goods alerts, document completeness check
"""
import anthropic, base64, json, re, sys
from pathlib import Path

SYSTEM = """You are a licensed customs broker and international trade compliance specialist
with expertise in HS tariff classification across major trade jurisdictions.

Analyze this shipping document and provide complete customs classification.

Rules:
- HS codes should be 6-digit minimum (add jurisdiction-specific digits where confident)
- Duty rates are approximate — always recommend verification with official tariff schedules
- Flag any restricted, regulated, or prohibited goods immediately
- Note document completeness issues that would cause customs delays

Return ONLY valid JSON — no markdown, no explanation.

{
  "document_type": "commercial_invoice|packing_list|bill_of_lading|airway_bill|certificate_of_origin|customs_declaration|combined",
  "shipment_summary": {
    "shipper": "string or null",
    "consignee": "string or null",
    "origin_country": "ISO-2 code or null",
    "destination_country": "ISO-2 code or null",
    "shipment_date": "YYYY-MM-DD or null",
    "incoterms": "FOB|CIF|DDP|EXW|DAP|string or null",
    "total_value": number_or_null,
    "currency": "string or null",
    "total_weight_kg": number_or_null
  },
  "line_items": [
    {
      "description": "product description from document",
      "quantity": number_or_null,
      "unit": "string",
      "unit_value": number_or_null,
      "total_value": number_or_null,
      "hs_code": {
        "code": "NNNNNN or NNNNNNNN",
        "description": "official HS chapter description",
        "confidence": "high|medium|low",
        "reasoning": "why this HS code was assigned",
        "alternative_codes": ["other possible codes if uncertain"]
      },
      "duty_estimate": {
        "us_mfn_rate_pct": number_or_null,
        "eu_mfn_rate_pct": number_or_null,
        "uk_mfn_rate_pct": number_or_null,
        "notes": "any special rates, FTA applicability, or anti-dumping duties"
      },
      "compliance_flags": [
        {
          "flag": "description",
          "severity": "stop|high|medium|low",
          "jurisdiction": "US|EU|UK|global",
          "action_required": "string"
        }
      ]
    }
  ],
  "document_completeness": {
    "score": number_0_to_100,
    "missing_fields": ["list of fields required for customs clearance that are absent"],
    "recommended_supporting_docs": ["certificate of origin","material safety data sheet","..."]
  },
  "compliance_summary": {
    "restricted_goods_detected": true_or_false,
    "dual_use_potential": true_or_false,
    "sanctions_risk": "none|low|medium|high",
    "country_specific_issues": ["list of jurisdiction-specific issues"],
    "overall_clearance_risk": "low|medium|high|stop"
  },
  "estimated_duties": {
    "us_total_duty_usd": number_or_null,
    "eu_total_duty_eur": number_or_null,
    "disclaimer": "Estimates only — verify with official tariff schedules before importing"
  },
  "broker_notes": "2-3 sentence summary and key recommendations",
  "confidence": 0.0
}"""

def classify(source: str) -> dict:
    client = anthropic.Anthropic()
    path = Path(source)
    if path.exists() and source.endswith(".pdf"):
        data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
        content = [
            {"type":"document","source":{"type":"base64","media_type":"application/pdf","data":data}},
            {"type":"text","text":"Classify all items in this shipping document for customs."}
        ]
    elif path.exists():
        text = path.read_text(encoding="utf-8",errors="replace")[:40000]
        content = [{"type":"text","text":f"Classify for customs:\n\n{text}"}]
    else:
        content = [{"type":"text","text":f"Classify for customs:\n\n{source[:40000]}"}]

    resp = client.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=3000, system=SYSTEM,
        messages=[{"role":"user","content":content}]
    )
    raw = re.sub(r'^```(?:json)?\s*','',resp.content[0].text.strip(),flags=re.MULTILINE)
    raw = re.sub(r'\s*```$','',raw,flags=re.MULTILINE)
    return json.loads(raw)

RISK_ICON = {"low":"🟢","medium":"🟡","high":"🔴","stop":"🚫","none":"✅"}
SEV_ICON = {"stop":"🚫","high":"🔴","medium":"🟠","low":"🔵"}

def print_report(r: dict):
    ship = r.get("shipment_summary",{})
    comp = r.get("compliance_summary",{})
    docs = r.get("document_completeness",{})
    duties = r.get("estimated_duties",{})
    items = r.get("line_items",[])

    print(f"\n{'═'*60}")
    print(f"  CUSTOMS CLASSIFIER — {r.get('document_type','?').upper().replace('_',' ')}")
    clearance_risk = comp.get("overall_clearance_risk","low")
    print(f"  Clearance risk: {RISK_ICON.get(clearance_risk,'')} {clearance_risk.upper()}")
    print(f"{'═'*60}")

    if ship.get("origin_country") or ship.get("destination_country"):
        print(f"\n  Route: {ship.get('origin_country','?')} → {ship.get('destination_country','?')}")
    if ship.get("total_value"): print(f"  Value: {ship.get('currency','')}{ship['total_value']:,.2f}")
    if ship.get("incoterms"): print(f"  Incoterms: {ship['incoterms']}")

    print(f"\n  CLASSIFIED ITEMS ({len(items)})")
    for item in items:
        hs = item.get("hs_code",{})
        conf_icon = {"high":"✅","medium":"🟡","low":"⚠"}.get(hs.get("confidence","low"),"?")
        print(f"\n  {item.get('description','?')}")
        print(f"  HS: {hs.get('code','?')} — {hs.get('description','?')} {conf_icon}")
        duty = item.get("duty_estimate",{})
        rates = []
        if duty.get("us_mfn_rate_pct") is not None: rates.append(f"US: {duty['us_mfn_rate_pct']}%")
        if duty.get("eu_mfn_rate_pct") is not None: rates.append(f"EU: {duty['eu_mfn_rate_pct']}%")
        if duty.get("uk_mfn_rate_pct") is not None: rates.append(f"UK: {duty['uk_mfn_rate_pct']}%")
        if rates: print(f"  Duty rates: {' | '.join(rates)}")
        if duty.get("notes"): print(f"  Note: {duty['notes'][:80]}")
        flags = item.get("compliance_flags",[])
        for flag in flags:
            print(f"  {SEV_ICON.get(flag.get('severity','low'),'')} {flag.get('flag','')}")

    if duties.get("us_total_duty_usd"):
        print(f"\n  ESTIMATED DUTIES")
        print(f"  US: ${duties.get('us_total_duty_usd',0):,.2f}")
        if duties.get("eu_total_duty_eur"): print(f"  EU: €{duties.get('eu_total_duty_eur',0):,.2f}")
        print(f"  ⚠ {duties.get('disclaimer','')}")

    if comp.get("restricted_goods_detected"): print(f"\n  🚫 RESTRICTED GOODS DETECTED")
    if comp.get("dual_use_potential"): print(f"  ⚠ DUAL-USE POTENTIAL — may require export license")
    if comp.get("country_specific_issues"):
        for issue in comp["country_specific_issues"]: print(f"  ! {issue}")

    missing = docs.get("missing_fields",[])
    if missing:
        print(f"\n  MISSING FIELDS (clearance may be delayed)")
        for m in missing: print(f"  ○ {m}")

    if r.get("broker_notes"): print(f"\n  Broker notes: {r['broker_notes']}")
    print(f"\n  Doc completeness: {docs.get('score',0)}/100 | Confidence: {int(r.get('confidence',0)*100)}%")
    print(f"{'═'*60}\n")

if __name__ == "__main__":
    if len(sys.argv)<2: print("Usage: python -m customs_doc_classifier <document.pdf|.txt> [--json]"); sys.exit(0)
    src = sys.argv[1]
    r = classify(src if src!="-" else sys.stdin.read())
    if "--json" in sys.argv: print(json.dumps(r,indent=2,ensure_ascii=False))
    else: print_report(r)
