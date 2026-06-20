"""Outbound HTTP client to consult the Dolibarr REST API per instance.

Used by the draw panel to filter out tickets whose source invoice is still
unpaid. Each `DolibarrInstance` carries its own `outbound_api_url` and
`outbound_api_key` so this client works across N parallel Dolibarr installs.
"""
import logging

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 600  # 10 minutes
_HTTP_TIMEOUT_SECONDS = 5

_session = requests.Session()


def _cache_key(instance_id, facture_id):
    return f"dolinvoice_{instance_id}_{facture_id}"


def is_invoice_paid(ticket, force_refresh=False):
    """Return True if the ticket's source invoice is paid in Dolibarr,
    False if explicitly unpaid, or None when the answer is unknown
    (no transaction, no facture_id, instance has no outbound creds,
    or the API call fails). Callers MUST treat None as "unverified" and
    decide whether to include or exclude such tickets.

    Set ``force_refresh=True`` to bypass the 10-minute cache and re-query
    Dolibarr — used by the "refrescar verificación de pagos" button.
    """
    tx = getattr(ticket, 'dolibarr_transaction', None)
    if tx is None or tx.facture_id is None or tx.instance_id is None:
        return None

    instance = tx.instance
    if not instance.outbound_api_url or not instance.outbound_api_key:
        return None

    key = _cache_key(instance.id, tx.facture_id)
    if not force_refresh:
        cached = cache.get(key)
        if cached is not None:
            return cached

    url = f"{instance.outbound_api_url.rstrip('/')}/invoices/{tx.facture_id}"
    headers = {
        'DOLAPIKEY': instance.outbound_api_key,
        'Accept': 'application/json',
    }
    try:
        response = _session.get(url, headers=headers, timeout=_HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.warning(
            "Dolibarr API unreachable for instance=%s facture_id=%s: %s",
            instance.slug, tx.facture_id, exc,
        )
        return None

    if not response.ok:
        logger.warning(
            "Dolibarr API returned %s for instance=%s facture_id=%s",
            response.status_code, instance.slug, tx.facture_id,
        )
        return None

    try:
        payload = response.json()
    except ValueError:
        logger.warning(
            "Dolibarr API returned non-JSON for instance=%s facture_id=%s",
            instance.slug, tx.facture_id,
        )
        return None

    # Dolibarr serializes `paye` as the string "1" or "0".
    paid = str(payload.get('paye', '')) == '1'
    cache.set(key, paid, _CACHE_TTL_SECONDS)
    return paid
