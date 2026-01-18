
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


def _get_cfg(key: str, default: str = "") -> str:
    """Read config from environment first, then Streamlit secrets if available.

    On some hosts (e.g. Render), st.secrets may be unavailable unless a secrets.toml is provided.
    This helper avoids StreamlitSecretNotFoundError by catching any secrets access errors.
    """
    v = os.getenv(key, "")
    if v:
        return v
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default
# Streamlit requires page config before any other Streamlit calls.
st.set_page_config(page_title="Suspension Engineering – Pressure Balance & Adjuster Authority", layout="wide")


def _get_query_params() -> dict:
    """Compatibility wrapper across Streamlit versions."""
    try:
        # New API
        return dict(st.query_params)
    except Exception:
        # Old API
        return st.experimental_get_query_params()


def _data_dir() -> str:
    d = os.getenv("DATA_DIR", ".data")
    os.makedirs(d, exist_ok=True)
    return d


def _append_jsonl(path: str, payload: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def paypal_subscribe_button_html(client_id: str, plan_id: str) -> str:
    # PayPal JS SDK subscription button. On approve, redirects back with subscription_id.
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
    """Gate the app behind PayPal subscription ID.

    This intentionally keeps verification lightweight (stores subscription ID + email for records).
    """

    if os.getenv("PAYMENT_DISABLED", "0") == "1":
        st.session_state["unlocked"] = True
        return

    if st.session_state.get("unlocked"):
        return

    qp = _get_query_params()
    sub_id = None
    # handle both dict/list formats
    if "subscription_id" in qp:
        v = qp["subscription_id"]
        sub_id = v[0] if isinstance(v, list) else v

    st.title("Pressure Balance App")
    st.caption("Mountain Race Shop™ | Suspension Engineering™")

    st.markdown(
        """
**Why pressure balance matters**

Suspension performance is controlled by pressure — but pressure is rarely measured directly.
This tool converts dyno force data into internal pressures so your setup decisions are based on physics, not guesswork.

**Core principle:** Force = Area × Pressure → Pressure = Force ÷ Area
        """
    )

    # Collect email + show PayPal button
    email = st.text_input("Email (for receipt + access records)")

    client_id = _get_cfg("PAYPAL_CLIENT_ID")
    plan_id = _get_cfg("PAYPAL_PLAN_ID")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Unlock access")
        st.write("Subscribe to unlock the app.")

        if client_id and plan_id:
            components.html(paypal_subscribe_button_html(client_id, plan_id), height=220)
        else:
            st.warning(
                "PayPal is not configured yet. Set PAYPAL_CLIENT_ID and PAYPAL_PLAN_ID in your host (Render) environment variables."
            )

        st.write("Already subscribed? Paste your PayPal subscription ID:")
        # Be defensive: if 'sub_id' isn't available for any reason, fall back to blank.
        try:
            _sub_id_prefill = sub_id or ""
        except NameError:
            _sub_id_prefill = ""

        manual_sub_id = st.text_input("Subscription ID", value=_sub_id_prefill)
        sub_id_final = manual_sub_id.strip() or _sub_id_prefill

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

    with col2:
        st.subheader("What you need")
        st.markdown(
            """
- Baseline pressure P1 (bar)
- Rod diameter (mm)
- Body/piston diameter (mm)
- **Up to 6 velocity points** (m/s)
- Corresponding dyno forces (N): **Adj-only** and **Full**

Then choose Linear / Quadratic / Cubic and compare how well each model fits your data.
            """
        )

    st.markdown("---")
    st.caption("© Mountain Race Shop™ 2025–2026. All rights reserved.")
    st.stop()


ensure_unlocked()

st.title("Suspension Engineering – Pressure Balance, Adjuster Authority & Damping Targets")
st.caption("© Mountain Race Shop™ 2025–2026. All rights reserved.")

model = st.sidebar.selectbox("Curve fit model", ["Linear", "Quadratic", "Cubic"])

st.sidebar.header("Geometry & Pressure Inputs")
p1 = st.sidebar.number_input("Baseline pressure P1 (bar)", value=10.0)
rod_d = st.sidebar.number_input("Rod diameter (mm)", value=10.0)
piston_d = st.sidebar.number_input("Body / piston diameter (mm)", value=46.0)
v_ref = st.sidebar.number_input("Velocity reference (m/s)", value=1.0)

st.header("Compression – 6 Point Definition")

cols = st.columns(6)
v = []
f_adj = []
f_full = []
for i in range(6):
    with cols[i]:
        v.append(st.number_input(f"V{i+1} (m/s)", value=0.5*(i+1)))
        f_adj.append(st.number_input(f"Adj-only F{i+1} (N)", value=300*(i+1)))
        f_full.append(st.number_input(f"Full F{i+1} (N)", value=1200*(i+1)))

v = np.array(v, dtype=float)
f_adj = np.array(f_adj, dtype=float)
f_full = np.array(f_full, dtype=float)

def fit_curve(x, y, model):
    deg = {"Linear":1, "Quadratic":2, "Cubic":3}[model]
    if len(np.unique(x)) <= deg:
        deg = len(np.unique(x)) - 1
    coeffs = np.polyfit(x, y, deg)
    return np.poly1d(coeffs), deg

curve_adj, used_deg_adj = fit_curve(v, f_adj, model)
curve_full, used_deg_full = fit_curve(v, f_full, model)

v_dense = np.linspace(min(v), max(v), 200)
adj_dense = curve_adj(v_dense)
full_dense = curve_full(v_dense)

st.subheader("Results")
st.write(f"Adj-only model used: Degree {used_deg_adj}")
st.write(f"Full-force model used: Degree {used_deg_full}")

st.line_chart({
    "Velocity (m/s)": v_dense,
    "Adj-only force (N)": adj_dense,
    "Full force (N)": full_dense
})

peak_adj_ratio = max(f_adj / f_full) * 100

st.markdown("## Rebound – 6 Point Definition")

rv = []
rf_adj = []
rf_full = []
for i in range(1,7):
    rv.append(st.number_input(f"R V{i} (m/s)", value=float(i)*0.5, key=f"rv{i}"))
    rf_adj.append(st.number_input(f"Rebound Adj-only F{i} (N)", value=500*i, key=f"rfadj{i}"))
    rf_full.append(st.number_input(f"Rebound Full F{i} (N)", value=1500*i, key=f"rffull{i}"))

rv = np.array(rv)
rf_adj = np.array(rf_adj)
rf_full = np.array(rf_full)

r_curve_adj, used_r_deg_adj = fit_curve(rv, rf_adj, curve_model)
r_curve_full, used_r_deg_full = fit_curve(rv, rf_full, curve_model)

rv_dense = np.linspace(min(rv), max(rv), 100)
r_adj_dense = r_curve_adj(rv_dense)
r_full_dense = r_curve_full(rv_dense)

st.markdown("### Rebound Results")
fig2, ax2 = plt.subplots()
ax2.plot(rv_dense, r_adj_dense, label="Rebound Adj-only")
ax2.plot(rv_dense, r_full_dense, label="Rebound Full")
ax2.legend()
ax2.set_xlabel("Velocity (m/s)")
ax2.set_ylabel("Force (N)")
st.pyplot(fig2)


st.metric("Peak Adjuster %", f"{peak_adj_ratio:.1f}%")

st.info("Target band typically 15–20%. Above this = adjuster doing too much of the job.")
if peak_adj_ratio < 15:
    st.warning("Adjuster below 15% authority will have little to no real effect.")

st.caption("© Mountain Race Shop™ 2025–2026 | Support: fenianparktrading@gmail.com")
