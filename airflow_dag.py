"""Example: run the pipeline every day with Apache Airflow.

Airflow runs on Linux or WSL. Install it there, copy this file and pipeline.py into
Airflow's dags/ folder, and the scheduler runs run_pipeline() once a day.
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from pipeline import run_pipeline

with DAG(
    dag_id="student_performance_pipeline",
    start_date=datetime(2026, 11, 1),
    schedule="@daily",
    catchup=False,
) as dag:
    PythonOperator(task_id="run_pipeline", python_callable=run_pipeline)
