# Airflow's official image + the Java runtime and PySpark client needed for
# transform_dag to spark-submit jobs to the standalone Spark cluster, plus
# this repo's own pipeline package (GE suites, generators, anomaly logic,
# WAP helper) so DAGs can import it directly.
FROM apache/airflow:2.10.4-python3.11

USER root

# Java 17 is required by spark-submit's driver JVM (Iceberg's Spark runtime
# and the standalone Spark 3.5 cluster both target Java 17).
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk-headless procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

USER airflow

COPY requirements.txt /tmp/requirements.txt

# Installed against Airflow's own constraints for this Airflow+Python
# combination first, so pip's resolver doesn't fight Airflow's pinned
# transitive dependencies -- then this repo's runtime deps on top.
RUN pip install --no-cache-dir \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.10.4/constraints-3.11.txt" \
    apache-airflow==2.10.4 \
    && pip install --no-cache-dir -r /tmp/requirements.txt

ENV SPARK_HOME=/home/airflow/.local/lib/python3.11/site-packages/pyspark
ENV PATH="${SPARK_HOME}/bin:${PATH}"
ENV PYTHONPATH="/opt/airflow:${PYTHONPATH}"

COPY --chown=airflow:root pipeline /opt/airflow/pipeline
