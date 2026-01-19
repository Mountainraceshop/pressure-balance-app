"""Suspension Engineering – Pressure Balance App (Cubic 6‑Point)

Locked web version (PayPal-gated).

Mountain Race Shop™ & Suspension Engineering™
© Mountain Race Shop™ 2025–2026. All rights reserved.

Decision-support tool only. Outputs provided “as is”.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import streamlit as st
import streamlit.components.v1 as components

# IMPORTANT: must be first Streamlit call
st.set_page_config(
    page_title="Suspension Engineering – Pressure Balance & Adjuster Authority",
    layout="wide",
)


# -----------------------------
# Helpers
# -----------------------------

def _get_cfg(key: str, default: str = "") -> str:
    """Env first, then st.secrets (safe on hosts without secrets)."""
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
        return dict(st.query_params)
    except Exception:
        return st.experimental_get_query_params()


def _data_dir() -> str:
    d = os.getenv("DATA_DIR", ".data")
    os.makedirs(d, exist_ok=True)
    return d


def _append_jsonl(path: str, payload: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def paypal_subscribe_button_html(client_id: str, plan_id: str) -> str:
    """PayPal JS SDK subscription button.

    On approval, we redirect back to this page with ?subscription_id=....
    """
    # NOTE: keep it simple and avoid any CSS that could overlay the whole page.
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


# -----------------------------
# Unlock Gate
# -----------------------------

def ensure_unlocked() -> None:
    """Gate the app behind PayPal subscription ID + required email.

    CRITICAL FIX:
    - Do NOT write to st.session_state["email"] every rerun.
      Streamlit manages widget state; forcing it resets the input each keystroke
      and makes it look like "you can't type".
    """

    if os.getenv("PAYMENT_DISABLED", "0") == "1":
        st.session_state["unlocked"] = True
        return

    if st.session_state.get("unlocked", False):
        return

    qp = _get_query_params()
    sub_id_from_qp = ""
    if "subscription_id" in qp:
        v = qp["subscription_id"]
        sub_id_from_qp = v[0] if isinstance(v, list) else str(v)

    client_id = _get_cfg("PAYPAL_CLIENT_ID")
    plan_id = _get_cfg("PAYPAL_PLAN_ID")

    st.title("Unlock access")
    st.write("Subscribe to unlock the app.")

    # Email input (must be editable)
    # Use a UNIQUE key so we don't get stuck with any bad/old session_state from earlier versions.
    if "unlock_email_input_v25" not in st.session_state:
        st.session_state["unlock_email_input_v25"] = ""

    email = st.text_input(
        "Email (for receipt + access records)",
        key="unlock_email_input_v25",
        placeholder="your@email.com",
    )

    # Only show the PayPal embed AFTER the user has entered an email.
    # This avoids any possibility of the embedded PayPal iframe/script stealing focus.
    if not email.strip():
        st.info("Enter your email first. Then the PayPal Subscribe button will appear.")
    else:
        if client_id and plan_id:
            components.html(paypal_subscribe_button_html(client_id, plan_id), height=220)
        else:
            st.warning(
                "PayPal is not configured yet. Set PAYPAL_CLIENT_ID and PAYPAL_PLAN_ID in Render environment variables."
            )

    st.markdown("---")
    st.write("Already subscribed? Paste your PayPal subscription ID:")

    sub_id_manual = st.text_input(
        "Subscription ID",
        key="subscription_id",
        value=sub_id_from_qp,
        placeholder="I-XXXXXXXXXXXX",
    )

    # Unlock
    if st.button("Unlock", type="primary"):
        if not email.strip():
            st.error("Please enter your email.")
            st.stop()

        if not sub_id_manual.strip():
            st.error("Please enter a subscription ID.")
            st.stop()

        st.session_state["unlocked"] = True

        _append_jsonl(
            os.path.join(_data_dir(), "unlock_log.jsonl"),
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "email": email.strip(),
                "subscription_id": sub_id_manual.strip(),
                "app": "pressure_balance_cubic6",
            },
        )

        st.success("Unlocked. Loading app…")
        st.rerun()

    st.caption("© Mountain Race Shop™ 2025–2026 | Support: fenianparktrading@gmail.com")
    st.stop()


# -----------------------------
# Main App
# -----------------------------

ensure_unlocked()

st.title("Suspension Engineering – Pressure Balance, Adjuster Authority & Damping Targets")
st.caption("© Mountain Race Shop™ 2025–2026 | Support: fenianparktrading@gmail.com")

model = st.sidebar.selectbox("Curve fit model", ["Linear", "Quadratic", "Cubic"], key="model")

st.sidebar.header("Geometry & Pressure Inputs")
p1 = st.sidebar.number_input("Baseline pressure P1 (bar)", value=10.0, key="p1")
rod_d = st.sidebar.number_input("Rod diameter (mm)", value=10.0, key="rod_d")
piston_d = st.sidebar.number_input("Body / piston diameter (mm)", value=46.0, key="piston_d")
v_ref = st.sidebar.number_input("Velocity reference (m/s)", value=1.0, key="v_ref")


def fit_curve(x: np.ndarray, y: np.ndarray, curve_model: str):
    deg = {"Linear": 1, "Quadratic": 2, "Cubic": 3}[curve_model]
    uniq = len(np.unique(x))
    if uniq <= 1:
        deg = 1
    elif uniq <= deg:
        deg = uniq - 1
    coeffs = np.polyfit(x, y, deg)
    return np.poly1d(coeffs), deg


def _safe_ratio(a: np.ndarray, b: np.ndarray) -> float:
    b2 = np.where(b == 0, np.nan, b)
    r = a / b2
    r = r[np.isfinite(r)]
    if r.size == 0:
        return float("nan")
    return float(np.nanmax(r) * 100.0)


st.header("Compression – 6 Point Definition")
cols = st.columns(6)

v, f_adj, f_full = [], [], []
for i in range(6):
    with cols[i]:
        v.append(st.number_input(f"V{i+1} (m/s)", value=0.5 * (i + 1), key=f"cv{i}"))
        f_adj.append(st.number_input(f"Adj-only F{i+1} (N)", value=300 * (i + 1), key=f"ca{i}"))
        f_full.append(st.number_input(f"Full F{i+1} (N)", value=1200 * (i + 1), key=f"cf{i}"))

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

peak_adj_ratio = _safe_ratio(f_adj, f_full)

st.header("Rebound – 6 Point Definition")
cols_r = st.columns(6)
rv, rf_adj, rf_full = [], [], []
for i in range(6):
    with cols_r[i]:
        rv.append(st.number_input(f"R V{i+1} (m/s)", value=0.5 * (i + 1), key=f"rv{i}"))
        rf_adj.append(st.number_input(f"Rebound Adj-only F{i+1} (N)", value=500 * (i + 1), key=f"ra{i}"))
        rf_full.append(st.number_input(f"Rebound Full F{i+1} (N)", value=1500 * (i + 1), key=f"rf{i}"))

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
        "Rebound Adj-only (N)": r_adj_dense,
        "Rebound Full (N)": r_full_dense,
    }
)

st.metric("Peak Adjuster %", "—" if not np.isfinite(peak_adj_ratio) else f"{peak_adj_ratio:.1f}%")

st.info("Target band typically 15–20%. Above this = adjuster doing too much of the job.")
if np.isfinite(peak_adj_ratio) and peak_adj_ratio < 15:
    st.warning("Adjuster below 15% authority will have little to no real effect.")

