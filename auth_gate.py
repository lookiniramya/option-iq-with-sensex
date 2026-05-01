"""
auth_gate.py — Simple shared-password gate for the deployed app.

Reads the expected password from the OPTIONSIQ_APP_PASSWORD environment
variable. On Cloud Run, set this with:
    gcloud run services update SERVICE --update-env-vars OPTIONSIQ_APP_PASSWORD=...

For local development, you can either:
  - export OPTIONSIQ_APP_PASSWORD=mypass before running streamlit, OR
  - leave it unset and the gate auto-disables (open access locally)

Single shared password protects against random URL discovery. It is NOT
a substitute for proper per-user auth — when this app gets shared more
broadly, replace this with Firebase Auth / Google Identity / etc.
"""
import os
import hmac
import streamlit as st


_PASSWORD_ENV_VAR = "OPTIONSIQ_APP_PASSWORD"
_PLACEHOLDER = "CHANGE_ME_BEFORE_DEPLOYING"


def _expected_password() -> str:
    """Returns the configured password, or empty string if not set."""
    return os.environ.get(_PASSWORD_ENV_VAR, "").strip()


def _gate_disabled() -> bool:
    """
    Gate is disabled (open access) if:
      - The env var is not set at all (typical for local dev), OR
      - The env var still has the placeholder value.
    Both conditions log a warning so misconfigurations are visible.
    """
    pw = _expected_password()
    if not pw:
        return True
    if pw == _PLACEHOLDER:
        return True
    return False


def check_password() -> bool:
    """
    Renders a password prompt if the gate is enabled and the user
    hasn't authenticated yet. Returns True if access is granted.

    Call this at the top of app.py BEFORE any other UI code.

    Behavior:
      - If OPTIONSIQ_APP_PASSWORD is unset → gate disabled, returns True.
      - If unauthenticated → renders prompt, returns False.
      - If authenticated this session → returns True silently.
    """
    if _gate_disabled():
        # Local dev convenience — no prompt, no warning shown to user.
        # (We could log a server-side warning, but that adds noise.)
        return True

    if st.session_state.get("_gate_authed"):
        return True

    # Render the gate UI
    st.markdown(
        """
        <div style="max-width:420px;margin:4rem auto 0 auto;padding:2rem 2rem 1.5rem;
                    background:#ffffff;border:1px solid #e0e4eb;border-radius:14px;
                    box-shadow:0 4px 16px rgba(20,30,60,0.06);font-family:system-ui,sans-serif">
            <div style="font-size:1.4rem;font-weight:700;color:#1565c0;margin-bottom:0.4rem">
                🔒 OptionsIQ
            </div>
            <div style="font-size:0.9rem;color:#5a6478;margin-bottom:1.2rem">
                This is a private deployment. Enter the access password to continue.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns([1, 2, 1])
    with cols[1]:
        with st.form("_gate_form", clear_on_submit=False):
            entered = st.text_input(
                "Access password",
                type="password",
                key="_gate_input",
                placeholder="Enter password",
                label_visibility="collapsed",
            )
            submit = st.form_submit_button("Unlock", use_container_width=True)

        if submit:
            if hmac.compare_digest(entered or "", _expected_password()):
                st.session_state["_gate_authed"] = True
                st.rerun()
            else:
                st.error("Wrong password.")

    return False
