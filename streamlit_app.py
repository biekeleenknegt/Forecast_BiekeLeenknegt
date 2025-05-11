import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Project Cost Estimator", layout="centered")
st.title("Project Cost Estimator")

USERNAME = "test"
PASSWORD = "test"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    with st.form("login_form"):
        st.subheader("Login required")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login = st.form_submit_button("Login")
        if login:
            if username == USERNAME and password == PASSWORD:
                st.session_state.authenticated = True
                st.success("Login successful. Please press login again.")
                st.stop()
            else:
                st.error("Invalid credentials. Please try again.")
    st.stop()

# ---------------- DATABASE ----------------
CSV_PATH = "database.csv"
if os.path.exists(CSV_PATH):
    # Inlezen (standaard komma-separator, punt-decimalen)
    df = pd.read_csv(CSV_PATH, sep=",", decimal=".")
    # Migratie: als kolom ontbreekt, toevoegen met default 0
    if "vaults" not in df.columns:
        df["vaults"] = 0
    if "loading_bay" not in df.columns:
        df["loading_bay"] = 0
    # Zorg dat numerieke velden écht numeriek zijn
    for col in [
        "surface","price","price_per_m2",
        "exterior_surface","exterior_price","exterior_price_per_m2","year"
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
else:
    df = pd.DataFrame(columns=[
        "name", "vaults", "loading_bay", "surface", "price", "price_per_m2",
        "exterior_surface", "exterior_price", "exterior_price_per_m2", "year"
    ])

# ---------------- NAVIGATION ----------------
page = st.sidebar.radio("Navigation", [
    "Forecast price", "Add new project", "View and modify projects", "About this tool"
])

# ---------------- 1. FORECAST ----------------
if page == "Forecast price":
    st.header("Forecast Project Price")
    st.markdown("""
    This tool estimates both building cost and exterior works separately, with adjustments for time-based inflation.
    """)

    # Checkboxes als booleans, omzetten naar 0/1
    vaults_req   = st.checkbox("Are vaults required?")
    loading_req  = st.checkbox("Is a loading bay required?")
    vault_val    = 1 if vaults_req else 0
    load_val     = 1 if loading_req else 0

    input_surface    = st.number_input("Expected building surface (m²)", min_value=1)
    exterior_surface = st.number_input("Expected exterior surface (m²)", min_value=0)
    forecast_year    = st.number_input(
        "Planned project year", min_value=2020, max_value=2100,
        value=datetime.now().year
    )

    # Filter op exact 0/1
    filtered = df[
        (df["vaults"] == vault_val) &
        (df["loading_bay"] == load_val)
    ]

    if not filtered.empty:
        # Inflatie-correctie
        def correct(row):
            return 1.023 ** (forecast_year - row["year"])

        filtered["corrected_price_per_m2"] = (
            filtered["price_per_m2"] * filtered.apply(correct, axis=1)
        )
        filtered["corrected_exterior_price_per_m2"] = (
            filtered["exterior_price_per_m2"] * filtered.apply(correct, axis=1)
        )

        # Building cost = gemiddelde * oppervlakte
        avg_ppm2     = filtered["corrected_price_per_m2"].mean()
        est_building = avg_ppm2 * input_surface

        st.info(f"{filtered.shape[0]} matching projects found.")
        st.write(f"Corrected avg price per m²: **€{avg_ppm2:,.2f}**")
        st.success(f"Estimated building cost: **€{est_building:,.2f}**")

        # Exterior cost = range * oppervlakte
        st.subheader("Exterior works estimate")
        ex = filtered["corrected_exterior_price_per_m2"].dropna()
        if not ex.empty and exterior_surface > 0:
            mn, mx = ex.min(), ex.max()
            st.write(
                f"Estimated exterior cost range: **€{mn*exterior_surface:,.2f} – "
                f"€{mx*exterior_surface:,.2f}**"
            )
            st.write(f"Based on corrected €/m² from **€{mn:.2f}** to **€{mx:.2f}**")
        elif exterior_surface > 0:
            st.warning("No exterior pricing data available.")
        else:
            st.info("Enter an exterior surface to see a cost range.")
    else:
        st.warning("No matching projects found in the database yet.")

# ---------------- 2. ADD PROJECT ----------------
elif page == "Add new project":
    st.header("Add New Project")
    with st.form("add_form"):
        name         = st.text_input("Project name")
        vaults_pres  = 1 if st.checkbox("Are vaults present?") else 0
        load_pres    = 1 if st.checkbox("Is a loading bay present?") else 0
        surface      = st.number_input("Building surface (m²)", min_value=1)
        price        = st.number_input("Total sale price (€)", min_value=1)
        ext_surf     = st.number_input("Exterior surface (m²)", min_value=0)
        ext_price    = st.number_input("Total exterior price (€)", min_value=0)
        year         = st.number_input(
            "Year of construction",
            min_value=2000, max_value=datetime.now().year,
            value=datetime.now().year
        )

        submit = st.form_submit_button("Submit project")
        if submit:
            if name:
                price_ppm2    = price / surface
                ext_ppm2      = ext_price / ext_surf if ext_surf > 0 else None
                new_row       = {
                    "name": name,
                    "vaults": vaults_pres,
                    "loading_bay": load_pres,
                    "surface": surface,
                    "price": price,
                    "price_per_m2": price_ppm2,
                    "exterior_surface": ext_surf,
                    "exterior_price": ext_price,
                    "exterior_price_per_m2": ext_ppm2,
                    "year": year
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df.to_csv(CSV_PATH, index=False)
                st.success("Project successfully added.")
            else:
                st.error("Please fill out all required fields.")

# ---------------- 3. VIEW / MODIFY ----------------
elif page == "View and modify projects":
    st.header("Project Database")
    if df.empty:
        st.warning("No projects in the database.")
    else:
        st.dataframe(df)
        st.subheader("Modify or delete a project")
        idx = st.number_input("Select row index", min_value=0, max_value=len(df)-1)
        st.write(df.iloc[idx])

        new_price     = st.number_input(
            "New building price (€)",
            min_value=1,
            value=int(df.at[idx, "price"])
        )
        new_ext_price = st.number_input(
            "New exterior price (€)",
            min_value=0,
            value=int(df.at[idx, "exterior_price"] or 0)
        )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Update price"):
                df.at[idx, "price"] = new_price
                df.at[idx, "price_per_m2"] = new_price / df.at[idx, "surface"]
                df.at[idx, "exterior_price"] = new_ext_price
                if df.at[idx, "exterior_surface"] > 0:
                    df.at[idx, "exterior_price_per_m2"] = new_ext_price / df.at[idx, "exterior_surface"]
                df.to_csv(CSV_PATH, index=False)
                st.success("Price updated.")
        with c2:
            if st.button("Delete project"):
                df = df.drop(index=idx).reset_index(drop=True)
                df.to_csv(CSV_PATH, index=False)
                st.success("Project deleted.")

# ---------------- 4. ABOUT TOOL ----------------
elif page == "About this tool":
    st.header("About this Tool")
    st.markdown("""
    This web tool helps estimate construction project prices using a simplified Reference Class Forecasting (RCF) method.

    **Key Features:**
    - Predicts total building price based on historical averages of similar projects (based on vaults and loading bay requirements).
    - Separates **building** and **exterior works** cost estimation.
    - Exterior cost is shown as a price range based on the minimum and maximum €/m² in the database.
    - Building cost is based on the average €/m².
    - Includes a time correction factor: **2.3% yearly price increase** is assumed.
    - Projects from earlier years are adjusted upwards to match the selected forecast year.
    - Users can view, modify or delete projects.
    - Built using **Streamlit** with a CSV-based backend.
    """)
