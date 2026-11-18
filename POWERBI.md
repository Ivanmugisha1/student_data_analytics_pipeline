# Power BI dashboard

Build an interactive dashboard from the files the pipeline writes to `output/`.

## 1. Install and load the data
1. Install **Power BI Desktop** (free) from the Microsoft Store.
2. Run `python pipeline.py` so the `output/` folder is up to date.
3. In Power BI: **Get data → Text/CSV** → choose `output/student_performance_clean.csv` → **Load**.

This one file has every student with the columns the pipeline added (`performance_level`, `attendance_group`, `score_change`), so no relationships are needed.

## 2. Measures
In the **Modeling** tab, choose **New measure** and add:
```
Students = COUNTROWS(student_performance_clean)
Avg Exam Score = AVERAGE(student_performance_clean[exam_score])
Avg Attendance = AVERAGE(student_performance_clean[attendance])
Avg Hours Studied = AVERAGE(student_performance_clean[hours_studied])
Excellent Share = DIVIDE(
    CALCULATE([Students], student_performance_clean[performance_level] = "Excellent"),
    [Students])
```

## 3. Suggested page
| Visual | Fields |
|---|---|
| 4 **Cards** across the top | Students · Avg Exam Score · Avg Attendance · Excellent Share |
| **Clustered column chart** | X: attendance_group · Y: Avg Exam Score |
| **Scatter chart** | X: hours_studied · Y: exam_score · Legend: performance_level |
| **Bar chart** | Y: parental_involvement · X: Avg Exam Score |
| **Slicers** | gender · school_type · motivation_level |

Sort `attendance_group` in the right order: select the column, then **Column tools → Sort by column**. Or add a helper column that numbers the groups 1–3.

## 4. Keep it fresh
After running the pipeline again, press **Refresh** in Power BI and the dashboard updates.

## 5. For the portfolio
Save the file as `dashboard.pbix` in this folder and add a screenshot to `images/dashboard.png`, then show it in the README.
