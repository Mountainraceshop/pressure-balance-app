import os
import json
from datetime import datetime, timezone

import numpy as np
import streamlit as st
import streamlit.components.v1 as components

# ------------------ BASIC SETUP ------------------

st.set_page_config(
    page_title="Suspension Engineering – Pressure Balance",
    layout="wide"
)

def data_dir():
    d = os.getenv("DATA_DIR", ".data")
    os.makedirs(d, exist_ok=True)
    return d

def append_jsonl(path, payload):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")

def get_cfg(key, default=""):
    v = os.getenv(key, "")
    if v:
        return v
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

# ------------------ PAYPAL BUTTON ------------------

def paypal_button(client_id, plan_id):
    return f"""
<div id="paypal-button-container"></div>
<script src="https://www.paypal.com/sdk/js?client-id={client_id}&vault=true&intent=subscription"></script>
<script>
paypal.Buttons({{
  createSubscription: function(data, actions) {{
    return actions.subscription.create({{
      'plan_id': '{plan_id}'
    }});
  }},
  onApprove: function(data, actions) {{
    const url = new URL(window.location.href);
    url.searchParams.set('subscription_id', data.subscriptionID);
    window.location.href = url.toString();
  }}
}}).render('#paypal-button-container');
</script>
"""

# ------------------ UNLOCK GATE ------------------

def ensure_unlocked():
    if os.getenv("PAYMENT_DISABLED", "0") == "1":
        st.session_state["unlocked"] = True
        return

    if st.session_state.get("unlocked"):
        return

    if "email" not in st.session_state:
        st.session_state.email = ""

    # Read query param
    try:
        qp = dict(st.query_params)
    except Exception:
        qp = st.experimental_get_query_params()

    sub_from_url = ""
    if "subscription_id" in qp:
        v = qp["subscription_id"]
        sub_from_url = v[0] if isinstance(v, list) else v

    st.title("Unlock access")
    st.write("Subscribe to unlock the app.")

    # ---- EMAIL INPUT (THIS MUST WORK) ----
    email = st.text_input(
        "Email (for receipt + access records)",
        value=st.session_state.email,
        key="email_box"
    )
    st.session_state.email = email

    if not email.strip():
        st.info("Enter your email first. Then the PayPal button will appear.")

    client_id = get_cfg("PAYPAL_CLIENT_ID")
    plan_id = get_cfg("PAYPAL_PLAN_ID")

    if email.strip() and client_id and plan_id:
        components.html(paypal_button(client_id, plan_id), height=220)
    elif not client_id or not plan_id:
        st.warning("PayPal not configured on server yet.")

    st.markdown("---")
    st.write("Already subscribed? Paste your PayPal subscription ID:")

    sub_id = st.text_input("Subscription ID", value=sub_from_url, key="sub_box")

    if st.button("Unlock"):
        if not st.session_state.email.strip():
            st.error("Please enter your email.")
            st.stop()

        if not sub_id.strip():
            st.error("Please enter a subscription ID.")
            st.stop()

        st.session_state["unlocked"] = True

        append_jsonl(
            os.path.join(data_dir(), "unlock_log.jsonl"),
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "email": st.session_state.email.strip(),
                "subscription_id": sub_id.strip(),
                "app": "pressure_balance_cubic6",
            },
        )

        st.success("Unlocked. Reloading…")
        st.rerun()

    st.stop()

# ------------------ GATE ------------------

ensure_unlocked()

# ------------------ MAIN APP ------------------

st.title("Suspension Engineering – Pressure Balance")
st.caption("© Mountain Race Shop™ 2025–2026")

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
        v.append(st.number_input(f"V{i+1}", value=0.5*(i+1)))
        f_adj.append(st.number_input(f"Adj F{i+1}", value=300*(i+1)))
        f_full.append(st.number_input(f"Full F{i+1}", value=1200*(i+1)))

v = np.array(v, float)
f_adj = np.array(f_adj, float)
f_full = np.array(f_full, float)

def fit_curve(x, y, model):
    deg = {"Linear":1, "Quadratic":2, "Cubic":3}[model]
    if len(np.unique(x)) <= deg:
        deg = len(np.unique(x)) - 1
    p = np.polyfit(x, y, deg)
    return np.poly1d(p), deg

curve_adj, deg_adj = fit_curve(v, f_adj, model)
curve_full, deg_full = fit_curve(v, f_full, model)

vd = np.linspace(min(v), max(v), 200)
adj_d = curve_adj(vd)
full_d = curve_full(vd)

st.subheader("Results")
st.write(f"Adj model degree: {deg_adj}")
st.write(f"Full model degree: {deg_full}")

st.line_chart({
    "Velocity": vd,
    "Adj-only": adj_d,
    "Full": full_d
})

peak_adj_ratio = max(f_adj / f_full) * 100
st.metric("Peak Adjuster %", f"{peak_adj_ratio:.1f}%")

st.caption("Support: fenianparktrading@gmail.com")
