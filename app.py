"""
Suspension Engineering – Pressure Balance App (Cubic 6-Point)
Locked web version (PayPal-gated).

© Mountain Race Shop™ 2025–2026. All rights reserved.
Support: fenianparktrading@gmail.com
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import streamlit as st
import streamlit.components.v1 as components


# Must be first Streamlit call
st.set_page_config(
    page_title="Suspension Engineering – Pressure Balance & Adjuster Authority",
    layout="wide",
)


# ----------------- Helpers -----------------
def _get_cfg(key: str, default: str = "") -> str:
    v = os.getenv(key, "")
    if v:
        return v
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def _get_query_params() -> dict:
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
    return f"""
<div id="paypal-button-container"></div>
<script src="https://www.paypal.com/sdk/js?client-id={client_id}&vault=true&intent=subscription"></script>
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


# ----------------- Unlock gate -----------------
def ensure_unlocked() -> None:
    if os.getenv("PAYMENT_DISABLED", "0") == "1":
        st.session_state["unlocked"] = True
        return

    if st.session_state.get("unlocked"):
        return

    qp = _get_query_params()
    sub_id_from_url = ""
    if "subscription_id" in qp:
        v = qp["subscription_id"]
        sub_id_from_url = v[0] if isinstance(v, list) else str(v)

    client_id = _get_cfg("PAYPAL_CLIENT_ID")
    plan_id = _get_cfg("PAYPAL_PLAN_ID")

    st.title("Unlock access")
    st.write("Subscribe to unlock the app.")

    # IMPORTANT: initialize session_state keys ONCE, then use key= only (no value=)
    if "email_input" not in st.session_state:
        st.session_state["email_input"] = ""
    if "sub_id_input" not in st.session_state:
        st.session_state["sub_id_input"] = sub_id_from_url or ""

    # Keep email above the PayPal iframe (and do NOT write back manually)
    st.text_input(
        "Email (for receipt + access records)",
        key="email_input",
        placeholder="you@company.com",
    )

    if client_id and plan_id:
        components.html(
            paypal_subscribe_button_html(client_id, plan_id),
            height=240,
        )
    else:
        st.warning(
            "PayPal is not configured yet. Set PAYPAL_CLIENT_ID and PAYPAL_PLAN_ID in Render environment variables."
        )

    st.write("Already subscribed? Paste your PayPal subscription ID:")

    st.text_input(
        "Subscription ID",
        key="sub_id_input",
        placeholder="I-XXXXXXXXXXXX",
    )

    if st.button("Unlock", key="unlock_btn"):
        email = (st.session_state.get("email_input") or "").strip()
        sub_id_final = (st.session_state.get("sub_id_input") or "").strip()

        if not email:
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
                "email": email,
                "subscription_id": sub_id_final,
                "app": "pressure_balance_cubic6",
            },
        )

        st.success("Unlocked. Loading app…")
        st.rerun()

    st.caption("© Mountain Race Shop™ 2025–2026. All rights reserved.")
    st.stop()


# ----------------- Curve fit -----------------
def fit_curve(x: np.ndarray, y: np.ndarray, model_name: str):
    deg = {"Linear": 1, "Quadratic": 2, "Cubic": 3}[model_name]
    unique_n = len(np.unique(x))
    if unique_n <= deg:
        deg = max(1, unique_n - 1)
    coeffs = np.polyfit(x, y, deg)
    return np.poly1d(coeffs), deg


def chart_xy(x: np.ndarray, y1: np.ndarray, y2: np.ndarray, label1: str, label2: str):
    # Avoid requiring pandas; Streamlit can chart arrays but x-axis becomes index.
    # This still works reliably on Render.
    data = np.column_stack([y1, y2])
    st.line_chart(data)


# ----------------- Main app -----------------
ensure_unlocked()

st.title("Suspension Engineering – Pressure Balance, Adjuster Authority & Damping Targets")
st.caption("© Mountain Race Shop™ 2025–2026 | Support: fenianparktrading@gmail.com")

model = st.sidebar.selectbox("Curve fit model", ["Linear", "Quadratic", "Cubic"], key="curve_model")

st.sidebar.header("Geometry & Pressure Inputs")
p1 = st.sidebar.number_input("Baseline pressure P1 (bar)", value=10.0, key="p1")
rod_d = st.sidebar.number_input("Rod diameter (mm)", value=10.0, key="rod_d")
piston_d = st.sidebar.number_input("Body / piston diameter (mm)", value=46.0, key="piston_d")
v_ref = st.sidebar.number_input("Velocity reference (m/s)", value=1.0, key="v_ref")

st.header("Compression – 6 Point Definition")

cols = st.columns(6)
v, f_adj, f_full = [], [], []

for i in range(6):
    with cols[i]:
        v.append(st.number_input(f"V{i+1} (m/s)", value=0.5 * (i + 1), key=f"cv{i+1}"))
        f_adj.append(st.number_input(f"Adj-only F{i+1} (N)", value=300 * (i + 1), key=f"cfa{i+1}"))
        f_full.append(st.number_input(f"Full F{i+1} (N)", value=1200 * (i + 1), key=f"cff{i+1}"))

v = np.array(v, dtype=float)
f_adj = np.array(f_adj, dtype=float)
f_full = np.array(f_full, dtype=float)

curve_adj, used_deg_adj = fit_curve(v, f_adj, model)
curve_full, used_deg_full = fit_curve(v, f_full, model)

v_dense = np.linspace(float(np.min(v)), float(np.max(v)), 200)
adj_dense = curve_adj(v_dense)
full_dense = curve_full(v_dense)

st.subheader("Compression Results")
st.write(f"Adj-only model used: Degree {used_deg_adj}")
st.write(f"Full-force model used: Degree {used_deg_full}")
chart_xy(v_dense, adj_dense, full_dense, "Adj-only", "Full")

peak_adj_ratio = float(np.max(f_adj / np.maximum(f_full, 1e-9)) * 100.0)
st.metric("Peak Adjuster % (Compression)", f"{peak_adj_ratio:.1f}%")

st.markdown("---")
st.header("Rebound – 6 Point Definition")

rcols = st.columns(6)
rv, rf_adj, rf_full = [], [], []

for i in range(6):
    with rcols[i]:
        rv.append(st.number_input(f"R V{i+1} (m/s)", value=0.5 * (i + 1), key=f"rv{i+1}"))
        rf_adj.append(st.number_input(f"Rebound Adj-only F{i+1} (N)", value=500 * (i + 1), key=f"rfa{i+1}"))
        rf_full.append(st.number_input(f"Rebound Full F{i+1} (N)", value=1500 * (i + 1), key=f"rff{i+1}"))

rv = np.array(rv, dtype=float)
rf_adj = np.array(rf_adj, dtype=float)
rf_full = np.array(rf_full, dtype=float)

r_curve_adj, used_r_deg_adj = fit_curve(rv, rf_adj, model)
r_curve_full, used_r_deg_full = fit_curve(rv, rf_full, model)

rv_dense = np.linspace(float(np.min(rv)), float(np.max(rv)), 200)
r_adj_dense = r_curve_adj(rv_dense)
r_full_dense = r_curve_full(rv_dense)

st.subheader("Rebound Results")
st.write(f"Adj-only model used: Degree {used_r_deg_adj}")
st.write(f"Full-force model used: Degree {used_r_deg_full}")
chart_xy(rv_dense, r_adj_dense, r_full_dense, "Rebound Adj-only", "Rebound Full")

r_peak_adj_ratio = float(np.max(rf_adj / np.maximum(rf_full, 1e-9)) * 100.0)
st.metric("Peak Adjuster % (Rebound)", f"{r_peak_adj_ratio:.1f}%")

st.info("Target band typically 15–20%. If much higher, the adjuster is doing too much of the job.")
if peak_adj_ratio < 15:
    st.warning("Compression adjuster below 15% authority will have little to no real effect.")
if r_peak_adj_ratio < 15:
    st.warning("Rebound adjuster below 15% authority will have little to no real effect.")

st.caption("© Mountain Race Shop™ 2025–2026 | Support: fenianparktrading@gmail.com")
