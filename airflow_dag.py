"""Airflow DAG that runs the pipeline daily (place with pipeline.py in the dags/ folder)."""
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
