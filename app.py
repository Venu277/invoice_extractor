import pandas as pd
import streamlit as st

import database as db
from processing import process_pdf
from report import build_report, month_label

st.set_page_config(page_title="Invoice Data Extractor", page_icon="🧾", layout="wide")
db.init_db()

# ---------- session defaults ----------
st.session_state.setdefault("user", None)          # logged-in user (dict) or None
st.session_state.setdefault("pending", [])         # extracted but not yet saved invoices
st.session_state.setdefault("uploader_key", 0)     # changing this key clears the file uploader
st.session_state.setdefault("report", None)        # last generated PDF report
st.session_state.setdefault("flash", None)         # one-time success message

MENU = ["Dashboard", "Upload Invoices", "My Invoices", "Monthly Report"]


# ---------- small helpers ----------
def money(x):
    return f"Rs. {x:,.2f}"


def month_options(df):
    return sorted(df["month"].dropna().unique(), reverse=True) if not df.empty else []


def colour_rows(column):
    """Green row when `column` == 'OK', red otherwise."""
    def apply(row):
        colour = "#d4edda" if row[column] == "OK" else "#f8d7da"
        return [f"background-color: {colour}; color: black"] * len(row)
    return apply


NUMBER_FORMAT = {"subtotal": "{:,.2f}", "cgst": "{:,.2f}", "sgst": "{:,.2f}",
                 "igst": "{:,.2f}", "gst_amount": "{:,.2f}", "total": "{:,.2f}"}


# =====================================================================
# HOME PAGE (login / sign up)
# =====================================================================
def home_page():
    st.title("🧾 Invoice Data Extractor")
    st.subheader("Turn invoice PDFs into clean, validated accounting data.")

    c1, c2, c3 = st.columns(3)
    c1.markdown("**1. Upload**\n\nAdd your invoice PDFs. Scanned invoices work too.")
    c2.markdown("**2. Check**\n\nVendor, date, GSTIN, amounts and GST rules are extracted and verified.")
    c3.markdown("**3. Report**\n\nSee your dashboard and download a monthly PDF summary.")
    st.divider()

    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        tab_login, tab_signup = st.tabs(["Log in", "Sign up"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log in", type="primary")
            if submitted:
                user = db.authenticate(email, password)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Incorrect email or password.")

        with tab_signup:
            with st.form("signup_form"):
                business = st.text_input("Business name")
                email_new = st.text_input("Email", key="signup_email")
                pw1 = st.text_input("Password (at least 6 characters)", type="password",
                                    key="signup_pw1")
                pw2 = st.text_input("Confirm password", type="password", key="signup_pw2")
                created = st.form_submit_button("Create account", type="primary")
            if created:
                if pw1 != pw2:
                    st.error("The two passwords do not match.")
                else:
                    ok, message = db.create_user(business, email_new, pw1)
                    if ok:
                        st.session_state.user = db.authenticate(email_new, pw1)
                        st.rerun()
                    else:
                        st.error(message)


# =====================================================================
# SIDEBAR
# =====================================================================
def sidebar(user):
    st.sidebar.title("🧾 Invoice Extractor")
    st.sidebar.caption(user["business_name"])
    page = st.sidebar.radio("Menu", MENU)
    st.sidebar.divider()
    if st.sidebar.button("Log out"):
        st.session_state.user = None
        st.session_state.pending = []
        st.session_state.report = None
        st.session_state.flash = None
        st.rerun()
    return page


# =====================================================================
# DASHBOARD
# =====================================================================
def dashboard_page(user):
    st.title("Dashboard")
    df = db.get_invoices(user["id"])
    if df.empty:
        st.info("You have no invoices yet. Open **Upload Invoices** in the menu to add your first ones.")
        return

    choice = st.selectbox("Period", ["All time"] + month_options(df),
                          format_func=lambda m: m if m == "All time" else month_label(m))
    view = df if choice == "All time" else df[df["month"] == choice]

    attention = view[view["status"] != "OK"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Invoices", len(view))
    c2.metric("Total value", money(pd.to_numeric(view["total"]).sum()))
    c3.metric("Total GST", money(pd.to_numeric(view["gst_amount"]).sum()))
    c4.metric("Need attention", len(attention))

    left, right = st.columns(2)
    with left:
        st.subheader("Value by month")
        by_month = (df.dropna(subset=["month"]).assign(total=pd.to_numeric(df["total"]))
                      .groupby("month")["total"].sum())
        if by_month.empty:
            st.caption("No dated invoices yet.")
        else:
            st.bar_chart(by_month)
    with right:
        st.subheader("Top vendors")
        by_vendor = (view.dropna(subset=["vendor"]).assign(total=pd.to_numeric(view["total"]))
                         .groupby("vendor")["total"].sum().nlargest(5))
        if by_vendor.empty:
            st.caption("No vendor data yet.")
        else:
            st.bar_chart(by_vendor)

    st.subheader("Needs attention")
    if attention.empty:
        st.success("All invoices in this period passed validation.")
    else:
        st.dataframe(attention[["date", "invoice_no", "vendor", "status"]], hide_index=True)
        st.caption("Check these in **My Invoices**. Delete wrong ones and upload corrected invoices.")


# =====================================================================
# UPLOAD
# =====================================================================
def upload_page(user):
    st.title("Upload Invoices")
    st.write("Add invoice PDFs, review what was extracted, then save to your records.")

    files = st.file_uploader("Invoice PDFs", type=["pdf"], accept_multiple_files=True,
                             key=f"uploader_{st.session_state.uploader_key}")

    if files and st.button("Extract data", type="primary"):
        results = []
        with st.spinner("Reading invoices..."):
            for f in files:
                row, readable = process_pdf(f.name, f.getvalue())
                row["_readable"] = readable
                results.append(row)
        st.session_state.pending = results

    pending = st.session_state.pending
    if not pending:
        return

    # mark duplicates (already saved earlier, or repeated inside this batch)
    known = db.existing_keys(user["id"])
    seen = set()
    for row in pending:
        key = db.duplicate_key(row.get("vendor"), row.get("invoice_no"))
        row["_dup"] = bool(key) and (key in known or key in seen)
        if key:
            seen.add(key)

    def result_text(row):
        if not row["_readable"]:
            return row["status"]
        if row["_dup"]:
            return "Duplicate - will be skipped"
        return row["status"]

    preview = pd.DataFrame([{"file": r["file"], "vendor": r["vendor"],
                             "invoice_no": r["invoice_no"], "date": r["date"],
                             "total": r["total"], "result": result_text(r)} for r in pending])

    st.subheader("Review")
    st.dataframe(preview.style.apply(colour_rows("result"), axis=1)
                        .format({"total": "{:,.2f}"}, na_rep="-"), hide_index=True)

    ready = [r for r in pending if r["_readable"] and not r["_dup"]]
    st.write(f"**{len(ready)}** invoice(s) ready to save.")
    st.caption("Invoices with issues are still saved and shown under 'Needs attention'. "
               "Unreadable files and duplicates are skipped.")

    save_col, discard_col, _ = st.columns([1, 1, 4])
    if save_col.button("Save to my records", type="primary", disabled=not ready):
        saved, skipped = db.save_invoices(user["id"], ready)
        st.session_state.pending = []
        st.session_state.uploader_key += 1
        st.session_state.report = None
        st.session_state.flash = f"Saved {saved} invoice(s)." + (
            f" Skipped {skipped} duplicate(s)." if skipped else "")
        st.rerun()
    if discard_col.button("Discard"):
        st.session_state.pending = []
        st.session_state.uploader_key += 1
        st.rerun()


# =====================================================================
# MY INVOICES
# =====================================================================
def invoices_page(user):
    st.title("My Invoices")
    df = db.get_invoices(user["id"])
    if df.empty:
        st.info("No invoices saved yet.")
        return

    f1, f2, f3 = st.columns(3)
    month = f1.selectbox("Month", ["All"] + month_options(df),
                         format_func=lambda m: m if m == "All" else month_label(m))
    status = f2.selectbox("Status", ["All", "Valid", "Needs attention"])
    vendor = f3.selectbox("Vendor", ["All"] + sorted(df["vendor"].dropna().unique()))

    view = df
    if month != "All":
        view = view[view["month"] == month]
    if status == "Valid":
        view = view[view["status"] == "OK"]
    elif status == "Needs attention":
        view = view[view["status"] != "OK"]
    if vendor != "All":
        view = view[view["vendor"] == vendor]

    if view.empty:
        st.warning("No invoices match these filters.")
        return

    shown = view[["date", "invoice_no", "vendor", "gstin", "subtotal", "cgst", "sgst",
                  "igst", "gst_amount", "total", "status"]]
    st.dataframe(shown.style.apply(colour_rows("status"), axis=1)
                      .format(NUMBER_FORMAT, na_rep="-"), hide_index=True)
    st.caption(f"{len(view)} invoice(s) shown.")

    st.download_button("Download as CSV", data=shown.to_csv(index=False).encode("utf-8"),
                       file_name="invoices.csv", mime="text/csv")

    with st.expander("Delete an invoice"):
        labels = {int(r["id"]): f"{r['invoice_no'] or 'No number'} | {r['vendor'] or 'Unknown'} | "
                                f"{r['date'] or 'No date'}" for _, r in view.iterrows()}
        chosen = st.selectbox("Choose the invoice to delete", list(labels),
                              format_func=lambda i: labels[i])
        if st.button("Delete selected invoice"):
            db.delete_invoice(user["id"], chosen)
            st.session_state.report = None
            st.session_state.flash = "Invoice deleted."
            st.rerun()


# =====================================================================
# MONTHLY REPORT
# =====================================================================
def report_page(user):
    st.title("Monthly Report")
    df = db.get_invoices(user["id"])
    months = month_options(df)
    if not months:
        st.info("Save some invoices with readable dates first, then come back here.")
        return

    month = st.selectbox("Select month", months, format_func=month_label)
    view = df[df["month"] == month]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Invoices", len(view))
    c2.metric("Total value", money(pd.to_numeric(view["total"]).sum()))
    c3.metric("Total GST", money(pd.to_numeric(view["gst_amount"]).sum()))
    c4.metric("Need attention", int((view["status"] != "OK").sum()))

    if st.button("Generate PDF report", type="primary"):
        pdf = build_report(user["business_name"], month, view)
        st.session_state.report = {"month": month, "pdf": pdf}

    report = st.session_state.report
    if report and report["month"] == month:
        st.success(f"Report for {month_label(month)} is ready.")
        st.download_button("Download PDF report", data=report["pdf"],
                           file_name=f"Monthly_Report_{month}.pdf", mime="application/pdf")
        st.caption("The file is saved to your computer's Downloads folder by your browser.")


# =====================================================================
# MAIN
# =====================================================================
user = st.session_state.user
if user is None:
    home_page()
else:
    page = sidebar(user)
    if st.session_state.flash:
        st.success(st.session_state.flash)
        st.session_state.flash = None

    if page == "Dashboard":
        dashboard_page(user)
    elif page == "Upload Invoices":
        upload_page(user)
    elif page == "My Invoices":
        invoices_page(user)
    else:
        report_page(user)