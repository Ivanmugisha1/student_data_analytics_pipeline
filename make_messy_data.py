"""Generate synthetic messy data for the pipeline's robustness test.

Writes student_performance_messy.csv: the source data with duplicates, numbers stored
as text ("23 hours", "84%", "67/100"), out-of-range values and extra missing values.
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
df = pd.read_csv("StudentPerformanceFactors.csv")
n = len(df)

for col in ["Hours_Studied", "Attendance", "Exam_Score"]:
    df[col] = df[col].astype(object)

def pick(k):
    return rng.choice(n, k, replace=False)

for i in pick(600):
    df.at[i, "Hours_Studied"] = f"{df.at[i, 'Hours_Studied']} hours"
for i in pick(800):
    df.at[i, "Attendance"] = f"{df.at[i, 'Attendance']}%"
for i in pick(800):
    df.at[i, "Exam_Score"] = f"{df.at[i, 'Exam_Score']}/100"

for i in pick(15):
    df.at[i, "Attendance"] = f"{rng.integers(105, 130)}%"
for i in pick(12):
    df.at[i, "Exam_Score"] = str(rng.integers(105, 150))

for col, k in [("Hours_Studied", 40), ("Attendance", 35), ("Exam_Score", 25), ("Sleep_Hours", 20)]:
    df.loc[pick(k), col] = np.nan

df = pd.concat([df, df.sample(60, random_state=1)]).sample(frac=1, random_state=2)
df.to_csv("student_performance_messy.csv", index=False)
print(f"Saved student_performance_messy.csv with {len(df):,} rows")
