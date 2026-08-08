"""Email address validation, outreach limits, and compliance footers.

The module deliberately contains no SMTP code.  It is safe to use from the UI,
dry-run workflows, and alternative email transports.
"""

from __future__ import annotations

import html as html_lib
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.utils import parseaddr
from typing import List, Tuple


_LOCAL_PART_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+$")
_DOMAIN_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")

# Well-known consumer mail providers (not suitable for B2B prospecting).
FREE_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "msn.com", "yahoo.com", "ymail.com", "icloud.com", "me.com", "mac.com",
    "aol.com", "proton.me", "protonmail.com", "zoho.com", "mail.com",
    "gmx.com", "gmx.de", "gmx.net", "web.de", "t-online.de", "orange.fr",
    "wanadoo.fr", "qq.com", "163.com", "126.com", "189.cn", "sina.com",
    "sohu.com", "foxmail.com", "yeah.net", "tom.com", "21cn.com",
    "yandex.com", "yandex.ru", "mail.ru", "inbox.ru", "list.ru", "bk.ru",
    "rambler.ru", "ukr.net", "naver.com", "daum.net", "nate.com",
    "hanmail.net", "163.net", "sina.cn", "sogou.com", "wo.cn", "hey.com",
    "fastmail.com", "hushmail.com", "tutanota.com", "outlook.co.jp",
    "googlemail.de", "rediffmail.com", "aim.com", "verizon.net", "att.net",
    "comcast.net", "sbcglobal.net", "bellsouth.net", "cox.net", "shaw.ca",
    "rogers.com", "sympatico.ca", "optusnet.com.au", "bigpond.com", "tpg.com.au",
    "xtra.co.nz", "libero.it", "virgilio.it", "tin.it", "alice.it",
    "telefonica.net", "terra.com.br", "uol.com.br", "bol.com.br", "ig.com.br",
    "globo.com", "hotmail.co.uk", "hotmail.fr", "hotmail.de", "hotmail.it",
    "hotmail.es", "live.co.uk", "live.fr", "live.de", "live.it", "live.jp",
}

# Disposable / throwaway mailbox providers, blocked outright.
DISPOSABLE_DOMAINS = {
    "mailinator.com", "mailinator.net", "mailinator.org", "mailinator.cc",
    "guerrillamail.com", "guerrillamail.net", "guerrillamail.org",
    "guerrillamail.biz", "guerrillamail.de", "grr.la", "pokemail.net",
    "spam4.me", "10minutemail.com", "10minutemail.net", "10minutemail.org",
    "maildrop.cc", "mailnesia.com", "tempmail.com", "temp-mail.org",
    "temp-mail.io", "tempmail.net", "tempail.com", "throwawaymail.com",
    "yopmail.com", "yopmail.net", "yopmail.fr", "trashmail.com", "trashmail.de",
    "trashmail.me", "getnada.com", "nada.email", "dispostable.com",
    "mailcatch.com", "spambox.us", "spamgourmet.com", "fakemailgenerator.com",
    "emailondeck.com", "tempinbox.com", "mailtemp.net", "emailtemp.com",
    "33mail.com", "mailnull.com", "moakt.com", "mintemail.com", "discard.email",
    "discardmail.com", "discardmail.de", "mailer.fun", "fakemail.net",
    "fakeinbox.com", "mailinator2.com", "mytemp.email", "spam.la",
    "tempr.email", "dropmail.me", "emlpro.com", "emltmp.com", "mohmal.com",
    "mailforspam.com", "spamspot.com", "spamthis.co.uk", "sogetthis.com",
}

# Marketing-spam wording with severity weight. Used by check_spam_content().
SPAM_WORD_PATTERNS = [
    ("free", 3),
    ("money", 2),
    ("guaranteed", 3),
    ("guarantee", 3),
    ("act now", 2),
    ("buy now", 2),
    ("limited offer", 2),
    ("100%", 2),
    ("click here", 2),
    ("risk-free", 2),
    ("no risk", 2),
    ("winner", 3),
    ("cash", 2),
    ("bonus", 1),
    ("urgent", 1),
    ("double your", 2),
    ("instant", 1),
    ("special promotion", 2),
    ("cheap", 1),
    ("congratulations", 2),
]


def _compile_spam_patterns():
    """Precompile spam patterns once (longest first for overlap handling)."""
    patterns = [
        (re.compile(r"(?<![a-z0-9])" + re.escape(pattern) + r"(?![a-z0-9])"), weight, pattern)
        for pattern, weight in SPAM_WORD_PATTERNS
    ]
    patterns.sort(key=lambda item: -len(item[2]))
    return patterns


_SPAM_PATTERNS = _compile_spam_patterns()


def _match_disposable_domain(domain):
    """Return the matching disposable domain (subdomains included) or None."""
    domain = str(domain or "").strip().rstrip(".").casefold()
    if not domain:
        return None
    if domain in DISPOSABLE_DOMAINS:
        return domain
    for known in DISPOSABLE_DOMAINS:
        if domain.endswith("." + known):
            return known
    return None


def is_business_email(email: str) -> bool:
    """Heuristic: True when the mailbox is not a known free or disposable provider."""
    address = normalize_email(email)
    if not address:
        return False
    domain = address.rsplit("@", 1)[1].casefold()
    if domain in FREE_EMAIL_DOMAINS:
        return False
    return _match_disposable_domain(domain) is None



def normalize_email(email: str) -> str:
    """Return a canonical mailbox address, or an empty string for bad input."""
    if email is None:
        return ""
    raw = str(email).strip()
    if not raw or "\r" in raw or "\n" in raw:
        return ""
    _display_name, address = parseaddr(raw)
    address = address.strip()
    if address.count("@") != 1:
        return ""
    local, domain = address.rsplit("@", 1)
    try:
        ascii_domain = domain.rstrip(".").encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError):
        return ""
    return f"{local}@{ascii_domain}"


def validate_email(email: str) -> Tuple[bool, str]:
    """Validate an external B2B mailbox without making a network request."""
    address = normalize_email(email)
    if not address:
        return False, "Invalid email address"
    if len(address) > 254:
        return False, "Email address exceeds 254 characters"

    local, domain = address.rsplit("@", 1)
    if not local or len(local) > 64 or not _LOCAL_PART_RE.fullmatch(local):
        return False, "Invalid email local part"
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False, "Invalid email local part"
    if len(domain) > 253 or "." not in domain:
        return False, "Invalid email domain"
    labels = domain.split(".")
    if any(not _DOMAIN_LABEL_RE.fullmatch(label) for label in labels):
        return False, "Invalid email domain"
    return True, "OK"


@dataclass
class EmailComplianceConfig:
    daily_limit: int = 50
    hourly_limit: int = 10
    min_interval_seconds: float = 10
    bounce_threshold: int = 5
    unsubscribe_required: bool = True
    gdpr_footer_required: bool = True
    sender_name: str = "Sales Team"
    company_name: str = ""
    privacy_contact: str = ""
    allow_free_email: bool = False
    spam_threshold: float = 50.0


@dataclass
class SendRecord:
    email: str
    company: str
    subject: str
    status: str
    timestamp: float = field(default_factory=time.time)


class EmailCompliance:
    """In-process outreach guard used before every attempted delivery."""

    def __init__(self, config: EmailComplianceConfig = None, store=None):
        self.config = config or EmailComplianceConfig()
        self._store = store
        try:
            if self._store is None:
                from memory.store import memory_store
                self._store = memory_store
            self._unsubscribed = set(self._store.get_unsubscribed_emails())
        except Exception:
            self._unsubscribed = set()
        self._sent_today: List[SendRecord] = []
        self._sent_this_hour: List[SendRecord] = []
        self._bounces: List[SendRecord] = []
        self._last_send_time: float = 0.0
        self._last_reset_date: str = ""
        self._paused: bool = False
        self._pause_reason: str = ""
        try:
            if self._store is not None:
                self._unsubscribed = set(self._store.get_unsubscribed_emails())
            else:
                self._unsubscribed = set()
        except Exception:
            self._unsubscribed = set()
        self._blocked_domains = set()
        self._lock = threading.RLock()

    def _reset_daily(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if self._last_reset_date != today:
            self._last_reset_date = today
            self._sent_today.clear()
            self._sent_this_hour.clear()
            self._paused = False
            self._pause_reason = ""

    def _reset_hourly(self) -> None:
        cutoff = (datetime.now() - timedelta(hours=1)).timestamp()
        self._sent_this_hour = [record for record in self._sent_this_hour if record.timestamp > cutoff]

    def can_send(self, email: str = "", company: str = "") -> Tuple[bool, str]:
        """Return whether an address may be contacted at this moment."""
        del company  # Kept for backward-compatible call sites and future policy hooks.
        with self._lock:
            self._reset_daily()
            self._reset_hourly()

            valid, reason = validate_email(email)
            if not valid:
                return False, reason
            address = normalize_email(email).casefold()
            domain = address.rsplit("@", 1)[1]

            if self._paused:
                return False, f"Paused: {self._pause_reason}"
            if address in self._unsubscribed:
                return False, "Email has unsubscribed"
            if domain in self._blocked_domains:
                return False, f"Domain {domain} is blocked after repeated bounces"
            disposable = _match_disposable_domain(domain)
            if disposable:
                return False, f"Disposable email domain {disposable} is not allowed for B2B outreach"
            if not self.config.allow_free_email and domain in FREE_EMAIL_DOMAINS:
                return False, f"Email domain {domain} is a free email provider; use a business email"
            if len(self._sent_today) >= max(0, int(self.config.daily_limit)):
                return False, f"Daily limit reached ({self.config.daily_limit})"
            if len(self._sent_this_hour) >= max(0, int(self.config.hourly_limit)):
                return False, f"Hourly limit reached ({self.config.hourly_limit})"

            elapsed = time.time() - self._last_send_time
            min_wait = max(0.0, float(self.config.min_interval_seconds))
            if self._last_send_time > 0 and elapsed < min_wait:
                return False, f"Rate limit: wait {max(1, int(min_wait - elapsed + 0.999))}s"

            if len(self._bounces) >= max(1, int(self.config.bounce_threshold)):
                self._paused = True
                self._pause_reason = (
                    f"Bounce threshold reached ({len(self._bounces)}/{self.config.bounce_threshold})"
                )
                return False, self._pause_reason

            return True, "OK"

    def check_spam_content(self, subject: str = "", body: str = "") -> Tuple[List[str], float]:
        """Detect marketing-spam wording.

        Returns (matched patterns, risk score 0-100). A score at or above
        config.spam_threshold indicates the content should not be delivered.
        """
        text = f"{subject or ''} {body or ''}".casefold()
        hits: List[str] = []
        total = 0
        covered = [False] * len(text)
        # Longest-first: "risk-free" covers "free", avoiding double counting
        for regex, weight, pattern in _SPAM_PATTERNS:
            search_start = 0
            while search_start < len(text):
                match = regex.search(text, pos=search_start)
                if not match:
                    break
                abs_start = match.start()
                abs_end = match.end()
                if any(covered[abs_start:abs_end]):
                    search_start = abs_end
                    continue
                for index in range(abs_start, abs_end):
                    covered[index] = True
                hits.append(pattern)
                total += weight
                search_start = abs_end
        return hits, min(100.0, float(total * 10))

    def record_send(self, email: str, company: str, subject: str) -> None:
        with self._lock:
            self._reset_daily()
            record = SendRecord(
                email=normalize_email(email), company=company, subject=subject, status="sent"
            )
            self._sent_today.append(record)
            self._sent_this_hour.append(record)
            self._last_send_time = record.timestamp

    def record_bounce(self, email: str, company: str, subject: str) -> None:
        with self._lock:
            self._reset_daily()
            address = normalize_email(email)
            if not address:
                return
            record = SendRecord(email=address, company=company, subject=subject, status="bounced")
            self._bounces.append(record)
            domain = address.rsplit("@", 1)[1].casefold()
            recent_domain_bounces = sum(
                1 for bounce in self._bounces[-10:]
                if normalize_email(bounce.email).casefold().endswith("@" + domain)
            )
            if recent_domain_bounces >= 3:
                self._blocked_domains.add(domain)

    def record_open(self, email: str, company: str, subject: str) -> None:
        with self._lock:
            self._sent_today.append(
                SendRecord(
                    email=normalize_email(email), company=company, subject=subject, status="opened"
                )
            )

    def add_unsubscribe(self, email: str) -> None:
        """Suppress exactly one mailbox; never suppress its whole provider domain."""
        address = normalize_email(email)
        if address:
            with self._lock:
                self._unsubscribed.add(address.casefold())
                try:
                    if self._store is not None:
                        self._store.add_unsubscribed(address, reason="user requested")
                except Exception:
                    pass

    def block_domain(self, domain: str) -> None:
        normalized = str(domain or "").strip().rstrip(".").casefold()
        if normalized:
            with self._lock:
                self._blocked_domains.add(normalized)

    def get_unsubscribe_footer(self, html: bool = True) -> str:
        text = (
            "You received this message because your business profile may be relevant to our "
            "services. To opt out of future outreach, reply with 'unsubscribe'."
        )
        if html:
            return (
                '<div data-compliance="unsubscribe"><hr><small>'
                + html_lib.escape(text)
                + "</small></div>"
            )
        return "\n\n---\n[Unsubscribe] " + text

    def get_gdpr_footer(
        self, sender_name: str = "", company_name: str = "", html: bool = True
    ) -> str:
        name = sender_name or self.config.sender_name or "Sales Team"
        company = company_name or self.config.company_name or "our company"
        contact = self.config.privacy_contact or "reply to this email"
        text = (
            f"Privacy notice: {name} at {company} uses business contact data for relevant B2B "
            f"outreach. To access, correct, delete, or object to its use, {contact}."
        )
        if html:
            return (
                '<div data-compliance="gdpr"><small>'
                + html_lib.escape(text)
                + "</small></div>"
            )
        return "\n[Privacy] " + text

    def append_required_footers(
        self,
        body: str,
        html: bool = False,
        sender_name: str = "",
        company_name: str = "",
    ) -> str:
        """Append configured footers once, preserving plain-text and HTML formats."""
        result = str(body or "")
        if self.config.unsubscribe_required:
            marker = 'data-compliance="unsubscribe"' if html else "[Unsubscribe]"
            if marker not in result:
                result += self.get_unsubscribe_footer(html=html)
        if self.config.gdpr_footer_required:
            marker = 'data-compliance="gdpr"' if html else "[Privacy]"
            if marker not in result:
                result += self.get_gdpr_footer(
                    sender_name=sender_name, company_name=company_name, html=html
                )
        return result

    def get_stats(self) -> dict:
        with self._lock:
            self._reset_daily()
            self._reset_hourly()
            return {
                "sent_today": len(self._sent_today),
                "sent_this_hour": len(self._sent_this_hour),
                "total_bounces": len(self._bounces),
                "unsubscribed": len(self._unsubscribed),
                "blocked_domains": len(self._blocked_domains),
                "paused": self._paused,
                "pause_reason": self._pause_reason,
                "daily_remaining": max(0, int(self.config.daily_limit) - len(self._sent_today)),
                "hourly_remaining": max(
                    0, int(self.config.hourly_limit) - len(self._sent_this_hour)
                ),
            }


email_compliance = EmailCompliance()
