"""Suspension Engineering – Pressure Balance App (Cubic 6‑Point)

Locked web version (PayPal-gated).

Copyright / TM
- Mountain Race Shop™ & Suspension Engineering™
- © Mountain Race Shop™ 2025–2026. All rights reserved.

Notes
- This is a decision-support tool only.
- All outputs are provided "as is".
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import streamlit as st
import streamlit.components.v1 as components


# Streamlit requires page config before any other Streamlit calls.
st.set_page_config(
    page_title="Suspension Engineering – Pressure Balance & Adjuster Authority",
    layout="wide",
)


def _get_cfg(key: str, default: str = "") -> str:
    """Read config from environment first, then Streamlit secrets if available."""
    v = os.getenv(key, "")
    if v:
        return v
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def _get_query_params() -> dict:
    """Compatibility wrapper across Streamlit versions."""
    try:
        return dict(st.query_params)  # new API
    except Exception:
        return st.experimental_get_query_params()  # old API


def _data_dir() -> str:
    d = os.getenv("DATA_DIR", ".data")
    os.makedirs(d, exist_ok=True)
    return d


def _append_jsonl(path: str, payload: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def paypal_subscribe_button_html(client_id: str, plan_id: str) -> str:
    """PayPal JS SDK subscription button.

    On approve, redirects back with ?subscription_id=<id>.
    """
    return f"""
<div id=\"paypal-button-container\"></div>
<script src=\"https://www.paypal.com/sdk/js?client-id={client_id}&vault=true&intent=subscription\"></script>
<script>
  paypal.Buttons({{
    style: {{ shape: 'rect', color: 'gold', layout: 'vertical', label: 'subscribe' }},
    createSubscription: function(data, actions) {{
      return actions.subscription.create({{ 'plan_id': '{plan_id}' }});
    }},
    onApprove: function(data, actions) {{
      const url = new URL(window.location.href);
      url.searchParams.set('subscription_id', data.subscriptionID);
      window.location.href = url.toString();
    }}
  }}).render('#paypal-button-container');
</script>
"""


def ensure_unlocked() -> None:
    """Gate the app behind an email + PayPal subscription ID."""

    # Emergency bypass for admin/testing.
    if os.getenv("PAYMENT_DISABLED", "0") == "1":
        st.session_state["unlocked"] = True
        return

    if st.session_state.get("unlocked"):
        return

    # Pull subscription_id from query params (return from PayPal).
    qp = _get_query_params()
    sub_id_from_qp = ""
    if "subscription_id" in qp:
        v = qp["subscription_id"]
        sub_id_from_qp = v[0] if isinstance(v, list) else str(v)

    # Init widget state once.
    if "email" not in st.session_state:
        st.session_state["email"] = ""
    if "sub_id" not in st.session_state:
        st.session_state["sub_id"] = sub_id_from_qp

    st.title("Unlock access")
    st.write("Subscribe to unlock the app.")

    # IMPORTANT: do NOT render PayPal iframe until after email is typed.
    # (On some browsers, the PayPal iframe can steal focus/keyboard input.)
    email = st.text_input(
        "Email (for receipt + access records)",
        key="email",
        placeholder="your@email.com",
    )

    client_id = _get_cfg("PAYPAL_CLIENT_ID")
    plan_id = _get_cfg("PAYPAL_PLAN_ID")

    # Step 1: enter email
    if not email.strip():
        st.info("Enter your email first. Then the PayPal Subscribe button will appear.")
    else:
        # Step 2: show PayPal subscribe only after email is present
        if client_id and plan_id:
            with st.expander("PayPal Subscribe", expanded=True):
                components.html(
                    paypal_subscribe_button_html(client_id, plan_id),
                    height=220,
                )
        else:
            st.warning(
                "PayPal is not configured yet. Set PAYPAL_CLIENT_ID and PAYPAL_PLAN_ID in your host (Render) environment variables."
            )

    st.markdown("---")
    st.write("Already subscribed? Paste your PayPal subscription ID:")

    # Keep this as a normal Streamlit widget (no custom html)
    manual_sub_id = st.text_input(
        "Subscription ID",
        key="sub_id",
        placeholder="I-XXXXXXXXXXXX",
    )

    sub_id_final = (manual_sub_id or "").strip()

    if st.button("Unlock"):
        if not email.strip():
            st.error("Please enter your email.")
            st.stop()

        if not sub_id_final:
            st.error("Please enter a subscription ID.")
            st.stop()

        st.session_state["unlocked"] = True

        _append_jsonl(
            os.path.join(_data_dir(), "unlock_log.jsonl"),
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "email": email.strip(),
                "subscription_id": sub_id_final,
                "app": "pressure_balance_cubic6",
            },
        )

        st.success("Unlocked. Loading app…")
        st.rerun()

    st.caption("© Mountain Race Shop™ 2025–2026. All rights reserved.")
    st.stop()


def fit_curve(x: np.ndarray, y: np.ndarray, model: str):
    deg = {"Linear": 1, "Quadratic": 2, "Cubic": 3}[model]
    uniq = len(np.unique(x))
    if uniq <= deg:
        deg = max(0, uniq - 1)
    coeffs = np.polyfit(x, y, deg)
    return np.poly1d(coeffs), deg


# --- Gate ---
ensure_unlocked()

# --- App ---
st.title("Suspension Engineering – Pressure Balance, Adjuster Authority & Damping Targets")
st.caption("© Mountain Race Shop™ 2025–2026 | Support: fenianparktrading@gmail.com")

model = st.sidebar.selectbox("Curve fit model", ["Linear", "Quadratic", "Cubic"], index=2)

st.sidebar.header("Geometry & Pressure Inputs")
p1 = st.sidebar.number_input("Baseline pressure P1 (bar)", value=10.0)
rod_d = st.sidebar.number_input("Rod diameter (mm)", value=10.0)
piston_d = st.sidebar.number_input("Body / piston diameter (mm)", value=46.0)
v_ref = st.sidebar.number_input("Velocity reference (m/s)", value=1.0)

# --- Compression ---
st.header("Compression – 6 Point Definition")
cols = st.columns(6)
v, f_adj, f_full = [], [], []
for i in range(6):
    with cols[i]:
        v.append(st.number_input(f"V{i+1} (m/s)", value=0.5 * (i + 1), key=f"v{i}"))
        f_adj.append(st.number_input(f"Adj-only F{i+1} (N)", value=300 * (i + 1), key=f"fa{i}"))
        f_full.append(st.number_input(f"Full F{i+1} (N)", value=1200 * (i + 1), key=f"ff{i}"))

v = np.array(v, dtype=float)
f_adj = np.array(f_adj, dtype=float)
f_full = np.array(f_full, dtype=float)

curve_adj, used_deg_adj = fit_curve(v, f_adj, model)
curve_full, used_deg_full = fit_curve(v, f_full, model)

v_dense = np.linspace(float(np.min(v)), float(np.max(v)), 200)
adj_dense = curve_adj(v_dense)
full_dense = curve_full(v_dense)

st.subheader("Compression results")
st.write(f"Adj-only model used: Degree {used_deg_adj}")
st.write(f"Full-force model used: Degree {used_deg_full}")

st.line_chart(
    {
        "Velocity (m/s)": v_dense,
        "Adj-only force (N)": adj_dense,
        "Full force (N)": full_dense,
    }
)

peak_adj_ratio = float(np.max(f_adj / np.maximum(f_full, 1e-9)) * 100.0)

# --- Rebound ---
st.header("Rebound – 6 Point Definition")
cols_r = st.columns(6)
rv, rf_adj, rf_full = [], [], []
for i in range(6):
    with cols_r[i]:
        rv.append(st.number_input(f"R V{i+1} (m/s)", value=0.5 * (i + 1), key=f"rv{i}"))
        rf_adj.append(st.number_input(f"Rebound Adj-only F{i+1} (N)", value=500 * (i + 1), key=f"rfa{i}"))
        rf_full.append(st.number_input(f"Rebound Full F{i+1} (N)", value=1500 * (i + 1), key=f"rff{i}"))

rv = np.array(rv, dtype=float)
rf_adj = np.array(rf_adj, dtype=float)
rf_full = np.array(rf_full, dtype=float)

r_curve_adj, used_r_deg_adj = fit_curve(rv, rf_adj, model)
r_curve_full, used_r_deg_full = fit_curve(rv, rf_full, model)

rv_dense = np.linspace(float(np.min(rv)), float(np.max(rv)), 200)
r_adj_dense = r_curve_adj(rv_dense)
r_full_dense = r_curve_full(rv_dense)

st.subheader("Rebound results")
st.write(f"Adj-only model used: Degree {used_r_deg_adj}")
st.write(f"Full-force model used: Degree {used_r_deg_full}")

st.line_chart(
    {
        "Velocity (m/s)": rv_dense,
        "Rebound Adj-only force (N)": r_adj_dense,
        "Rebound Full force (N)": r_full_dense,
    }
)

st.metric("Peak Adjuster %", f"{peak_adj_ratio:.1f}%")
st.info("Target band typically 15–20%. Above this = adjuster doing too much of the job.")
if peak_adj_ratio < 15:
    st.warning("Adjuster below 15% authority will have little to no real effect.")

st.caption("© Mountain Race Shop™ 2025–2026 | Support: fenianparktrading@gmail.com")
