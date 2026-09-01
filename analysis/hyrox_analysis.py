import marimo

__generated_with = "0.23.4"
app = marimo.App(width="medium")


@app.cell
def _():
    return


@app.cell
def _():
    import marimo as mo
    from getpass import getpass
    import os
    import sqlalchemy

    return getpass, mo, os, sqlalchemy


@app.cell
def _(getpass, os):
    # UWAGA: poniżej podmień na nazwę swojego użytkownika
    user = "postgres.zmnrqzujsapssgoeitzb"

    # UWAGA: poniżej podmień na host swojej bazy danych
    host = "aws-1-eu-central-1.pooler.supabase.com"

    # UWAGA: tutaj nic nie zmieniaj, po uruchomieniu tej komórki trzeba będzie wkleić 
    # hasło do bazy danych i zatwierdzić ENTER
    password = os.environ.get("SUPABASE_PASSWORD", getpass("podaj hasło"))
    return host, password, user


@app.cell
def _(host, password, sqlalchemy, user):
    DATABASE_URL = f"postgresql+psycopg2://{user}:{password}@{host}:5432/postgres?sslmode=require"
    engine = sqlalchemy.create_engine(DATABASE_URL)
    return (engine,)


@app.cell
def _(mo):
    # ============================================================
    # PROJECT CONTEXT
    # ============================================================
    # HYROX is a fitness race format combining running with functional workout
    # stations such as SkiErg, sled push/pull, rowing, lunges and wall balls.
    # This analysis uses official HYROX race result data as the main source and
    # enriches it with Eurostat and Google Trends indicators.
    mo.md("""
    ## HYROX performance analysis - project context

    HYROX is a fitness race format combining repeated running sections with functional workout stations, including SkiErg, sled push/pull, rowing, lunges and wall balls.
        The main performance data comes from the official HYROX Results service: https://results.hyrox.com/.
        The analysis is enriched with external country-level indicators from Eurostat and Google Trends to explore the fitness-culture context.

    **Research question:** do selected European HYROX events differ in athlete pacing profiles and Pace Change, and can those differences be described using country-level fitness culture indicators?
    """)
    return


@app.cell
def _(mo):
    # ============================================================
    # ANALYSIS SCOPE PARAMETERS
    # ============================================================
    # These parameters make the analysis reproducible and easy to adjust.
    # The raw database can contain more events/categories than used in this report.
    # Here the report is limited to selected men's OPEN/PRO events in six countries.
    ANALYSIS_RACE_KEYWORDS = [
        "Warsaw",
        "Lisboa",
        "Barcelona",
        "London",
        "Paris",
        "Copenhagen",
    ]

    ANALYSIS_CATEGORY_TYPES = ["OPEN", "PRO"]

    mo.md(
        f"""
        ## Analysis scope

        The analysis is filtered to selected men's HYROX events hosted in: **{', '.join(ANALYSIS_RACE_KEYWORDS)}**.  \n        Included categories: **{', '.join(ANALYSIS_CATEGORY_TYPES)}**.  \n        The filtering is applied after loading data from the database and before feature engineering.
        """
    )
    return ANALYSIS_CATEGORY_TYPES, ANALYSIS_RACE_KEYWORDS


@app.cell
def _(ANALYSIS_CATEGORY_TYPES, ANALYSIS_RACE_KEYWORDS, engine):
    # ============================================================
    # DATA LOADING AND BASE TABLE PREPARATION
    # ============================================================
    # Load raw tables from the PostgreSQL database. These tables contain
    # event metadata, race results, athlete data and detailed workout splits.
    import pandas as pd
    import numpy as np

    events = pd.read_sql("SELECT * FROM events", engine)
    results = pd.read_sql("SELECT * FROM results", engine)
    athletes = pd.read_sql("SELECT * FROM athletes", engine)
    result_members = pd.read_sql("SELECT * FROM result_members", engine)
    workout_splits = pd.read_sql("SELECT * FROM workout_splits", engine)

    # Join result members with athlete attributes so each result can be
    # connected with athlete name and country metadata.
    members = result_members.merge(
        athletes,
        on="athlete_id",
        how="left"
    )

    # Build a base result-level table: one row per race result with event
    # and athlete information attached.
    hyrox_base = (
        results
        .merge(events, on="event_id", how="left")
        .merge(
            members[["result_id", "athlete_id", "name", "country"]],
            on="result_id",
            how="left"
        )
    )

    # Convert workout split data from long format to wide format so that
    # every split becomes a separate column, e.g. Running 1, Sled Push.
    splits_wide = (
        workout_splits
        .pivot_table(
            index="result_id",
            columns="split_name",
            values="split_time",
            aggfunc="first"
        )
        .reset_index()
    )

    # Final raw analytical table used for feature engineering.
    hyrox = hyrox_base.merge(
        splits_wide,
        on="result_id",
        how="left"
    )

    # Apply the report scope filters defined above. This keeps the notebook
    # focused on the selected countries/events and OPEN/PRO divisions used in
    # the final analysis.
    race_pattern = "|".join(ANALYSIS_RACE_KEYWORDS)
    race_filter = hyrox["race_name"].astype(str).str.contains(
        race_pattern,
        case=False,
        na=False
    )

    category_filter = hyrox["division"].astype(str).str.upper().apply(
        lambda division: any(category in division for category in ANALYSIS_CATEGORY_TYPES)
    )

    hyrox = hyrox[race_filter & category_filter].copy()

    # Keep only rows from the filtered analytical scope in supporting tables.
    selected_result_ids = hyrox["result_id"].unique()
    selected_event_ids = hyrox["event_id"].unique()
    workout_splits = workout_splits[
        workout_splits["result_id"].isin(selected_result_ids)
    ].copy()
    events = events[events["event_id"].isin(selected_event_ids)].copy()

    {
        "events": events.shape,
        "results": results.shape,
        "athletes": athletes.shape,
        "result_members": result_members.shape,
        "workout_splits": workout_splits.shape,
        "hyrox": hyrox.shape,
    }
    return events, hyrox, pd, workout_splits


@app.cell
def _(hyrox):
    # Quick check: number of rows and columns in the main HYROX table.
    hyrox.shape
    return


@app.cell
def _(events):
    # Inspect available events and divisions included in the dataset.
    events[["event_id", "race_name", "division"]].sort_values(["race_name", "division"])
    return


@app.cell
def _(workout_splits):
    # Check split coverage and missing values in the raw split table.
    workout_splits.groupby("split_name")["split_time"].agg(
        rows="count",
        missing=lambda x: x.isna().sum()
    ).reset_index()
    return


@app.cell
def _(hyrox):
    # Check missing values for key race splits before feature engineering.
    key_splits = [
        "Running 1",
        "Running 8",
        "1000m SkiErg",
        "50m Sled Push",
        "50m Sled Pull",
        "Wall Balls",
        "Roxzone Time",
    ]

    hyrox[key_splits].isna().sum()
    return


@app.cell
def _(hyrox):
    # Feature engineering + data quality checks

    hyrox_fe = hyrox.copy()

    # Define expected split columns
    required_splits = [
        "Running 1",
        "Running 2",
        "Running 3",
        "Running 4",
        "Running 5",
        "Running 6",
        "Running 7",
        "Running 8",
        "1000m SkiErg",
        "50m Sled Push",
        "50m Sled Pull",
        "80m Burpee Broad Jump",
        "1000m Row",
        "200m Farmers Carry",
        "100m Sandbag Lunges",
        "Wall Balls",
        "Roxzone Time",
    ]

    run_cols_raw = [
        "Running 1",
        "Running 2",
        "Running 3",
        "Running 4",
        "Running 5",
        "Running 6",
        "Running 7",
        "Running 8",
    ]

    station_cols_raw = [
        "1000m SkiErg",
        "50m Sled Push",
        "50m Sled Pull",
        "80m Burpee Broad Jump",
        "1000m Row",
        "200m Farmers Carry",
        "100m Sandbag Lunges",
        "Wall Balls",
    ]

    # Check whether all required columns exist
    missing_columns = [c for c in required_splits if c not in hyrox_fe.columns]

    if missing_columns:
        raise ValueError(f"Missing expected split columns: {missing_columns}")

    # Convert timedeltas to seconds
    for split_col in required_splits:
        hyrox_fe[f"{split_col}_sec"] = hyrox_fe[split_col].dt.total_seconds()

    hyrox_fe["overall_time_sec"] = hyrox_fe["overall_time"].dt.total_seconds()

    run_cols_sec = [f"{c}_sec" for c in run_cols_raw]
    station_cols_sec = [f"{c}_sec" for c in station_cols_raw]

    # Core features
    hyrox_fe["run_total_calc_sec"] = hyrox_fe[run_cols_sec].sum(axis=1)
    hyrox_fe["station_total_calc_sec"] = hyrox_fe[station_cols_sec].sum(axis=1)

    hyrox_fe["run_ratio"] = hyrox_fe["run_total_calc_sec"] / hyrox_fe["overall_time_sec"]
    hyrox_fe["station_ratio"] = hyrox_fe["station_total_calc_sec"] / hyrox_fe["overall_time_sec"]

    hyrox_fe["fatigue_index"] = (
        (hyrox_fe["Running 8_sec"] - hyrox_fe["Running 1_sec"])
        / hyrox_fe["Running 1_sec"]
    )

    hyrox_fe["pacing_consistency"] = hyrox_fe[run_cols_sec].std(axis=1)

    hyrox_fe["sled_total_sec"] = (
        hyrox_fe["50m Sled Push_sec"] + hyrox_fe["50m Sled Pull_sec"]
    )

    hyrox_fe["sled_ratio"] = hyrox_fe["sled_total_sec"] / hyrox_fe["overall_time_sec"]

    hyrox_fe["wall_ball_ratio"] = hyrox_fe["Wall Balls_sec"] / hyrox_fe["overall_time_sec"]

    # Category helper
    hyrox_fe["category_type"] = hyrox_fe["division"].apply(
        lambda x: "PRO" if "PRO" in str(x).upper() else "OPEN"
    )

    # Quality checks
    feature_cols = [
        "overall_time_sec",
        "run_total_calc_sec",
        "station_total_calc_sec",
        "run_ratio",
        "station_ratio",
        "fatigue_index",
        "pacing_consistency",
        "sled_total_sec",
        "sled_ratio",
        "wall_ball_ratio",
    ]

    missing_summary = hyrox_fe[feature_cols].isna().sum().reset_index()
    missing_summary.columns = ["field", "missing_count"]

    ratio_problem_rows = hyrox_fe[
        (hyrox_fe["run_ratio"] < 0)
        | (hyrox_fe["run_ratio"] > 1)
        | (hyrox_fe["station_ratio"] < 0)
        | (hyrox_fe["station_ratio"] > 1)
        | (hyrox_fe["sled_ratio"] < 0)
        | (hyrox_fe["sled_ratio"] > 1)
        | (hyrox_fe["wall_ball_ratio"] < 0)
        | (hyrox_fe["wall_ball_ratio"] > 1)
    ]

    audit_summary = {
        "rows_total": len(hyrox_fe),
        "rows_with_complete_features": int(hyrox_fe[feature_cols].dropna().shape[0]),
        "rows_with_missing_features": int(hyrox_fe[feature_cols].isna().any(axis=1).sum()),
        "ratio_problem_rows": int(len(ratio_problem_rows)),
        "events": int(hyrox_fe["event_id"].nunique()),
        "athletes": int(hyrox_fe["athlete_id"].nunique()),
    }

    print("AUDIT SUMMARY")
    print(audit_summary)

    print("\nMISSING VALUES")
    print(missing_summary)

    print("\nFEATURE DESCRIPTIVE STATS")
    hyrox_fe[feature_cols].describe().round(3)

    print("\nSAMPLE OUTPUT")
    hyrox_fe[
        [
            "name",
            "country",
            "race_name",
            "division",
            "category_type",
            *feature_cols,
        ]
    ].head(10)
    return feature_cols, hyrox_fe


@app.cell
def _(hyrox_fe, mo):
    # ============================================================
    # RESULT DISTRIBUTION VISUALIZATION
    # ============================================================
    # Required report element: inspect the distribution of the main outcome
    # measure, overall race time, using a histogram.
    import matplotlib.pyplot as plt

    overall_time_min = hyrox_fe["overall_time_sec"] / 60
    overall_time_median_min = overall_time_min.median()
    overall_time_q1_min = overall_time_min.quantile(0.25)
    overall_time_q3_min = overall_time_min.quantile(0.75)
    overall_time_skew = overall_time_min.skew()

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(overall_time_min.dropna(), bins=25)
    ax.axvline(overall_time_median_min, linestyle="--", linewidth=2)
    ax.set_title("Distribution of HYROX finish times")
    ax.set_xlabel("Overall time (minutes)")
    ax.set_ylabel("Number of athletes")

    distribution_summary = (
        f"Median finish time: {overall_time_median_min:.1f} minutes. "
        f"Typical range (IQR): {overall_time_q1_min:.1f}-{overall_time_q3_min:.1f} minutes. "
        f"Skewness: {overall_time_skew:.2f}."
    )

    mo.vstack([
        mo.md(
            f"""
            ## Distribution of finish times

            {distribution_summary}  \n            Positive skewness indicates that most athletes finished around the typical range, while a smaller number of athletes had substantially longer race times.
            """
        ),
        fig,
    ])
    return


@app.cell
def _(hyrox_fe, mo):
    # ============================================================
    # OPTIONAL DATA QUALITY CHECKS
    # ============================================================
    # These checks do not remove records. They document potential quality issues
    # and flag outliers so that the analysis remains transparent.

    duplicate_result_rows = int(hyrox_fe.duplicated(subset=["result_id"]).sum())

    time_columns_quality = [
        column for column in hyrox_fe.columns
        if column.endswith("_sec")
    ]

    non_positive_time_rows = int(
        (hyrox_fe[time_columns_quality] <= 0).any(axis=1).sum()
    )

    overall_time_min_quality = hyrox_fe["overall_time_sec"] / 60

    q1_quality = overall_time_min_quality.quantile(0.25)
    q3_quality = overall_time_min_quality.quantile(0.75)
    iqr_quality = q3_quality - q1_quality

    lower_bound_quality = q1_quality - 1.5 * iqr_quality
    upper_bound_quality = q3_quality + 1.5 * iqr_quality

    outlier_rows_quality = hyrox_fe[
        (overall_time_min_quality < lower_bound_quality)
        | (overall_time_min_quality > upper_bound_quality)
    ]

    data_quality_summary = {
        "duplicate_result_rows": duplicate_result_rows,
        "rows_with_non_positive_times": non_positive_time_rows,
        "overall_time_outliers_iqr_rule": int(len(outlier_rows_quality)),
        "outlier_lower_bound_min": round(lower_bound_quality, 2),
        "outlier_upper_bound_min": round(upper_bound_quality, 2),
    }

    mo.md(
        f"""
        ## Data quality checks

        - Duplicate result rows: **{duplicate_result_rows}**  
        - Rows with zero or negative split/metric times: **{non_positive_time_rows}**  
        - Finish-time outliers using the IQR rule: **{len(outlier_rows_quality)}**  
        - Outlier rule: values below **{lower_bound_quality:.1f} min** or above **{upper_bound_quality:.1f} min**.

        Outliers are **kept** in the dataset because they can represent real race outcomes, but they are explicitly flagged for interpretation.
        """
    )
    return


@app.cell
def _(feature_cols, hyrox_fe):
    # Compare median performance metrics between OPEN and PRO categories.
    hyrox_fe["category_type"] = hyrox_fe["division"].apply(
        lambda x: "PRO" if "PRO" in str(x).upper() else "OPEN"
    )

    hyrox_fe.groupby("category_type")[
        feature_cols
    ].median().round(3)
    return


@app.cell
def _(hyrox_fe):
    # Inspect athletes with the lowest fatigue / strongest negative split profile.
    hyrox_fe[
        [
            "name",
            "race_name",
            "category_type",
            "overall_time_sec",
            "fatigue_index",
            "pacing_consistency",
            "run_ratio",
            "sled_ratio",
        ]
    ].sort_values("fatigue_index").head(15)
    return


@app.cell
def _(hyrox_fe):
    # Inspect athletes with the highest share of total time spent running.
    hyrox_fe[
        [
            "name",
            "race_name",
            "category_type",
            "overall_time_sec",
            "run_ratio",
            "sled_ratio",
            "wall_ball_ratio",
        ]
    ].sort_values("run_ratio", ascending=False).head(15)
    return


@app.cell
def _(hyrox_fe):
    # Inspect athletes with the highest share of total time spent running.
    hyrox_fe[
        [
            "name",
            "race_name",
            "category_type",
            "overall_time_sec",
            "run_ratio",
            "sled_ratio",
            "fatigue_index",
        ]
    ].sort_values("sled_ratio", ascending=False).head(15)
    return


@app.cell
def _(hyrox_fe):
    # ============================================================
    # CLUSTERING INPUT PREPARATION
    # ============================================================
    # Select engineered features used to group athletes into performance
    # archetypes. Rows with missing values are removed before clustering.
    cluster_features = [
        "run_ratio",
        "station_ratio",
        "fatigue_index",
        "pacing_consistency",
        "sled_ratio",
        "wall_ball_ratio",
    ]

    cluster_df = hyrox_fe[
        [
            "result_id",
            "name",
            "race_name",
            "category_type",
            *cluster_features,
        ]
    ].dropna().copy()

    cluster_df.shape
    return cluster_df, cluster_features


@app.cell
def _(cluster_df, cluster_features):
    # Standardize features before K-Means so that variables with larger
    # numerical ranges, e.g. pacing_consistency, do not dominate clustering.
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler()

    X_scaled = scaler.fit_transform(
        cluster_df[cluster_features]
    )

    X_scaled.shape
    return (X_scaled,)


@app.cell
def _(X_scaled, cluster_df):
    # Apply K-Means clustering to identify 4 athlete performance archetypes.
    from sklearn.cluster import KMeans

    kmeans = KMeans(
        n_clusters=4,
        random_state=42,
        n_init=20
    )

    cluster_df["cluster"] = kmeans.fit_predict(X_scaled)

    cluster_df["cluster"].value_counts()
    return


@app.cell
def _(cluster_df, cluster_features):
    # Summarize each cluster using median feature values. This helps interpret
    # and name the clusters as athlete archetypes.
    cluster_profiles = (
        cluster_df
        .groupby("cluster")[cluster_features]
        .median()
        .round(3)
    )

    cluster_profiles
    return (cluster_profiles,)


@app.cell
def _(cluster_profiles):
    cluster_profiles
    return


@app.cell
def _(cluster_df):
    # Assign meaningful business-friendly names to the numerical cluster labels.
    cluster_name_map = {
        0: "Fatigue-Prone",
        1: "Strength Hybrid",
        2: "Efficient Hybrid",
        3: "Aggressive Negative Splitter",
    }

    cluster_df["archetype"] = cluster_df["cluster"].map(
        cluster_name_map
    )

    cluster_df[
        [
            "name",
            "race_name",
            "category_type",
            "archetype",
        ]
    ].head(20)
    return (cluster_name_map,)


@app.cell
def _(X_scaled, cluster_df):
    # Use PCA to project multidimensional performance features into two
    # dimensions for Power BI scatter plot visualization.
    from sklearn.decomposition import PCA

    pca = PCA(n_components=2)

    X_pca = pca.fit_transform(X_scaled)

    cluster_df["pca_1"] = X_pca[:, 0]
    cluster_df["pca_2"] = X_pca[:, 1]

    cluster_df[
        [
            "name",
            "archetype",
            "pca_1",
            "pca_2",
        ]
    ].head()
    return (pca,)


@app.cell
def _(pca):
    # Share of variance explained by the two PCA components.
    pca.explained_variance_ratio_
    return


@app.cell
def _(cluster_df, hyrox_fe):
    # Build the main archetype export table by combining clustering results
    # with selected engineered performance metrics.
    cluster_export = cluster_df.merge(
        hyrox_fe[
            [
                "result_id",
                "overall_time_sec",
                "run_ratio",
                "station_ratio",
                "fatigue_index",
                "pacing_consistency",
                "sled_ratio",
                "wall_ball_ratio",
            ]
        ],
        on="result_id",
        how="left"
    )

    cluster_export.head()
    return (cluster_export,)


@app.cell
def _(hyrox_fe):
    # Create an event-level summary table for Power BI comparison across races.
    event_summary = (
        hyrox_fe
        .groupby(["race_name", "category_type"])
        .agg(
            athletes=("result_id", "count"),
            median_total_min=("overall_time_sec", lambda x: x.median() / 60),
            median_run_ratio=("run_ratio", "median"),
            median_fatigue=("fatigue_index", "median"),
            median_pacing=("pacing_consistency", "median"),
            median_sled_ratio=("sled_ratio", "median"),
        )
        .reset_index()
        .round(3)
    )

    event_summary
    return (event_summary,)


@app.cell
def _(cluster_export, cluster_profiles, event_summary):
    # Export intermediate datasets used in the first version of the dashboard.
    cluster_export.to_csv(
        "hyrox_archetypes.csv",
        index=False
    )

    cluster_profiles.to_csv(
        "hyrox_cluster_profiles.csv",
        index=False
    )

    event_summary.to_csv(
        "hyrox_event_summary.csv",
        index=False
    )
    return


@app.cell
def _(cluster_df, cluster_export, cluster_profiles, hyrox_fe):
    # Sanity check: verify row counts before integrating external data.
    print("hyrox_fe:", hyrox_fe.shape)
    print("cluster_df:", cluster_df.shape)
    print("cluster_export:", cluster_export.shape)
    print("cluster_profiles:", cluster_profiles.shape)
    return


@app.cell
def _(pd):
    # ============================================================
    # EXTERNAL DATA IMPORT
    # ============================================================
    # Load Eurostat and Google Trends files used to add country-level
    # fitness culture context to the HYROX performance dataset.
    eurostat = pd.read_excel("eurostat.xlsx")
    trends = pd.read_excel("GoogleTrends.xlsx")

    print(eurostat.head())
    print(trends.head())
    return eurostat, trends


@app.cell
def _(eurostat, trends):
    # Inspect source columns before cleaning and standardizing names.
    print("Eurostat columns:")
    print(eurostat.columns)

    print("Google Trends columns:")
    print(trends.columns)
    return


@app.cell
def _(eurostat):
    # Clean Eurostat data and keep only country-level physical activity metrics
    # used in the Power BI dashboard.
    eurostat_clean = eurostat.rename(
        columns={
            "PHYSACT (Labels)": "country_full",
            "Aerobic sports": "aerobic_sports_pct",
            "Muscle-strengthening": "strength_training_pct",
        }
    )

    eurostat_clean = eurostat_clean[
        [
            "country_full",
            "aerobic_sports_pct",
            "strength_training_pct",
        ]
    ]

    eurostat_clean.head()
    return (eurostat_clean,)


@app.cell
def _(trends):
    # Aggregate Google Trends data by country and standardize column names.
    trends_clean = (
        trends
        .groupby("Country")[
            ["Hyrox", "crossfit", "running"]
        ]
        .mean()
        .reset_index()
    )

    trends_clean = trends_clean.rename(
        columns={
            "Country": "country_full",
            "Hyrox": "hyrox_trend",
            "crossfit": "crossfit_trend",
            "running": "running_trend",
        }
    )

    trends_clean.head()
    return (trends_clean,)


@app.cell
def _(hyrox_fe):
    # Inspect athlete country codes available in the source data.
    hyrox_fe["country"].value_counts()
    return


@app.cell
def _(hyrox_fe):
    # Map each selected HYROX event to its host country. This is used as the
    # joining key for Eurostat and Google Trends country-level datasets.
    def event_country_from_race_name(race_name):
        race_name = str(race_name)

        if "Warsaw" in race_name:
            return "Poland"

        if "Lisboa" in race_name:
            return "Portugal"

        if "Barcelona" in race_name:
            return "Spain"

        if "London" in race_name:
            return "United Kingdom"

        if "Paris" in race_name:
            return "France"

        if "Copenhagen" in race_name:
            return "Denmark"

        return None


    hyrox_fe["country_full"] = hyrox_fe["race_name"].apply(
        event_country_from_race_name
    )

    hyrox_fe[
        ["race_name", "country_full"]
    ].drop_duplicates()
    return


@app.cell
def _(cluster_export, hyrox_fe):
    # Prepare country information for merging into the athlete archetype table.
    country_for_merge = hyrox_fe[
        ["result_id", "race_name", "country_full"]
    ].drop_duplicates()

    cluster_export_with_country = cluster_export.merge(
        country_for_merge,
        on=["result_id", "race_name"],
        how="left"
    )

    cluster_export_with_country[
        ["result_id", "race_name", "country_full"]
    ].head()
    return (cluster_export_with_country,)


@app.cell
def _(cluster_export_with_country, eurostat_clean, trends_clean):
    # Final enriched table: athlete archetypes + HYROX metrics + country-level
    # Eurostat and Google Trends indicators.
    hyrox_external = (
        cluster_export_with_country
        .merge(
            eurostat_clean,
            on="country_full",
            how="left"
        )
        .merge(
            trends_clean,
            on="country_full",
            how="left"
        )
    )

    hyrox_external.head()
    return (hyrox_external,)


@app.cell
def _(hyrox_external):
    # Verify that external indicators were successfully mapped to each race.
    hyrox_external[
        [
            "race_name",
            "country_full",
            "aerobic_sports_pct",
            "strength_training_pct",
            "hyrox_trend",
            "crossfit_trend",
            "running_trend",
        ]
    ].drop_duplicates()
    return


@app.cell
def _(hyrox_external, mo):
    # ============================================================
    # COUNTRY-LEVEL COMPARISON FOR THE RESEARCH QUESTION
    # ============================================================

    import matplotlib.pyplot as plt_country

    # Pick the correct Pace Change column after merges.
    if "fatigue_index" in hyrox_external.columns:
        pace_change_col = "fatigue_index"
    elif "fatigue_index_x" in hyrox_external.columns:
        pace_change_col = "fatigue_index_x"
    elif "fatigue_index_y" in hyrox_external.columns:
        pace_change_col = "fatigue_index_y"
    else:
        raise KeyError(
            "No Pace Change column found. Expected one of: "
            "fatigue_index, fatigue_index_x, fatigue_index_y"
        )

    country_comparison_report = (
        hyrox_external
        .groupby("country_full")
        .agg(
            athletes=("result_id", "count"),
            median_pace_change=(pace_change_col, "median"),
            median_total_min=("overall_time_sec", lambda values: values.median() / 60),
            median_aerobic_activity=("aerobic_sports_pct", "median"),
            median_running_interest=("running_trend", "median"),
        )
        .reset_index()
        .sort_values("median_pace_change")
    )

    fig_country, ax_country = plt_country.subplots(figsize=(8, 4))

    ax_country.bar(
        country_comparison_report["country_full"],
        country_comparison_report["median_pace_change"] * 100,
    )

    ax_country.axhline(0, linewidth=1)
    ax_country.set_title("Median Pace Change by country")
    ax_country.set_xlabel("Country")
    ax_country.set_ylabel("Median Pace Change (%)")
    ax_country.tick_params(axis="x", rotation=30)

    best_country_report = country_comparison_report.iloc[0]
    worst_country_report = country_comparison_report.iloc[-1]

    pace_change_difference_pp_report = (
        worst_country_report["median_pace_change"]
        - best_country_report["median_pace_change"]
    ) * 100

    country_conclusion_report = (
        f"{best_country_report['country_full']} had the lowest median Pace Change "
        f"({best_country_report['median_pace_change'] * 100:.1f}%), while "
        f"{worst_country_report['country_full']} had the highest median Pace Change "
        f"({worst_country_report['median_pace_change'] * 100:.1f}%). "
        f"The difference between these countries was "
        f"{pace_change_difference_pp_report:.1f} percentage points."
    )

    mo.vstack([
        mo.md(
            f"""
            ## Country comparison and report conclusion

            {country_conclusion_report}

            This supports the exploratory finding that athlete pacing profiles differed between countries.
            Because only six countries/events were analyzed, this result should be interpreted as descriptive rather than causal.
            """
        ),
        fig_country,
    ])
    return


@app.cell
def _(cluster_profiles, event_summary, hyrox_external):
    # Export final enriched datasets for Power BI.
    hyrox_external.to_csv(
        "hyrox_external.csv",
        index=False
    )

    cluster_profiles.to_csv(
        "hyrox_cluster_profiles.csv",
        index=False
    )

    event_summary.to_csv(
        "hyrox_event_summary.csv",
        index=False
    )
    return


@app.cell
def _(cluster_name_map, cluster_profiles):
    # Add archetype names to the cluster profile summary for easier use in Power BI.
    cluster_profiles_export = (
        cluster_profiles
        .reset_index()
    )

    cluster_profiles_export["archetype"] = (
        cluster_profiles_export["cluster"]
        .map(cluster_name_map)
    )

    cluster_profiles_export
    return (cluster_profiles_export,)


@app.cell
def _(cluster_profiles_export):
    # Export named cluster profile summary.
    cluster_profiles_export.to_csv(
        "hyrox_cluster_profiles_v2.csv",
        index=False
    )
    return


@app.cell
def _(cluster_df, hyrox_fe):
    # Attach archetype labels back to the full feature table so running splits
    # can be reshaped for split progression analysis.
    archetype_lookup = cluster_df[
        ["result_id", "archetype"]
    ].drop_duplicates()

    hyrox_fe_with_archetype = hyrox_fe.merge(
        archetype_lookup,
        on="result_id",
        how="left"
    )

    hyrox_fe_with_archetype[
        ["result_id", "name", "archetype"]
    ].head()
    return (hyrox_fe_with_archetype,)


@app.cell
def _(hyrox_fe_with_archetype):
    # Create a long-format table of running split progression.
    # One athlete has 8 rows: Running 1 to Running 8.
    # This format is required for line charts in Power BI.
    run_progression = hyrox_fe_with_archetype[
        [
            "result_id",
            "archetype",
            "Running 1_sec",
            "Running 2_sec",
            "Running 3_sec",
            "Running 4_sec",
            "Running 5_sec",
            "Running 6_sec",
            "Running 7_sec",
            "Running 8_sec",
        ]
    ].copy()

    run_progression_long = run_progression.melt(
        id_vars=["result_id", "archetype"],
        value_vars=[
            "Running 1_sec",
            "Running 2_sec",
            "Running 3_sec",
            "Running 4_sec",
            "Running 5_sec",
            "Running 6_sec",
            "Running 7_sec",
            "Running 8_sec",
        ],
        var_name="split_name",
        value_name="split_time_sec"
    )

    split_order_map = {
        "Running 1_sec": 1,
        "Running 2_sec": 2,
        "Running 3_sec": 3,
        "Running 4_sec": 4,
        "Running 5_sec": 5,
        "Running 6_sec": 6,
        "Running 7_sec": 7,
        "Running 8_sec": 8,
    }

    run_progression_long["split_order"] = run_progression_long["split_name"].map(split_order_map)

    run_progression_long.to_csv(
        "hyrox_run_progression.csv",
        index=False
    )

    run_progression_long.head()
    return


if __name__ == "__main__":
    app.run()
