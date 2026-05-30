# customs-doc-classifier

> **Shipping document → HS tariff codes, duty estimates, compliance flags.** Classifies every line item, estimates duties for US/EU/UK, flags restricted goods, checks document completeness.

[![PyPI](https://img.shields.io/pypi/v/customs-doc-classifier?style=flat)](https://pypi.org/project/customs-doc-classifier/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Quickstart

```bash
pip install customs-doc-classifier
python -m customs_doc_classifier commercial_invoice.pdf
python -m customs_doc_classifier packing_list.txt --json
```

## What it does

- **HS code classification** for every line item with confidence score and reasoning
- **Duty rate estimates** — US MFN, EU MFN, UK MFN rates per item
- **Compliance flags** — restricted goods, dual-use items, sanctions risk
- **Document completeness** — missing fields that would delay clearance
- **Total duty estimates** for US and EU destinations

⚠️ Estimates only. Always verify with official tariff schedules and a licensed customs broker.

## License
MIT © [Alper Nabil Gabra Zakher](https://github.com/AlperNab)
