"""
Excel Import Utilities for Accounting Module
===========================================
Robust Excel importer for General Ledger and Trial Balance data.
Header-agnostic; handles merged headers, unlabeled columns, and various formats.

Features:
- Automatic header detection
- Flexible column mapping via keyword matching
- Supports multiple sheet formats
- Integrates with existing Account and JournalEntry models
"""
import os
import re
import sys
from decimal import Decimal
from typing import Dict, List, Optional

# Optional Pandas import (required for Excel import)
try:
    import pandas as pd
except Exception:
    pd = None

from django.db import transaction
from django.contrib.auth.models import User


# Column mapping keywords for flexible header detection
KEYWORDS = {
    "date": ["date", "txn date", "posting date", "transaction date"],
    "ref": ["ref", "reference", "doc no", "voucher", "invoice", "cheque no", "doc number"],
    "desc": ["description", "memo", "particulars", "narration", "details", "notes"],
    "acct_code": ["account code", "gl code", "acc code", "code", "account no"],
    "acct_name": ["account", "account name", "gl name", "account title"],
    "debit": ["debit", "dr", "debits", "debit amount"],
    "credit": ["credit", "cr", "credits", "credit amount"],
    "cost_center": ["cost center", "department", "unit", "ward", "dept"],
    "balance": ["balance", "running balance"],
}


def _normalize(s: Optional[str]) -> str:
    """Normalize string for comparison"""
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _detect_header_row(df, must_have=("debit", "credit")) -> int:
    """Scan first 30 rows to find a probable header row that contains must-have columns."""
    limit = min(30, len(df))
    for i in range(limit):
        row = [_normalize(x) for x in df.iloc[i].tolist()]
        if not any(row):
            continue
        joined = " ".join(row)
        if all(m in joined for m in must_have):
            return i
    return 0  # fallback


def _map_columns(cols: List[str]) -> Dict[str, Optional[int]]:
    """Map column names to standard field names using keyword matching"""
    mapping = {k: None for k in KEYWORDS.keys()}
    for idx, col in enumerate(cols):
        c = _normalize(col)
        for key, variants in KEYWORDS.items():
            if any(v in c for v in variants):
                if mapping[key] is None:
                    mapping[key] = idx
    return mapping


def _to_decimal(x) -> Decimal:
    """Convert various numeric formats to Decimal"""
    try:
        if x in ("", None) or (isinstance(x, float) and pd is not None and pd.isna(x)):
            return Decimal("0")
        return Decimal(str(x).replace(",", ""))
    except Exception:
        return Decimal("0")


def _map_account_type(account_type: str) -> str:
    """Map account type from Excel format to Django model format"""
    type_map = {
        "ASSET": "asset",
        "LIAB": "liability",
        "LIABILITY": "liability",
        "EQUITY": "equity",
        "INCOME": "revenue",
        "REVENUE": "revenue",
        "EXP": "expense",
        "EXPENSE": "expense",
    }
    return type_map.get(account_type.upper(), "expense")


def _infer_type_by_name(name: str) -> str:
    """Infer account type from account name using keyword matching"""
    n = (name or "").lower()
    if any(k in n for k in ["cash", "bank", "asset", "inventory", "debtors", "receivable"]):
        return "asset"
    if any(k in n for k in ["payable", "creditors", "loan", "liability"]):
        return "liability"
    if any(k in n for k in ["capital", "retained", "equity"]):
        return "equity"
    if any(k in n for k in ["revenue", "income", "sales", "fees", "consultation", "drug sales"]):
        return "revenue"
    return "expense"


def import_gl_from_excel(
    xlsx_path: str,
    sheet_ledger: str = "LEDGER 2025",
    sheet_tb: str = "TB 2025",
    entered_by: Optional[User] = None,
    auto_post: bool = False,
):
    """
    Import General Ledger and Trial Balance from an Excel workbook into Django models.
    
    This function integrates with the existing Account and JournalEntry models.
    
    :param xlsx_path: Absolute path to Excel workbook
    :param sheet_ledger: Ledger sheet name
    :param sheet_tb: Trial balance / COA sheet name (optional)
    :param entered_by: User who is importing (for audit trail)
    :param auto_post: If True, automatically post journal entries
    :return: Dictionary with import statistics
    """
    if pd is None:
        raise RuntimeError("pandas is required for Excel import. pip install pandas openpyxl")

    from .models_accounting import Account, CostCenter, JournalEntry, JournalEntryLine

    xl = pd.ExcelFile(xlsx_path)

    # --- Bootstrap Chart of Accounts from TB sheet (if present) ---
    accounts_created = 0
    if sheet_tb in xl.sheet_names:
        tb_raw = xl.parse(sheet_tb, header=None)
        tb_hdr_row = _detect_header_row(tb_raw, must_have=("debit", "credit"))
        tb = pd.read_excel(xlsx_path, sheet_name=sheet_tb, header=tb_hdr_row)
        tb.columns = [str(c).strip() for c in tb.columns]
        tb_map = _map_columns(tb.columns)

        code_idx = tb_map.get("acct_code")
        name_idx = tb_map.get("acct_name")

        for _, row in tb.iterrows():
            code = str(row.iloc[code_idx]).strip() if code_idx is not None else ""
            name = str(row.iloc[name_idx]).strip() if name_idx is not None else ""
            if not code and not name:
                continue
            
            account_code = code or name[:20]  # Limit to 20 chars for account_code
            account_name = name or code
            
            acc, created = Account.objects.get_or_create(
                account_code=account_code,
                defaults={
                    "account_name": account_name[:200],  # Limit to 200 chars
                    "account_type": _infer_type_by_name(account_name),
                },
            )
            if name and acc.account_name != account_name:
                acc.account_name = account_name[:200]
                acc.save()
            
            if created:
                accounts_created += 1

    # --- Ledger import ---
    if sheet_ledger not in xl.sheet_names:
        raise ValueError(f"Sheet '{sheet_ledger}' not found in workbook. Available sheets: {xl.sheet_names}")

    raw = xl.parse(sheet_ledger, header=None)
    hdr_row = _detect_header_row(raw, must_have=("debit", "credit"))
    df = pd.read_excel(xlsx_path, sheet_name=sheet_ledger, header=hdr_row)
    df.columns = [str(c).strip() for c in df.columns]
    colmap = _map_columns(df.columns)

    # Build normalized columns
    date_series = df.iloc[:, colmap["date"]] if colmap["date"] is not None else None
    ref_series = df.iloc[:, colmap["ref"]] if colmap["ref"] is not None else ""
    memo_series = df.iloc[:, colmap["desc"]] if colmap["desc"] is not None else ""
    acct_name_series = df.iloc[:, colmap["acct_name"]] if colmap["acct_name"] is not None else ""
    acct_code_series = df.iloc[:, colmap["acct_code"]] if colmap["acct_code"] is not None else ""
    cost_center_series = df.iloc[:, colmap["cost_center"]] if colmap["cost_center"] is not None else ""

    if date_series is not None:
        df["_date"] = pd.to_datetime(date_series, errors="coerce")
    else:
        df["_date"] = pd.NaT

    df["_ref"] = ref_series
    df["_memo"] = memo_series
    df["_acct_name"] = acct_name_series
    df["_acct_code"] = acct_code_series
    df["_debit"] = df.iloc[:, colmap["debit"]].apply(_to_decimal) if colmap["debit"] is not None else Decimal("0")
    df["_credit"] = df.iloc[:, colmap["credit"]].apply(_to_decimal) if colmap["credit"] is not None else Decimal("0")
    df["_cost_center"] = cost_center_series

    # Drop blank lines
    df = df[
        (df["_debit"] != 0) 
        | (df["_credit"] != 0) 
        | (df["_acct_name"].astype(str).str.strip() != "")
    ]

    # Create journal entries grouped by (date, ref)
    created_jrn = 0
    created_lines = 0
    unbalanced_warnings = []
    
    with transaction.atomic():
        grouped = df.groupby([df["_date"].dt.date.fillna(pd.NaT), df["_ref"]])
        
        for (date, ref), g in grouped:
            # Handle NaT date
            entry_date = date if str(date) != "NaT" else pd.Timestamp("today").date()
            
            # Create journal entry description from first memo
            description = str(g["_memo"].iloc[0])[:500] if "_memo" in g and len(g["_memo"].iloc[0]) > 0 else "Imported from Excel GL"
            
            # Check if journal is balanced
            total_debit = g["_debit"].sum()
            total_credit = g["_credit"].sum()
            is_balanced = total_debit == total_credit
            
            journal_entry = JournalEntry.objects.create(
                entry_date=entry_date,
                ref=str(ref)[:64] if ref else None,
                description=description,
                source="Excel GL Import",
                entered_by=entered_by,
                is_posted=auto_post if is_balanced else False,  # Only auto-post if balanced
            )

            for _, r in g.iterrows():
                code = str(r["_acct_code"]).strip()
                name = str(r["_acct_name"]).strip() or code
                if not code and not name:
                    continue

                # Get or create account
                account_code = code or name[:20]
                account_name = name or code
                
                acc, _ = Account.objects.get_or_create(
                    account_code=account_code,
                    defaults={
                        "account_name": account_name[:200],
                        "account_type": _infer_type_by_name(account_name),
                    },
                )
                
                # Get or create cost center
                cc = None
                cc_val = str(r["_cost_center"]).strip()
                if cc_val:
                    cc, _ = CostCenter.objects.get_or_create(
                        code=cc_val[:32],
                        defaults={"name": cc_val[:128]},
                    )

                JournalEntryLine.objects.create(
                    journal_entry=journal_entry,
                    account=acc,
                    cost_center=cc,
                    description=(str(r.get("_memo", "")) or "")[:500],
                    debit_amount=r["_debit"],
                    credit_amount=r["_credit"],
                )
                created_lines += 1

            # Warn if not balanced
            if not is_balanced:
                unbalanced_warnings.append(
                    f"Journal {journal_entry.entry_number} unbalanced "
                    f"(DR {total_debit} != CR {total_credit})."
                )
                if sys.stderr:
                    sys.stderr.write(f"WARNING: {unbalanced_warnings[-1]}\n")

            created_jrn += 1

    result = {
        "journals": created_jrn,
        "lines": created_lines,
        "accounts_created": accounts_created,
        "unbalanced_warnings": unbalanced_warnings,
    }
    
    return result


def get_trial_balance(as_of=None):
    """
    Return a list of trial balance rows: account_code, account_name, account_type, 
    debit_total, credit_total, balance
    
    Uses existing Account and JournalEntryLine models.
    """
    from .models_accounting import Account, JournalEntryLine
    from django.db.models import Sum, Q

    qs = JournalEntryLine.objects.filter(journal_entry__is_posted=True)
    if as_of:
        qs = qs.filter(journal_entry__entry_date__lte=as_of)

    sums = qs.values("account_id").annotate(
        debit_total=Sum("debit_amount"),
        credit_total=Sum("credit_amount")
    )

    out = []
    for row in sums:
        acc = Account.objects.get(id=row["account_id"])
        dr = row["debit_total"] or Decimal("0")
        cr = row["credit_total"] or Decimal("0")
        bal = dr - cr
        out.append({
            "account_code": acc.account_code,
            "account_name": acc.account_name,
            "account_type": acc.account_type,
            "debit": str(dr),
            "credit": str(cr),
            "balance": str(bal),
        })
    
    # Sort by account code
    out.sort(key=lambda x: x["account_code"])
    
    return out


































