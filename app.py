# app.py
# Mountain Race Shop – Suspension Engineering
# © 2025 Fenian Park Trading Pty Ltd (trading as Mountain Race Shop™). All rights reserved.

import math
import csv
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# Config
# ============================================================
st.set_page_config(
    page_title="Suspension Engineering – Pressure Balance / Adjuster Authority",
    layout="wide",
)

APP_DIR = Path(__file__).resolve().parent


# ============================================================
# Compatibility helpers (older Streamlit)
# ============================================================
def get_query_params():
    """Return dict of query params (supports old + new Streamlit)."""
    try:
        qp = st.query_params  # newer
        # st.query_params behaves like a mapping; values can be str or list
        out = {}
        for k in qp.keys():
            v = qp.get(k)
            if isinstance(v, list):
                out[k] = v[0] if v else ""
            else:
                out[k] = v if v is not None else ""
        return out
    except Exception:
        qp = st.experimental_get_query_params()
        out = {}
        for k, v in qp.items():
            out[k] = v[0] if isinstance(v, list) and v else (v if isinstance(v, str) else "")
        return out


def set_query_params(**kwargs):
    """Set query params (supports old + new Streamlit)."""
    try:
        st.query_params.update(kwargs)  # newer
    except Exception:
        st.experimental_set_query_params(**kwargs)


def rerun():
    """Rerun (supports old + new Streamlit)."""
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()


# ============================================================
# Branding + Footer
# ============================================================
def show_branding():
    logo_candidates = [
        APP_DIR / "logo.png",
        APP_DIR / "logo.jpg",
        APP_DIR / "logo.jpeg",
        APP_DIR / "1000000413.jpg",
    ]
    logo_path = next((p for p in logo_candidates if p.exists()), None)

    c1, c2 = st.columns([1, 5])
    with c1:
        if logo_path:
            # Avoid use_container_width for older Streamlit
            st.image(str(logo_path), width=160)
    with c2:
        st.markdown(
            """
            <div style="padding-top:6px">
              <div style="font-size:30px; font-weight:800; line-height:1.1">
                Suspension Engineering – Pressure Balance, Adjuster Authority & Damping Targets
              </div>
              <div style="opacity:0.75; margin-top:6px">
                Mountain Race Shop™ • Engineering-backed suspension tuning — proven on track, validated by data.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def footer():
    st.markdown("---")
    st.caption("© 2025 Mountain Race Shop™. All rights reserved.")


# ============================================================
# PayPal unlock (simple, browser-session unlock)
# ============================================================
CLIENT_ID = "AUE4CAO_0aLpL2V_v2hjgjjlLrYNNZ5u-E8IhDNFmkTtKVCRyzm1XCFWTAO1RQDg0e3VcAyVeC2agAOB"
PLAN_ID = "P-2M332804VD909241WNFPUZ3Y"


def paypal_button_html():
    """
    IMPORTANT REALITY CHECK:
    Some PayPal subscription flows take over the tab and do NOT reliably call onApprove in an iframe/popup,
    especially in certain browser/privacy settings.

    So we provide:
      - best-effort onApprove redirect to add ?subscription_id=... (works when PayPal calls onApprove)
      - a manual "paste subscription id" fallback (always works)
    """
    return f"""
<div id="paypal-button-container"></div>

<script src="https://www.paypal.com/sdk/js?client-id={CLIENT_ID}&vault=true&intent=subscription" data-sdk-integration-source="button-factory"></script>

<script>
  paypal.Buttons({{
      style: {{
          shape: 'rect',
          color: 'gold',
          layout: 'vertical',
          label: 'subscribe'
      }},
      createSubscription: function(data, actions) {{
        return actions.subscription.create({{
          plan_id: '{PLAN_ID}'
        }});
      }},
      onApprove: function(data, actions) {{
        try {{
          const sub = data.subscriptionID;
          const url = new URL(window.location.href);
          url.searchParams.set('subscription_id', sub);
          window.location.href = url.toString();
        }} catch (e) {{
          console.log("onApprove redirect failed", e);
        }}
      }},
      onError: function(err) {{
        console.log("PayPal error:", err);
      }}
  }}).render('#paypal-button-container');
</script>
"""


def is_unlocked():
    # 1) Query param unlock
    qp = get_query_params()
    sub = qp.get("subscription_id", "").strip()
    if sub:
        st.session_state["subscription_id"] = sub
        st.session_state["unlocked"] = True

    # 2) Session state unlock
    return bool(st.session_state.get("unlocked", False))


def gate_paypal_ui():
    st.subheader("Unlock (PayPal)")
    st.write(
        "Subscribe to unlock the Pressure Balance app. If PayPal returns you here automatically, you’ll be unlocked straight away."
    )
    components.html(paypal_button_html(), height=260)

    st.info(
        "If PayPal takes over the whole tab and you don’t come back here automatically: "
        "open your PayPal receipt and copy the Subscription ID (looks like I-XXXXXXXXXXXX) and paste it below."
    )

    st.markdown("### Already paid but didn’t redirect?")
    manual = st.text_input("Paste your PayPal Subscription ID (looks like I-XXXXXXXXXXXX)")
    if st.button("Unlock using Subscription ID"):
        if manual.strip():
            st.session_state["subscription_id"] = manual.strip()
            st.session_state["unlocked"] = True
            rerun()


# ============================================================
# Customer email capture
# ============================================================
def save_customer_email(email: str, subscription_id: str):
    out = APP_DIR / "customers.csv"
    new_file = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp", "email", "subscription_id"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), email, subscription_id])


def require_email_capture():
    """
    Require once per browser session.
    If you want true "once per customer", you’d validate against PayPal + store server-side.
    """
    if not is_unlocked():
        return False

    if st.session_state.get("email_saved", False):
        return True

    st.markdown("### Customer details")
    st.write("Enter your email so we can send updates, support, and future tools (e.g. Shim App).")
    email = st.text_input("Email", placeholder="you@example.com")
    if st.button("Save email"):
        if "@" not in email or "." not in email:
            st.error("Please enter a valid email address.")
            return False
        save_customer_email(email=email.strip(), subscription_id=st.session_state.get("subscription_id", ""))
        st.session_state["email_saved"] = True
        st.success("Saved. Thank you!")
        return True

    return False


# ============================================================
# Calculations
# ============================================================
def interp_force(v: float, pts):
    pts = sorted(pts, key=lambda x: x[0])
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if v <= xs[0]:
        return ys[0]
    if v >= xs[-1]:
        return ys[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= v <= xs[i + 1]:
            t = (v - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] * (1 - t) + ys[i + 1] * t
    return ys[-1]


def adjuster_authority_percent(vref, adj_pts, full_pts):
    adj = interp_force(vref, adj_pts)
    full = interp_force(vref, full_pts)
    if full <= 0:
        return 0.0
    return 100.0 * (adj / full)


def critical_damping_target(zeta, spring_rate_n_per_mm, mass_kg, velocity_mps):
    # Simple 1-DOF model:
    # c_crit = 2 * sqrt(k*m)
    # c = zeta * c_crit
    # Force = c * v
    k = spring_rate_n_per_mm * 1000.0  # N/m
    if k <= 0 or mass_kg <= 0:
        return 0.0
    ccrit = 2.0 * math.sqrt(k * mass_kg)
    c = zeta * ccrit
    return c * velocity_mps  # N


def area_mm2(d_mm: float) -> float:
    r = d_mm / 2.0
    return math.pi * r * r


def pressure_bar(force_n: float, area_mm2_val: float) -> float:
    # Pa = N / m^2; 1 mm^2 = 1e-6 m^2; bar = Pa / 1e5
    if area_mm2_val <= 0:
        return 0.0
    pa = force_n / (area_mm2_val * 1e-6)
    return pa / 1e5


# ============================================================
# UI helpers
# ============================================================
def input_3point(prefix: str, defaults):
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        v1 = st.number_input("V1 (m/s)", value=float(defaults[0][0]), step=0.05, key=f"{prefix}_v1")
        v2 = st.number_input("V2 (m/s)", value=float(defaults[1][0]), step=0.05, key=f"{prefix}_v2")
        v3 = st.number_input("V3 (m/s)", value=float(defaults[2][0]), step=0.05, key=f"{prefix}_v3")
    with c2:
        a1 = st.number_input("Adj-only F1 (N)", value=float(defaults[0][1]), step=50.0, key=f"{prefix}_a1")
        a2 = st.number_input("Adj-only F2 (N)", value=float(defaults[1][1]), step=50.0, key=f"{prefix}_a2")
        a3 = st.number_input("Adj-only F3 (N)", value=float(defaults[2][1]), step=50.0, key=f"{prefix}_a3")
    with c3:
        f1 = st.number_input("Full F1 (N)", value=float(defaults[0][2]), step=50.0, key=f"{prefix}_f1")
        f2 = st.number_input("Full F2 (N)", value=float(defaults[1][2]), step=50.0, key=f"{prefix}_f2")
        f3 = st.number_input("Full F3 (N)", value=float(defaults[2][2]), step=50.0, key=f"{prefix}_f3")

    adj_pts = [(float(v1), float(a1)), (float(v2), float(a2)), (float(v3), float(a3))]
    full_pts = [(float(v1), float(f1)), (float(v2), float(f2)), (float(v3), float(f3))]
    return adj_pts, full_pts


def compute_table(adj_pts, full_pts, label, zeta, spring_rate, mass_kg, v_max, v_step):
    velocities = np.arange(0.0, float(v_max) + 1e-9, float(v_step))
    rows = []
    for v in velocities:
        if v == 0:
            continue
        adj = interp_force(v, adj_pts)
        full = interp_force(v, full_pts)
        pct = 0.0 if full <= 0 else 100.0 * adj / full
        z_force = critical_damping_target(zeta, spring_rate, mass_kg, v)
        rows.append([label, v, adj, full, pct, z_force])
    return pd.DataFrame(
        rows,
        columns=["Mode", "Velocity (m/s)", "Adj-only (N)", "Full (N)", "Adj %", "ζ target F (N)"],
    )


# ============================================================
# Pages: Home / Tools / Terms / Privacy
# ============================================================
TERMS_TEXT = """Mountain Race Shop™
Terms & Conditions of Use
Pressure Balance & Suspension Engineering Tools
Effective date: 2025
Owner: Fenian Park Trading Pty Ltd (trading as Mountain Race Shop™)

1. Acceptance of Terms
By accessing or using any Mountain Race Shop™ online tools, calculators, software, or applications (“the Tools”), you agree to be bound by these Terms and Conditions.
If you do not agree to these Terms, you must not access or use the Tools.

2. Nature of the Service
The Tools provide engineering-based calculations, estimates, and visualisations intended to assist professional judgment.
You acknowledge that the Tools:
• Are decision-support tools only
• Do not replace professional inspection, testing, or validation
• Are not a guarantee of performance, safety, or suitability for any purpose

3. No Warranty or Guarantee
All outputs and services are provided “as is” and “as available” without warranties of any kind, whether express or implied.
Mountain Race Shop™ makes no guarantees regarding:
• Accuracy under all conditions
• Suitability for any specific motorcycle, rider, terrain, or application
• Real-world performance outcomes

4. Professional Responsibility
You acknowledge and agree that:
• Suspension setup is highly application-specific
• Final setup decisions remain solely your responsibility
• Testing, rider feedback, and safety checks are mandatory
You agree not to rely solely on the Tools for safety-critical decisions.

5. Limitation of Liability
To the maximum extent permitted by law:
Mountain Race Shop™, Fenian Park Trading Pty Ltd, and their directors, employees, contractors, or agents shall not be liable for any loss or damage, including but not limited to:
• Personal injury or death
• Equipment damage or mechanical failure
• Financial or business loss
• Track, race, trail, or road incidents
Whether arising from use, misuse, reliance on, or inability to use the Tools.

6. User Responsibility
By using the Tools, you confirm that you:
• Are suitably experienced, trained, or supervised
• Understand suspension systems and associated risks
• Accept full responsibility for any adjustments, tuning, or mechanical work performed

7. Payments & Access
Access to some Tools may require payment.
All payments:
• Are processed through third-party providers (e.g. PayPal)
• Are subject to the provider’s own terms and conditions
• Are non-refundable once access is granted, unless required by law

8. Intellectual Property
All software, content, calculations, models, text, graphics, and code are the intellectual property of:
© 2025 Fenian Park Trading Pty Ltd. All rights reserved.
You must not:
• Copy, redistribute, resell, or sublicense any part of the Tools
• Reverse-engineer or attempt to extract source logic
• Share paid access with third parties
• Reproduce outputs for commercial resale without written permission

9. Privacy
User information, including email addresses, may be collected for:
• Access control
• Customer support
• Product updates and service communication
We do not sell user data.
Full details are provided in the separate Privacy Policy.

10. Governing Law
These Terms are governed by the laws of New South Wales, Australia.
You agree to submit to the exclusive jurisdiction of the courts of New South Wales.

END OF TERMS
"""

PRIVACY_TEXT = """Mountain Race Shop™
Privacy Policy
Effective date: 2025
Owner: Fenian Park Trading Pty Ltd (trading as Mountain Race Shop™)

1. Overview
This Privacy Policy explains how we collect, store, use, and disclose personal information when you use our online tools, calculators, software, or applications (“the Tools”).

2. Information We Collect
We may collect:
• Email address (for customer support, access control, and updates)
• Payment confirmation identifiers (e.g. subscription ID) provided via third-party payment services
• Basic usage information required to operate the Tools (e.g. inputs you type into the app)
We do not intentionally collect sensitive information.

3. How We Use Information
We may use your information to:
• Provide access to paid features
• Provide customer support
• Improve our Tools and reliability
• Send product updates and service communications (you can opt out where applicable)

4. Disclosure
We may disclose information:
• To payment providers (e.g. PayPal) as required to process payments (under their terms)
• To service providers that help us operate the Tools (if applicable)
We do not sell your personal information.

5. Storage & Security
We take reasonable steps to protect personal information from misuse, loss, or unauthorised access. No method of transmission or storage is 100% secure.

6. Access & Correction
You may request access to personal information we hold about you and request corrections, subject to legal and practical limits.

7. Contact
For privacy questions, contact Mountain Race Shop™ / Fenian Park Trading Pty Ltd.

Express consent to collection, storage, use and disclosure
In addition to the other consents provided by you above, by agreeing to accept the terms of this privacy policy, or by providing your personal information to us, or both, you are taken to have expressly consented to the collection, storage, use and disclosure of your personal information for each of the purposes and to all of the parties outlined in this privacy policy.
"""


def nav_buttons():
    """Top navigation buttons on Home."""
    c1, c2, c3 = st.columns([1, 1, 6])
    with c1:
        if st.button("Terms"):
            st.session_state["page"] = "Terms"
            set_query_params(page="terms")
            rerun()
    with c2:
        if st.button("Privacy"):
            st.session_state["page"] = "Privacy"
            set_query_params(page="privacy")
            rerun()
    with c3:
        st.caption("Use the sidebar to switch pages anytime.")


def render_home():
    st.markdown("## Why Pressure Balance matters (and why this tool pays for itself)")
    st.markdown(
        """
**Most suspension tuning stops at clicks and “feel”. Pressure Balance puts hard numbers behind what’s happening inside the fork/shock.**

At its core:

**Force = Area × Pressure**

Your dyno gives you **force**. Your piston/rod/cartridge dimensions give you **area**. 
So we can calculate **pressure at the exact point you care about**:

**Pressure = Force ÷ Area**

### What you get from this app
- **Pressure at key points** (main area vs adjuster/rod area proxy)
- **Adjuster Authority %** (how much of the total damping force the adjuster circuit can influence)
- **Damping targets** using the **ζ (damping ratio) method** as a baseline reference curve
- Clear tables + graphs to support **repeatable tuning decisions**
- A consistent way to compare setups across bikes, pistons, base valves, mid valves, and shocks

If you tune professionally, this is about **reducing guesswork**, **speeding up setup**, and **making changes that translate to the track**.
        """
    )

    st.markdown("---")

    st.markdown("## Quick Start")
    st.markdown(
        """
1. **Unlock** the app (PayPal subscription).
2. **Enter your geometry** (rod diameter + piston/body diameter).
3. **Enter 3 dyno points** for Adj-only and Full (Compression and Rebound).
4. Review:
   - **Adj %** at your chosen reference velocity
   - **Pressure estimates (bar)** derived from Force ÷ Area
   - **ζ target force** curve as a baseline reference
5. Export tables to CSV for customer reports or build logs.
        """
    )

    st.markdown("---")

    st.markdown("## Data required (what you MUST have to use this properly)")
    st.markdown(
        """
### A) Dyno data (minimum)
You need **force (N)** at **known shaft velocities (m/s)** for **two curves**:
- **Adj-only**: adjuster circuit contribution (or an approximation you treat as the adjuster effect)
- **Full**: total damping force at that setting

This app uses **three points** (V1, V2, V3) to build a curve:
- Typical: **0.1 m/s**, **1.0 m/s**, **2.5–3.0 m/s**
- Typical Force ranges depend on your setup — use your dyno results.

### B) Geometry (to calculate pressure)
You need two diameters (mm):
- **Rod diameter (mm)** → used as an **adjuster area proxy**
- **Body/Piston diameter (mm)** → used as the **main area**

These create areas (mm²) so the app can estimate:
- **Main pressure (bar)** = Full Force ÷ Main Area
- **Adjuster pressure proxy (bar)** = Adj-only Force ÷ Rod/adjuster proxy Area

### C) Reference settings (recommended)
- **Reference velocity (m/s)** where you judge “adjuster authority” (often 1.0 m/s)
- **Target band** for adjuster authority (e.g. 15–20%)
- **ζ (damping ratio)** baseline (e.g. 0.30) + spring rate + effective mass (for a reference target force curve)
        """
    )

    st.markdown("---")

    st.markdown("## What the readings mean")
    st.markdown(
        """
### Adjuster Authority % (Adj %)
**Adj % = (Adj-only Force ÷ Full Force) × 100**

- **Higher %** → adjuster has more influence on the overall curve 
- **Lower %** → adjuster has less ability to change damping (you may feel “clicks do nothing”)

This helps explain:
- why a stack feels “dead” to clicks
- why some pistons/ports respond strongly to small adjuster changes

### Pressure (bar)
Because **Pressure = Force ÷ Area**, pressure gives you a more physics-grounded number than force alone.
It helps compare apples-to-apples across:
- different piston sizes
- different rod diameters
- different cartridge designs

### ζ target force
This is a **reference baseline** using a simple 1-DOF model:
- It is NOT “the truth”
- It is a **starting point** to compare your curve shape against a physics-based baseline
        """
    )

    st.markdown("---")

    # Links + Unlock section
    nav_buttons()

    st.markdown("---")
    st.markdown("## Unlock / Access")

    if not is_unlocked():
        st.warning("Locked: Subscribe to unlock full features.")
        with st.expander("Unlock (PayPal)", expanded=True):
            gate_paypal_ui()
    else:
        st.success("Unlocked ✅")
        require_email_capture()
        st.info("Go to **Tools** in the sidebar to access the calculators.")

    st.markdown("---")
    st.caption("By using this tool you agree to the Terms & Conditions and Privacy Policy.")


def render_terms():
    st.markdown("## Terms & Conditions of Use")
    st.text(TERMS_TEXT)
    st.markdown("---")
    if st.button("Back to Home"):
        st.session_state["page"] = "Home"
        set_query_params(page="home")
        rerun()


def render_privacy():
    st.markdown("## Privacy Policy")
    st.text(PRIVACY_TEXT)
    st.markdown("---")
    if st.button("Back to Home"):
        st.session_state["page"] = "Home"
        set_query_params(page="home")
        rerun()


def render_tools():
    if not is_unlocked():
        st.warning("Locked: Subscribe to unlock full features.")
        with st.expander("Unlock (PayPal)", expanded=True):
            gate_paypal_ui()
        st.stop()

    # After unlock, require email once
    require_email_capture()

    # Sidebar inputs only show when unlocked (keeps Home clean)
    st.sidebar.header("Global settings")
    curve_model = st.sidebar.selectbox("Curve model", ["Quadratic", "Piecewise-linear"], index=0)

    st.sidebar.subheader("Geometry & pressure inputs")
    rod_mm = st.sidebar.number_input("Rod diameter (mm) – adjuster area proxy", min_value=1.0, value=10.0, step=0.5)
    body_mm = st.sidebar.number_input("Body / piston diameter (mm) – main area", min_value=5.0, value=46.0, step=0.5)
    vref = st.sidebar.number_input("Velocity reference (m/s)", min_value=0.01, value=1.0, step=0.05)

    st.sidebar.subheader("Adjuster authority target band")
    adj_low = st.sidebar.number_input("Lower bound (fraction)", min_value=0.0, max_value=1.0, value=0.15, step=0.01)
    adj_high = st.sidebar.number_input("Upper bound (fraction)", min_value=0.0, max_value=1.0, value=0.20, step=0.01)

    st.sidebar.subheader("Damping target (ζ method)")
    zeta = st.sidebar.number_input("Damping ratio ζ", min_value=0.0, max_value=2.0, value=0.30, step=0.05)
    spring_rate = st.sidebar.number_input("Spring rate (N/mm)", min_value=0.0, value=60.0, step=1.0)
    mass_kg = st.sidebar.number_input("Effective mass (kg)", min_value=0.0, value=75.0, step=1.0)

    st.sidebar.subheader("Velocity grid")
    v_max = st.sidebar.number_input("Max velocity (m/s)", min_value=0.5, value=3.0, step=0.5)
    v_step = st.sidebar.number_input("Step (m/s)", min_value=0.01, value=0.1, step=0.01)

    # Areas for pressure calc
    a_rod = area_mm2(rod_mm)
    a_body = area_mm2(body_mm)

    st.markdown("## Premium Tools")
    st.caption("Unlocked calculators: Compression / Rebound / Compare / Export")

    tabs = st.tabs(["Compression", "Rebound", "Compare", "Export"])

    default_comp = [(0.1, 300.0, 1400.0), (1.0, 800.0, 2600.0), (2.5, 1400.0, 4000.0)]
    default_reb = [(0.1, 250.0, 1200.0), (1.0, 700.0, 2400.0), (2.5, 1200.0, 3600.0)]

    with tabs[0]:
        st.subheader("Compression")
        adj_pts_c, full_pts_c = input_3point("comp", default_comp)

        pct = adjuster_authority_percent(vref, adj_pts_c, full_pts_c)
        st.metric("Adjuster Authority % (at vref)", f"{pct:.1f}%")
        st.caption(f"Target band: {adj_low*100:.0f}%–{adj_high*100:.0f}%")
        if adj_low * 100 <= pct <= adj_high * 100:
            st.success("Within target band ✅")
        else:
            st.warning("Outside target band ⚠️")

        # Pressure estimates at vref
        adj_force = interp_force(vref, adj_pts_c)
        full_force = interp_force(vref, full_pts_c)
        p_adj = pressure_bar(adj_force, a_rod)
        p_full = pressure_bar(full_force, a_body)
        st.write(
            f"**Pressure estimates at vref:**  Adjuster proxy ≈ **{p_adj:.2f} bar**,  Main ≈ **{p_full:.2f} bar**  "
            f"(Force ÷ Area)"
        )

        df_c = compute_table(adj_pts_c, full_pts_c, "Compression", zeta, spring_rate, mass_kg, v_max, v_step)
        st.line_chart(df_c.set_index("Velocity (m/s)")[["Adj-only (N)", "Full (N)", "ζ target F (N)"]])
        st.dataframe(df_c, use_container_width=True)

    with tabs[1]:
        st.subheader("Rebound")
        adj_pts_r, full_pts_r = input_3point("reb", default_reb)

        pct = adjuster_authority_percent(vref, adj_pts_r, full_pts_r)
        st.metric("Adjuster Authority % (at vref)", f"{pct:.1f}%")
        st.caption(f"Target band: {adj_low*100:.0f}%–{adj_high*100:.0f}%")
        if adj_low * 100 <= pct <= adj_high * 100:
            st.success("Within target band ✅")
        else:
            st.warning("Outside target band ⚠️")

        adj_force = interp_force(vref, adj_pts_r)
        full_force = interp_force(vref, full_pts_r)
        p_adj = pressure_bar(adj_force, a_rod)
        p_full = pressure_bar(full_force, a_body)
        st.write(
            f"**Pressure estimates at vref:**  Adjuster proxy ≈ **{p_adj:.2f} bar**,  Main ≈ **{p_full:.2f} bar**"
        )

        df_r = compute_table(adj_pts_r, full_pts_r, "Rebound", zeta, spring_rate, mass_kg, v_max, v_step)
        st.line_chart(df_r.set_index("Velocity (m/s)")[["Adj-only (N)", "Full (N)", "ζ target F (N)"]])
        st.dataframe(df_r, use_container_width=True)

    with tabs[2]:
        st.subheader("Compare (Compression vs Rebound)")

        # Rebuild from stored widget states (so it works even if user hasn't visited both tabs)
        adj_pts_c = [
            (st.session_state.get("comp_v1", 0.1), st.session_state.get("comp_a1", 300.0)),
            (st.session_state.get("comp_v2", 1.0), st.session_state.get("comp_a2", 800.0)),
            (st.session_state.get("comp_v3", 2.5), st.session_state.get("comp_a3", 1400.0)),
        ]
        full_pts_c = [
            (st.session_state.get("comp_v1", 0.1), st.session_state.get("comp_f1", 1400.0)),
            (st.session_state.get("comp_v2", 1.0), st.session_state.get("comp_f2", 2600.0)),
            (st.session_state.get("comp_v3", 2.5), st.session_state.get("comp_f3", 4000.0)),
        ]

        adj_pts_r = [
            (st.session_state.get("reb_v1", 0.1), st.session_state.get("reb_a1", 250.0)),
            (st.session_state.get("reb_v2", 1.0), st.session_state.get("reb_a2", 700.0)),
            (st.session_state.get("reb_v3", 2.5), st.session_state.get("reb_a3", 1200.0)),
        ]
        full_pts_r = [
            (st.session_state.get("reb_v1", 0.1), st.session_state.get("reb_f1", 1200.0)),
            (st.session_state.get("reb_v2", 1.0), st.session_state.get("reb_f2", 2400.0)),
            (st.session_state.get("reb_v3", 2.5), st.session_state.get("reb_f3", 3600.0)),
        ]

        df_c = compute_table(adj_pts_c, full_pts_c, "Compression", zeta, spring_rate, mass_kg, v_max, v_step)
        df_r = compute_table(adj_pts_r, full_pts_r, "Rebound", zeta, spring_rate, mass_kg, v_max, v_step)
        df = pd.concat([df_c, df_r], ignore_index=True)

        st.line_chart(df.pivot(index="Velocity (m/s)", columns="Mode", values="Adj %"))
        st.dataframe(df, use_container_width=True)

    with tabs[3]:
        st.subheader("Export")
        # Export combined table
        adj_pts_c = [
            (st.session_state.get("comp_v1", 0.1), st.session_state.get("comp_a1", 300.0)),
            (st.session_state.get("comp_v2", 1.0), st.session_state.get("comp_a2", 800.0)),
            (st.session_state.get("comp_v3", 2.5), st.session_state.get("comp_a3", 1400.0)),
        ]
        full_pts_c = [
            (st.session_state.get("comp_v1", 0.1), st.session_state.get("comp_f1", 1400.0)),
            (st.session_state.get("comp_v2", 1.0), st.session_state.get("comp_f2", 2600.0)),
            (st.session_state.get("comp_v3", 2.5), st.session_state.get("comp_f3", 4000.0)),
        ]
        adj_pts_r = [
            (st.session_state.get("reb_v1", 0.1), st.session_state.get("reb_a1", 250.0)),
            (st.session_state.get("reb_v2", 1.0), st.session_state.get("reb_a2", 700.0)),
            (st.session_state.get("reb_v3", 2.5), st.session_state.get("reb_a3", 1200.0)),
        ]
        full_pts_r = [
            (st.session_state.get("reb_v1", 0.1), st.session_state.get("reb_f1", 1200.0)),
            (st.session_state.get("reb_v2", 1.0), st.session_state.get("reb_f2", 2400.0)),
            (st.session_state.get("reb_v3", 2.5), st.session_state.get("reb_f3", 3600.0)),
        ]

        df = pd.concat(
            [
                compute_table(adj_pts_c, full_pts_c, "Compression", zeta, spring_rate, mass_kg, v_max, v_step),
                compute_table(adj_pts_r, full_pts_r, "Rebound", zeta, spring_rate, mass_kg, v_max, v_step),
            ],
            ignore_index=True,
        )

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name="pressure_balance_export.csv",
            mime="text/csv",
        )


# ============================================================
# App entry
# ============================================================
show_branding()

# Determine page (sidebar + query param)
qp = get_query_params()
qp_page = (qp.get("page", "") or "").strip().lower()

if "page" not in st.session_state:
    if qp_page in ("terms", "privacy", "tools", "home"):
        st.session_state["page"] = qp_page.title()
    else:
        st.session_state["page"] = "Home"

st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Home", "Tools", "Terms", "Privacy"], index=["Home", "Tools", "Terms", "Privacy"].index(st.session_state["page"]))
st.session_state["page"] = page
set_query_params(page=page.lower())

# Render selected page
if page == "Home":
    render_home()
elif page == "Tools":
    render_tools()
elif page == "Terms":
    render_terms()
elif page == "Privacy":
    render_privacy()

footer() 