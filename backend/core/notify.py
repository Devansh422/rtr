"""Outbound notifications: transactional email and share links.

Infrastructure, so it lives in core rather than being a module -- the Petitions,
Events, Volunteers and Academy modules all need to send something, and §4's rule
is that shared behaviour moves down into core rather than sideways.

Free-tier shape, per §5:

* Email goes through Brevo's 300/day free tier. Unconfigured, every send is a
  logged no-op that returns success, so local development and the test suite
  never touch the network and a missing API key degrades one feature instead of
  failing a request.
* WhatsApp is `wa.me` deep links only. There is no free way to SEND a WhatsApp
  message; there is a completely free way to hand someone a pre-filled one, and
  that is what the share buttons already do.
* Push (FCM) is genuinely free but needs a service account and a registered
  frontend; the hook is here and marked, not half-built.

Nothing here raises. A notification that fails must never fail the action that
triggered it: a volunteer whose certificate email bounced still earned the
certificate.
"""

from typing import Iterable, Optional
from urllib.parse import quote
import logging

from backend.core import config

logger = logging.getLogger(__name__)

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"

# Re-exported so callers say notify.SITE_URL rather than reaching into config for
# something that is, from their point of view, a property of outbound messages.
SITE_URL = config.SITE_URL


def email_enabled() -> bool:
    return config.email_enabled()


def absolute(path: str) -> str:
    return path if path.startswith("http") else f"{SITE_URL}/{path.lstrip('/')}"


async def send_email(
    *,
    to: str,
    subject: str,
    html: str,
    text: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> bool:
    """Send one transactional email. Returns whether it actually went out.

    Callers should treat False as "the user did not get an email", not as an
    error: every flow that sends one also shows the same information on screen,
    because 300 sends a day runs out and the platform has to keep working when
    it does.
    """
    if not email_enabled():
        logger.info("Email suppressed (BREVO_API_KEY unset): to=%s subject=%s", to, subject)
        return False

    try:
        import httpx
    except ImportError:  # pragma: no cover
        return False

    payload = {
        "sender": {"email": config.BREVO_SENDER_EMAIL, "name": config.BREVO_SENDER_NAME},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html,
    }
    if text:
        payload["textContent"] = text
    if reply_to:
        payload["replyTo"] = {"email": reply_to}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                BREVO_ENDPOINT,
                json=payload,
                headers={"api-key": config.BREVO_API_KEY, "content-type": "application/json"},
            )
        if response.status_code >= 400:
            # 402 is Brevo's "daily quota exhausted", which is an expected
            # operating condition on a free tier rather than a bug.
            logger.warning("Brevo send failed (%s): %s", response.status_code, response.text[:300])
            return False
        return True
    except Exception as e:
        logger.warning("Brevo send errored: %s", e)
        return False


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------
_LAYOUT = """\
<div style="font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:560px;
            margin:0 auto;padding:24px;color:#101828;line-height:1.6">
  <p style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#667085;margin:0 0 16px">
    Right to Recall Movement
  </p>
  <h1 style="font-size:22px;margin:0 0 16px;line-height:1.3">{heading}</h1>
  {body}
  <hr style="border:none;border-top:1px solid #eaecf0;margin:28px 0 16px">
  <p style="font-size:12px;color:#667085;margin:0">
    You are receiving this because you joined the Right to Recall Movement at
    <a href="{site}" style="color:#175cd3">{site}</a>. This is a non-partisan civic
    platform. <a href="{site}/privacy" style="color:#175cd3">Privacy policy</a> &middot;
    <a href="{site}/dashboard" style="color:#175cd3">Manage your data</a>
  </p>
</div>
"""


def render(heading: str, body_html: str) -> str:
    """Wrap body HTML in the shared shell.

    Inline styles because email clients discard <style> blocks, and no images
    because a civic notification should be readable with images blocked.
    """
    return _LAYOUT.format(heading=heading, body=body_html, site=SITE_URL)


def button(label: str, url: str) -> str:
    return (
        f'<p style="margin:24px 0"><a href="{absolute(url)}" '
        'style="background:#175cd3;color:#fff;text-decoration:none;padding:12px 20px;'
        'border-radius:8px;display:inline-block;font-weight:600">'
        f"{label}</a></p>"
    )


def paragraph(text: str) -> str:
    return f'<p style="margin:0 0 14px">{text}</p>'


# --------------------------------------------------------------------------
# Share links -- free, no API, no quota
# --------------------------------------------------------------------------
def share_links(*, url: str, text: str) -> dict:
    """Pre-filled share URLs for the platforms that support them via plain links.

    Already how the existing supporter certificate share works; centralised here
    so petitions, reports and events all produce identical links.
    """
    absolute_url = absolute(url)
    message = f"{text} {absolute_url}"
    return {
        "whatsapp": f"https://wa.me/?text={quote(message)}",
        "telegram": f"https://t.me/share/url?url={quote(absolute_url)}&text={quote(text)}",
        "twitter": f"https://twitter.com/intent/tweet?text={quote(message)}",
        "facebook": f"https://www.facebook.com/sharer/sharer.php?u={quote(absolute_url)}",
        "email": f"mailto:?subject={quote(text)}&body={quote(message)}",
        "copy": absolute_url,
    }


async def send_bulk(
    recipients: Iterable[str], *, subject: str, html: str, text: Optional[str] = None
) -> dict:
    """Sequential fan-out with a per-recipient result count.

    Sequential on purpose: the free tier is 300 messages a day and a serverless
    function has a 30-second ceiling, so anything that would need real
    concurrency here is a job that belongs on the Render worker (§5), not in a
    request. `skipped` counts addresses not attempted because the quota or the
    configuration ran out.
    """
    sent = failed = 0
    for address in recipients:
        if await send_email(to=address, subject=subject, html=html, text=text):
            sent += 1
        else:
            failed += 1
    return {"sent": sent, "failed": failed}
