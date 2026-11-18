"""Student Performance Analytics Pipeline.

Extract -> Clean -> Transform -> Analyze -> Load -> Report, all run by run_pipeline().

Usage:
    python pipeline.py                                          # the Kaggle dataset
    python pipeline.py --input student_performance_messy.csv    # practice on messy data
"""
import argparse
import base64
import io
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # draw charts to files, no window
import matplotlib.pyplot as plt
import pandas as pd

# ---------- Settings ----------
DEFAULT_INPUT = "StudentPerformanceFactors.csv"
OUTPUT_DIR = Path("output")
IMAGES_DIR = Path("images")

# Valid range for each numeric column; values outside become missing
VALID_RANGES = {
    "hours_studied": (0, 168),      # hours per week
    "attendance": (0, 100),         # percent
    "sleep_hours": (0, 24),
    "previous_scores": (0, 100),
    "tutoring_sessions": (0, 50),
    "physical_activity": (0, 50),
    "exam_score": (0, 100),
}
# Exam scores in this dataset run from 55 to 100, so "below 50" would be an empty group
PERFORMANCE_BINS = [0, 64, 79, 100]
PERFORMANCE_LABELS = ["Needs Improvement", "Good", "Excellent"]
# Attendance runs from 60% to 100%
ATTENDANCE_BINS = [0, 69, 84, 100]
ATTENDANCE_LABELS = ["Low (60-69%)", "Medium (70-84%)", "High (85-100%)"]
# Text factors whose effect on the exam score we compare
FACTORS = ["parental_involvement", "access_to_resources", "motivation_level",
           "teacher_quality", "peer_influence", "family_income", "internet_access",
           "learning_disabilities", "school_type", "gender"]


def to_snake_case(name):
    return name.strip().lower().replace(" ", "_")


def is_text(series):
    return not pd.api.types.is_numeric_dtype(series)


# ---------- Step 1: Extract ----------
def extract_data(path):
    df = pd.read_csv(path)
    df.columns = [to_snake_case(c) for c in df.columns]
    print(f"[Extract] Loaded {len(df):,} rows and {df.shape[1]} columns from {path}")
    return df


# ---------- Step 2: Clean ----------
def clean_data(df):
    df = df.copy()
    log = {"rows_in": len(df)}

    # 1. Remove duplicate rows
    df = df.drop_duplicates()
    log["duplicates_removed"] = log["rows_in"] - len(df)

    # 2. Numbers stored as text: strip "hours", "%", "/100", then convert
    converted = 0
    for col in VALID_RANGES:
        if col in df and is_text(df[col]):
            text = (df[col].astype("string")
                    .str.replace("hours", "", regex=False)
                    .str.replace("%", "", regex=False)
                    .str.replace("/100", "", regex=False)
                    .str.strip())
            df[col] = pd.to_numeric(text, errors="coerce")
            converted += 1
    log["text_columns_converted"] = converted

    # 3. Invalid values (e.g. exam score above 100) become missing
    invalid = {}
    for col, (low, high) in VALID_RANGES.items():
        if col in df:
            bad = (df[col] < low) | (df[col] > high)
            if bad.any():
                invalid[col] = int(bad.sum())
                df.loc[bad, col] = pd.NA
    log["invalid_values"] = invalid

    # 4. Missing values
    #    exam_score is the outcome we analyze, so rows without it are dropped
    before = len(df)
    df = df.dropna(subset=["exam_score"])
    log["rows_dropped_no_exam_score"] = before - len(df)
    filled = {}
    for col in df.columns:
        missing = int(df[col].isna().sum())
        if missing == 0:
            continue
        if is_text(df[col]):
            df[col] = df[col].fillna("Unknown")          # honest label for text gaps
        else:
            df[col] = df[col].fillna(df[col].median())   # median is robust to outliers
        filled[col] = missing
    log["missing_values_filled"] = filled

    # Whole numbers back to integers for tidy output
    for col in VALID_RANGES:
        if col in df and (df[col] % 1 == 0).all():
            df[col] = df[col].astype(int)

    log["rows_out"] = len(df)
    print(f"[Clean] {log['rows_in']:,} rows in -> {log['rows_out']:,} rows out")
    print(f"        duplicates removed: {log['duplicates_removed']}, "
          f"invalid values: {invalid or 'none'}, "
          f"rows dropped (no exam score): {log['rows_dropped_no_exam_score']}")
    print(f"        missing values filled: {filled or 'none'}")
    return df.reset_index(drop=True), log


# ---------- Step 3: Transform ----------
def transform_data(df):
    df = df.copy()
    df["performance_level"] = pd.cut(df["exam_score"], bins=PERFORMANCE_BINS,
                                     labels=PERFORMANCE_LABELS, include_lowest=True)
    df["attendance_group"] = pd.cut(df["attendance"], bins=ATTENDANCE_BINS,
                                    labels=ATTENDANCE_LABELS, include_lowest=True)
    df["score_change"] = df["exam_score"] - df["previous_scores"]
    print("[Transform] Added performance_level, attendance_group and score_change")
    return df


# ---------- Step 4: Analyze ----------
def analyze_data(df):
    by_attendance = (df.groupby("attendance_group", observed=False)
                     .agg(avg_exam_score=("exam_score", "mean"),
                          students=("exam_score", "size"))
                     .round(2).reset_index())

    by_level = (df.groupby("performance_level", observed=False)
                .agg(avg_hours_studied=("hours_studied", "mean"),
                     avg_attendance=("attendance", "mean"),
                     avg_exam_score=("exam_score", "mean"),
                     total_students=("exam_score", "size"))
                .round(2).reset_index())

    numeric = df.select_dtypes("number")
    correlation = numeric.corr().round(3)
    corr_with_exam = (correlation["exam_score"].drop(["exam_score", "score_change"], errors="ignore")
                      .sort_values(ascending=False).reset_index())
    corr_with_exam.columns = ["feature", "correlation_with_exam_score"]

    rows = []
    for factor in FACTORS:
        if factor in df:
            means = df.groupby(factor)["exam_score"].mean()
            for level, mean in means.items():
                rows.append({"factor": factor, "level": level,
                             "avg_exam_score": round(mean, 2),
                             "students": int((df[factor] == level).sum())})
    by_factor = pd.DataFrame(rows)
    factor_gap = (by_factor.groupby("factor")["avg_exam_score"]
                  .agg(lambda s: s.max() - s.min()).round(2)
                  .sort_values(ascending=False).reset_index(name="gap_best_minus_worst"))

    print("[Analyze] Average exam score by attendance group:")
    print(by_attendance.to_string(index=False))
    print("[Analyze] Summary by performance level:")
    print(by_level.to_string(index=False))
    print("[Analyze] Strongest numeric links to exam score:")
    print(corr_with_exam.head(5).to_string(index=False))
    return {"by_attendance": by_attendance, "by_level": by_level,
            "correlation": correlation, "corr_with_exam": corr_with_exam,
            "by_factor": by_factor, "factor_gap": factor_gap}


# ---------- Step 5: Load ----------
def load_results(df, results, out_dir=OUTPUT_DIR):
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "student_performance_clean.csv", index=False)
    results["by_attendance"].to_csv(out_dir / "avg_score_by_attendance.csv", index=False)
    results["by_level"].to_csv(out_dir / "summary_by_performance_level.csv", index=False)
    results["correlation"].to_csv(out_dir / "correlation_matrix.csv")
    results["by_factor"].to_csv(out_dir / "avg_score_by_factor.csv", index=False)
    print(f"[Load] Saved 5 CSV files to {out_dir.resolve()} (ready for Power BI / Tableau)")


# ---------- Step 6: Report ----------
def _chart_to_base64(fig, name):
    """Save the chart to images/<name>.png (for the README) and return it as base64 (for the report)."""
    IMAGES_DIR.mkdir(exist_ok=True)
    fig.savefig(IMAGES_DIR / f"{name}.png", dpi=110, bbox_inches="tight")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def make_charts(df, results):
    charts = {}
    color = "#2c4fd6"

    fig, ax = plt.subplots(figsize=(6, 3.4))
    r = results["by_attendance"]
    ax.bar(r["attendance_group"].astype(str), r["avg_exam_score"], color=color)
    ax.set_ylim(r["avg_exam_score"].min() - 5, r["avg_exam_score"].max() + 2)
    ax.set_ylabel("Average exam score")
    ax.set_title("Exam score by attendance group")
    for i, v in enumerate(r["avg_exam_score"]):
        ax.text(i, v + 0.3, f"{v:.1f}", ha="center")
    charts["attendance"] = _chart_to_base64(fig, "score_by_attendance")

    fig, ax = plt.subplots(figsize=(6, 3.4))
    r = results["corr_with_exam"]
    ax.barh(r["feature"], r["correlation_with_exam_score"], color=color)
    ax.invert_yaxis()
    ax.axvline(0, color="#888", lw=0.8)
    ax.set_xlabel("Correlation with exam score")
    ax.set_title("Which numeric factors move with the exam score?")
    charts["correlation"] = _chart_to_base64(fig, "correlation_with_exam")

    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.scatter(df["hours_studied"], df["exam_score"], s=6, alpha=0.3, color=color)
    ax.set_xlabel("Hours studied per week")
    ax.set_ylabel("Exam score")
    ax.set_title("Hours studied vs exam score")
    charts["hours"] = _chart_to_base64(fig, "hours_vs_score")

    fig, ax = plt.subplots(figsize=(6, 3.4))
    r = results["factor_gap"]
    ax.barh(r["factor"], r["gap_best_minus_worst"], color=color)
    ax.invert_yaxis()
    ax.set_xlabel("Exam score gap between best and worst level (points)")
    ax.set_title("Which background factors matter most?")
    charts["factors"] = _chart_to_base64(fig, "background_factors")
    return charts


def generate_report(df, results, clean_log, out_dir=OUTPUT_DIR):
    charts = make_charts(df, results)
    lvl = results["by_level"].set_index("performance_level")
    att = results["by_attendance"]
    top_corr = results["corr_with_exam"].iloc[0]
    top_factor = results["factor_gap"].iloc[0]

    def table(frame):
        return frame.to_html(index=False, border=0, classes="t")

    def img(key):
        return f'<img src="data:image/png;base64,{charts[key]}" alt="{key} chart">'

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Student Performance Report</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:30px auto;padding:0 16px;color:#1b2236;line-height:1.5}}
h1{{margin-bottom:0}} .sub{{color:#5a6580}} h2{{border-bottom:2px solid #1b2236;padding-bottom:4px;margin-top:32px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:18px 0}}
.kpi{{border:1px solid #d5dbe6;border-radius:8px;padding:12px}} .kpi b{{display:block;font-size:24px}}
table.t{{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}}
table.t th,table.t td{{border:1px solid #d5dbe6;padding:5px 8px;text-align:left}} table.t th{{background:#eef1f5}}
img{{max-width:100%;margin:8px 0}} li{{margin:4px 0}}
</style></head><body>
<h1>Student Performance Report</h1>
<p class="sub">Generated {datetime.now():%Y-%m-%d %H:%M} by pipeline.py · {len(df):,} students</p>

<div class="kpis">
<div class="kpi">Students analysed<b>{len(df):,}</b></div>
<div class="kpi">Average exam score<b>{df['exam_score'].mean():.1f}</b></div>
<div class="kpi">Excellent (80+)<b>{int(lvl.loc['Excellent','total_students']):,}</b></div>
<div class="kpi">Needs improvement (&lt;65)<b>{int(lvl.loc['Needs Improvement','total_students']):,}</b></div>
</div>

<h2>Key findings</h2>
<ul>
<li>Students with high attendance (85-100%) average <b>{att['avg_exam_score'].iloc[-1]:.1f}</b>, against
<b>{att['avg_exam_score'].iloc[0]:.1f}</b> for low attendance (60-69%).</li>
<li>The numeric factor most linked to the exam score is <b>{top_corr['feature']}</b>
(correlation {top_corr['correlation_with_exam_score']:.2f}).</li>
<li>Among background factors, <b>{top_factor['factor']}</b> shows the largest gap between its best and
worst level: <b>{top_factor['gap_best_minus_worst']:.1f}</b> points.</li>
<li>Excellent students study <b>{lvl.loc['Excellent','avg_hours_studied']:.1f}</b> hours a week on average,
against <b>{lvl.loc['Needs Improvement','avg_hours_studied']:.1f}</b> for students who need improvement.</li>
</ul>
<p class="sub">Correlation shows association, not cause.</p>

<h2>Attendance</h2>{img('attendance')}{table(results['by_attendance'])}
<h2>Performance levels</h2>{table(results['by_level'])}
<h2>Study hours</h2>{img('hours')}
<h2>Numeric factors</h2>{img('correlation')}
<h2>Background factors</h2>{img('factors')}{table(results['factor_gap'])}

<h2>Data quality (cleaning log)</h2>
<ul>
<li>Rows in: {clean_log['rows_in']:,} · rows out: {clean_log['rows_out']:,}</li>
<li>Duplicates removed: {clean_log['duplicates_removed']}</li>
<li>Text columns converted to numbers: {clean_log['text_columns_converted']}</li>
<li>Invalid values set to missing: {clean_log['invalid_values'] or 'none'}</li>
<li>Rows dropped because the exam score was missing or invalid: {clean_log['rows_dropped_no_exam_score']}</li>
<li>Missing values filled (median for numbers, "Unknown" for text): {clean_log['missing_values_filled'] or 'none'}</li>
</ul>
</body></html>"""
    path = out_dir / "report.html"
    path.write_text(html, encoding="utf-8")
    print(f"[Report] Wrote {path.resolve()}")


# ---------- Run everything ----------
def run_pipeline(input_path=DEFAULT_INPUT):
    print(f"=== Pipeline started {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    df = extract_data(input_path)
    df, clean_log = clean_data(df)
    df = transform_data(df)
    results = analyze_data(df)
    load_results(df, results)
    generate_report(df, results, clean_log)
    print("=== Pipeline finished ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Student performance analytics pipeline")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="CSV file to process")
    run_pipeline(parser.parse_args().input)
