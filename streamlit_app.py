import streamlit as st
import pandas as pd
import os
from datetime import datetime
from scipy.stats import shapiro, norm

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

        # ---------------- AANGEPASTE CONTROLE OP MINIMALE DATAPUNTEN ----------------
        if len(est_build_ppm2) < 3:
            st.info(
                "At this moment, there are not enough projects available to "
                "calculate a reliable price range (minimum of 3 values required). "
                "Please try again once at least 3 comparable projects have been entered."
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
    **Welcome to the Project Cost Estimator.**  
    This interactive web application was developed by **Bieke Leenknegt** as part of her Master’s thesis (see _“Masterproef: Reference Class Forecasting for Construction Pricing”_ for full details).

    ### Purpose and Scope
    The Project Cost Estimator provides a data-driven, reference-class approach to forecasting total building and exterior works costs for new construction projects. Instead of relying on simple linear regression models, this tool implements **Reference Class Forecasting (RCF)**—a methodology shown to mitigate systematic biases in traditional cost estimates. Historical projects are grouped into classes based on two primary characteristics:
    1. **Vaults** (presence of underground or basement spaces),  
    2. **Loading Bay** (presence of a loading dock or ramp).

    By focusing on these two categorical indicators, the tool identifies the most comparable reference population and calculates an adjusted average price per square meter (€/m²) for both building and exterior work components.

    ### Methodology
    1. **Data Acquisition and Preprocessing**  
       - Historical project data (vaults indicator, loading bay indicator, built-up surface in m², total sale price, exterior surface in m², exterior price, and completion year) are stored in a CSV file.  
       - Each entry is converted to price per square meter (`price_per_m2`) and exterior price per square meter (`exterior_price_per_m2`), where applicable.  
       - Missing values (`NaN`) are automatically ignored in subsequent analyses.  

    2. **Time-Series Adjustment (Inflation Correction)**  
       - A constant annual inflation rate of **2.3 %** is assumed.  
       - For each historical record, the price is adjusted to the user’s selected forecast year via:  
         \[
           \text{Corrected €/m²} \;=\; (\text{Historic €/m²}) \times (1 + 0.023)^{(\text{Forecast Year} - \text{Historic Year})}.
         \]

    3. **Reference Class Selection**  
       - Upon specifying “vaults required?” and “loading bay required?” via checkboxes, the tool filters the historical dataset to those projects that exactly match the selected binary flags (0 = no, 1 = yes).  
       - If no matching records are found, an informative warning appears, and forecasting halts.

    4. **Point Estimate Calculation**  
       - The mean of the corrected prices per square meter (\(\bar{x}\)) is computed for the selected reference class.  
       - The **estimated total building cost** is then  
         \[
           \widehat{\text{Building Cost}} \;=\; \bar{x} \times (\text{User–specified Building Surface in m}^2).
         \]

    5. **Prediction Interval and Normality Test**  
       - To quantify uncertainty, the tool first tests for normality using the **Shapiro–Wilk test** on the corrected €/m² values.  
         - If the Shapiro–Wilk p-value ≥ 0.05, normality is assumed and a **95 % z-interval** is constructed:  
           \[
             \bar{x} \pm z_{0.975} \times \frac{s}{\sqrt{n}},
           \]  
           where \(s\) is the sample standard deviation and \(n\) is the number of observations in the reference class.  
         - If p-value < 0.05, data are treated as non-normal; a **95 % quantile interval** is computed using the empirical 2.5 % and 97.5 % percentiles of the corrected sample.  
       - In either case, the interval is displayed in €/m², allowing users to gauge the likely range of building‐cost outcomes.

    6. **Exterior Works Estimate**  
       - The tool separately considers exterior works by taking the corrected exterior price per square meter (\(€/m²\)) values for the same reference class.  
       - If at least one positive corrected exterior €/m² is available and the user has entered a nonzero exterior surface, a **min–max range** is shown:  
         \[
           \bigl[\min(\text{corr\_ext\_ppm2}) \times \text{Surface},\, \max(\text{corr\_ext\_ppm2}) \times \text{Surface}\bigr].
         \]  
       - This provides a conservative boundary for exterior costs when sample sizes are small or data exhibit high dispersion.

    7. **Continuous Database Growth**  
       - Under the **“Add New Project”** tab, users can submit new projects by specifying name, vaults flag, loading bay flag, building surface, total sale price, exterior surface, exterior price, and construction year.  
       - New entries are appended to the CSV file and immediately integrated into the forecasting engine.  
       - Over time, the reference classes become richer, improving the reliability of both point estimates and prediction intervals.

    ### Navigation Overview
    - **Forecast price**:  
      Enter whether vaults/loading bay are required, specify building and exterior surfaces, and choose a forecast year. The tool returns:  
      1. Number of matching historical projects;  
      2. Inflated average €/m² and estimated total building cost;  
      3. 95 % prediction interval (normal or quantile) for building cost;  
      4. Exterior cost range if exterior surface > 0.  
    - **Add new project**:  
      Submit details for a new reference-class project. The form automatically computes €/m² values and stores the record.  
    - **View and modify projects**:  
      View the entire project database in tabular form, modify existing prices (which updates €/m² on the fly), or delete records permanently.  
    - **About this tool**:  
      You are currently viewing this detailed academic overview. For full theoretical and empirical background, consult my Master’s thesis.

    ### Academic Context (Masterproef)
    This implementation is grounded in my Master’s thesis, “_Reference Class Forecasting for Construction Pricing: A Data-Driven Methodology to Mitigate Cost Overruns_” (Leenknegt, 2025). Key contributions of that research include:
    1. **Demonstrating the superiority of RCF** over ordinary least squares (OLS) regression in the context of industrial and residential building projects.  
    2. **Quantifying the effect of vaults and loading bays** on unit costs, showing that these binary variables significantly stratify reference classes.  
    3. **Empirical validation** of a constant 2.3 % annual inflation factor for construction costs in the relevant market.  
    4. **Statistical evaluation of normality** in corrected price distributions, guiding the choice between parametric and non-parametric interval estimation.  

    By leveraging open-source technologies (Python, Streamlit, Pandas, SciPy) and a continuously updatable CSV backend, this tool serves as a transparent, replicable framework for practitioners, researchers, and students who wish to apply reference-class forecasting in real-world project planning.  
    """)

