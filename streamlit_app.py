import streamlit as st
import pandas as pd
import os
from datetime import datetime
from scipy.stats import shapiro, norm

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Project Cost Estimator", layout="centered")
st.title("Project Cost Estimator")

USERS = {
    "test": "test",
    "mario": "WachtwoordMario!",
    "tom": "WachtwoordTom!"
}


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    with st.form("login_form"):
        st.subheader("Login required")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login = st.form_submit_button("Login")
        if login:
            if username in USERS and password == USERS[username]:
                st.session_state.authenticated = True
                st.success("Login successful. Please press login again.")
                st.stop()
            else:
                st.error("Invalid credentials. Please try again.")
    st.stop()

# ---------------- DATABASE ----------------
CSV_PATH = "database.csv"
if os.path.exists(CSV_PATH):
    df = pd.read_csv(CSV_PATH, sep=",", decimal=".")
    if "vaults" not in df.columns:
        df["vaults"] = 0
    if "loading_bay" not in df.columns:
        df["loading_bay"] = 0
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
    Additionally, performs normality test and computes prediction intervals accordingly.
    """)

    vaults_req  = st.checkbox("Are vaults required?")
    loading_req = st.checkbox("Is a loading bay required?")
    vault_val   = 1 if vaults_req else 0
    load_val    = 1 if loading_req else 0

    input_surface    = st.number_input("Expected building surface (m²)", min_value=1)
    exterior_surface = st.number_input("Expected exterior surface (m²)", min_value=0)
    forecast_year    = st.number_input(
        "Planned project year", min_value=1900, max_value=2100,
        value=datetime.now().year
    )

    filtered = df[(df["vaults"] == vault_val) & (df["loading_bay"] == load_val)]

    if not filtered.empty:
        def correct(row):
            return 1.023 ** (forecast_year - row["year"])

        filtered["corr_ppm2"] = filtered["price_per_m2"] * filtered.apply(correct, axis=1)
        filtered["corr_ext_ppm2"] = filtered["exterior_price_per_m2"] * filtered.apply(correct, axis=1)

        est_build_ppm2 = filtered["corr_ppm2"].dropna()
        mean_ppm2 = est_build_ppm2.mean()
        est_build = mean_ppm2 * input_surface

        st.info(f"{filtered.shape[0]} matching projects found.")
        st.write(f"Corrected avg price per m²: **€{mean_ppm2:,.2f}**")
        st.success(f"Estimated building cost: **€{est_build:,.2f}**")

        st.subheader("Building price interval (normality test)")

        if len(est_build_ppm2) < 4:
            st.warning(
               f"Only {len(est_build_ppm2)} valid price points found for this reference class. "
               "The average price and estimate are shown below, but they are not statistically representative. "
                  "Use with caution! Ideally, at least 4 projects are required to ensure a robust average."
            )

        else:
            try:
                stat, p = shapiro(est_build_ppm2)
                st.write(f"Shapiro–Wilk p-value: {p:.3f}")
                if p > 0.05:
                    # assume normal, z-interval
                    z = norm.ppf(0.975)
                    sd = est_build_ppm2.std(ddof=1)
                    se = sd / (len(est_build_ppm2) ** 0.5)
                    low = mean_ppm2 - z * se
                    high = mean_ppm2 + z * se
                    st.write(f"95% prediction interval (±1.96 SE): €/m² [{low:,.2f} – {high:,.2f}] (normal)")
                else:
                    # quantile interval
                    q_low, q_high = est_build_ppm2.quantile([0.025, 0.975])
                    st.write(f"95% prediction interval (quantiles): €/m² [{q_low:,.2f} – {q_high:,.2f}] (non-normal)")
            except ValueError:
                st.error(
                    "Er is een onverwacht probleem opgetreden bij het berekenen van het interval. "
                    "Controleer of de gegevens correct zijn ingevoerd."
                )

        st.subheader("Exterior works estimate")
        ex = filtered["corr_ext_ppm2"].dropna()
        ex = ex[ex > 0]
        if not ex.empty and exterior_surface > 0:
            mn, mx = ex.min(), ex.max()
            st.write(
                f"Estimated exterior cost range: **€{mn * exterior_surface:,.2f} – €{mx * exterior_surface:,.2f}**"
            )
            st.write(f"Based on corrected €/m² from **€{mn:,.2f}** to **€{mx:,.2f}**")

            # totaal
            total_min = est_build + mn * exterior_surface
            total_max = est_build + mx * exterior_surface
            st.subheader("Total project cost estimate")
            st.write(
                f"Estimated total cost range: **€{total_min:,.2f} – €{total_max:,.2f}**"
            )
        elif exterior_surface > 0:
            st.warning("No positive exterior pricing data available.")
        else:
            st.info("Enter an exterior surface to see a cost range.")
    else:
        st.warning("No matching projects found in the database yet.")

# ---------------- 2. ADD PROJECT ----------------
elif page == "Add new project":
    st.header("Add New Project")
    with st.form("add_form"):
        name        = st.text_input("Project name")
        vaults_pres = 1 if st.checkbox("Are vaults present?") else 0
        load_pres   = 1 if st.checkbox("Is a loading bay present?") else 0
        surface     = st.number_input("Building surface (m²)", min_value=1)
        price       = st.number_input("Total sale price (€)", min_value=1)
        ext_surf    = st.number_input("Exterior surface (m²)", min_value=0)
        ext_price   = st.number_input("Total exterior price (€)", min_value=0)
        year        = st.number_input(
            "Year of construction",
            min_value=2000, max_value=datetime.now().year,
            value=datetime.now().year
        )

        submit = st.form_submit_button("Submit project")
        if submit:
            if name:
                ppm2 = price / surface
                ext_ppm2 = ext_price / ext_surf if ext_surf > 0 else None
                new = pd.DataFrame([{
                    "name": name,
                    "vaults": vaults_pres,
                    "loading_bay": load_pres,
                    "surface": surface,
                    "price": price,
                    "price_per_m2": ppm2,
                    "exterior_surface": ext_surf,
                    "exterior_price": ext_price,
                    "exterior_price_per_m2": ext_ppm2,
                    "year": year
                }])
                df = pd.concat([df, new], ignore_index=True)
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
                    df.at[idx, "exterior_price_per_m2"] = (
                        new_ext_price / df.at[idx, "exterior_surface"]
                    )
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
    This interactive application was developed by **Bieke Leenknegt** as part of her Master’s thesis titled  
    _“Reference Class Forecasting for Construction Pricing: A Data-Driven Framework for Transparent, Scalable, and Real-Time Project Estimates”_ (2025).

    It operationalises the principles of Reference Class Forecasting (RCF) into a transparent, updatable and user-friendly cost prediction tool for construction projects.

    ### Purpose and Functionality

    The tool offers real-time forecasts of total construction costs for new projects, based on similarity to previously completed buildings.  
    Instead of relying on traditional regression models, the tool applies RCF: historical projects are grouped into reference classes based on two binary indicators — the presence of **vaults** and a **loading bay** — shown to significantly stratify pricing.

    The application consists of three functional pages:

    - **Forecast price**  
      Users input project characteristics, surface areas, and a target forecast year.  
      The tool filters the reference dataset for similar projects and applies a **2.7% annual inflation adjustment** to bring all €/m² values in line with the selected year.  
      Output includes:
        - Number of matching reference projects  
        - Average corrected €/m² and total building cost  
        - A 95% confidence interval for unit price  
        - A min–max range for exterior works (if applicable)

    - **Add new project**  
      This page allows users to submit completed projects. The system stores inputs such as surface, total cost, exterior values, and construction year.  
      Derived metrics like €/m² are calculated automatically and added to the database.

    - **View and modify projects**  
      Provides access to the full historical dataset, with tools to review, edit, or delete records.

    ### Methodology

    - **Reference Class Definition**  
      Classes are defined using the binary presence of vaults and loading bays, forming four distinct groups for comparison.

    - **Time Adjustment**  
      All historical prices were already corrected in advance to reflect their expected position on a linear 2.7% growth trend between 2015 and 2025.  
      This removed temporary inflation shocks (e.g., 2022–2024) and established a clean baseline.  
      From this baseline, a 2.7% compound annual growth rate is applied to bring prices to the user’s forecast year.

    - **Confidence Intervals**  
      A Shapiro–Wilk test checks for normality of the €/m² distribution in the selected class:  
        - If normal: a z-based confidence interval is shown.  
        - If non-normal: a 2.5%–97.5% quantile range is used instead.

    - **Exterior Works**  
      Exterior prices are processed separately. If available, a min–max €/m² range is calculated and scaled to the user’s exterior surface input.

    ### Technical Stack

    This tool was fully developed in **Python**, using the **Streamlit** web framework with **Pandas** and **SciPy** for data processing and statistical logic.  
    All data is stored in a local `.csv` file, allowing easy extension and full transparency.
    """)
