"""ACWI owner-fence read-only classifier. No network or order transport."""
from __future__ import annotations

class EvidenceStop(ValueError):
    pass

import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
import fund100_v6_s1_public_genesis_witness_v1_0 as witness

SCHEMA='FUND100_V6_S1_FENCE_GET_REVIEW_V1'
GET_ONLY=True
LIVE_ORDERS_ALLOWED=False
