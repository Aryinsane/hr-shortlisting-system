"""
app/security/pii_masking.py
============================
PII (Personally Identifiable Information) masking utilities.
Applied before storing or logging candidate data.

Masks:
- Email addresses
- Phone numbers
- Social Security Numbers (SSN)
- Aadhaar numbers (India)
- Names (via replacement markers)
"""

import re
from typing import Dict, Tuple
from app.utils.constants import (
    EMAIL_PATTERN,
    PHONE_PATTERN,
    SSN_PATTERN,
    AADHAAR_PATTERN,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PIIMasker:
    """
    Masks PII from text strings and candidate data dictionaries.
    Used before logging, storing, or displaying candidate information.
    """

    def __init__(self):
        self._email_re = re.compile(EMAIL_PATTERN, re.IGNORECASE)
        self._phone_re = re.compile(PHONE_PATTERN)
        self._ssn_re = re.compile(SSN_PATTERN)
        self._aadhaar_re = re.compile(AADHAAR_PATTERN)

    def mask_email(self, email: str) -> str:
        """
        Mask an email address: john.doe@example.com → j***@e***.com

        Args:
            email: Raw email string.

        Returns:
            Masked email string.
        """
        if not email or "@" not in email:
            return email

        parts = email.split("@")
        local = parts[0]
        domain_parts = parts[1].split(".")

        masked_local = local[0] + "***" if len(local) > 1 else "***"
        masked_domain = domain_parts[0][0] + "***" if len(domain_parts[0]) > 1 else "***"
        tld = ".".join(domain_parts[1:]) if len(domain_parts) > 1 else "com"

        return f"{masked_local}@{masked_domain}.{tld}"

    def mask_phone(self, phone: str) -> str:
        """
        Mask a phone number: +91-9876543210 → +91-XXXXXX3210

        Args:
            phone: Raw phone string.

        Returns:
            Masked phone string.
        """
        if not phone:
            return phone
        # Keep first 3 and last 4 digits visible
        digits_only = re.sub(r"\D", "", phone)
        if len(digits_only) >= 7:
            masked_digits = digits_only[:3] + "X" * (len(digits_only) - 7) + digits_only[-4:]
            return masked_digits
        return "XXXXX"

    def mask_text(self, text: str) -> str:
        """
        Mask all PII occurrences in a block of text.

        Args:
            text: Raw text that may contain PII.

        Returns:
            Text with PII replaced by masked placeholders.
        """
        if not text:
            return text

        # Mask emails
        text = self._email_re.sub("[EMAIL_MASKED]", text)
        # Mask phone numbers
        text = self._phone_re.sub("[PHONE_MASKED]", text)
        # Mask SSNs
        text = self._ssn_re.sub("[SSN_MASKED]", text)
        # Mask Aadhaar
        text = self._aadhaar_re.sub("[AADHAAR_MASKED]", text)

        return text

    def mask_name(self, name: str) -> str:
        """
        Partially mask a name: John Doe → J*** D***

        Args:
            name: Full name string.

        Returns:
            Masked name.
        """
        if not name:
            return name

        parts = name.strip().split()
        masked_parts = []
        for part in parts:
            if len(part) > 1:
                masked_parts.append(part[0] + "***")
            else:
                masked_parts.append(part)

        return " ".join(masked_parts)

    def mask_candidate_data(self, data: Dict) -> Dict:
        """
        Apply PII masking to a candidate data dictionary.
        Modifies name, email, phone in-place (returns new dict).

        Args:
            data: Raw candidate data dictionary.

        Returns:
            New dictionary with PII fields masked.
        """
        masked = data.copy()

        if "name" in masked:
            masked["name"] = self.mask_name(str(masked.get("name", "")))

        if "email" in masked:
            masked["email"] = self.mask_email(str(masked.get("email", "")))

        if "phone" in masked:
            masked["phone"] = self.mask_phone(str(masked.get("phone", "")))

        # Do NOT mask the raw_text — it should not be stored at all
        if "raw_text" in masked:
            masked["raw_text"] = "[RAW TEXT NOT STORED — PII COMPLIANCE]"

        return masked


# --- Module-level singleton ---
_masker = PIIMasker()


def mask_pii(text: str) -> str:
    """Convenience function to mask PII in text."""
    return _masker.mask_text(text)


def mask_email(email: str) -> str:
    """Convenience function to mask an email address."""
    return _masker.mask_email(email)


def mask_phone(phone: str) -> str:
    """Convenience function to mask a phone number."""
    return _masker.mask_phone(phone)


def mask_name(name: str) -> str:
    """Convenience function to mask a name."""
    return _masker.mask_name(name)


def mask_candidate(data: Dict) -> Dict:
    """Convenience function to mask a candidate data dict."""
    return _masker.mask_candidate_data(data)
