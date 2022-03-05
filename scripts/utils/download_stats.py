from calendar import monthrange
from datetime import datetime

import dask.dataframe as dd
from google.cloud import bigquery
import pandas as pd


def get_conda_stats(packages=[], year=None, month=None):
    """
    Read Conda download statistics from AWS S3
    This function readS data from a public AWS S3 store containing hourly
    Conda package download data.
    """
    if not packages:
        return None

    if year is None:
        year = '*'

    if month is None:
        month = '*'

    s3uri = f's3://anaconda-package-data/conda/hourly/{year}/{month}/*-*-*.parquet'
    df = dd.read_parquet(
        s3uri,
        storage_options={'anon': True},
        engine='pyarrow',
    )
    if 'pkg_name' not in df:
        return None

    df = df[['time', 'data_source', 'pkg_name', 'counts']]
    df = df.loc[df.pkg_name.isin(packages)].compute()
    df.pkg_name = df.pkg_name.cat.remove_unused_categories()
    df = df.groupby([df.time.dt.to_period('M'), df.pkg_name]).sum().reset_index()
    df = df.pivot(index='time', columns='pkg_name', values='counts')
    df.index.name = 'month'

    return df


def get_pypi_stats(packages=[], year=None, month=None):
    """
    Read PyPI download statistics from Google BigQuery
    """
    if not packages:
        return None

    if year is None:
        year1 = 2019
        year2 = datetime.now().year
    else:
        year1 = year2 = year

    if month is None:
        month1 = 1
        month2 = 12
    else:
        month1 = month2 = month

    day1 = 1
    day2 = monthrange(year2, month2)[1]

    client = bigquery.Client()

    pkg_string = ', '.join(f"'{p}'" for p in packages)

    pkg_query_list = []
    for i, p in enumerate(packages):
        pkg_query_list.append(f"SUM(CASE WHEN file.project = '{p}' THEN 1 ELSE 0 END) AS `p{i}`")
    pkg_queries = ',\n    '.join(pkg_query_list)

    sql = f"""
    SELECT
        FORMAT_DATE("%Y-%m", DATE(timestamp)) as `month`,
        {pkg_queries}
    FROM `bigquery-public-data.pypi.file_downloads`
    WHERE
        file.project in ({pkg_string})
        AND DATE(timestamp) >= '{year1:04d}-{month1:02d}-{day1:02d}'
        AND DATE(timestamp) <= '{year2:04d}-{month2:02d}-{day2:02d}'
    GROUP BY `month`
    ORDER BY `month` ASC
    """

    df = client.query(sql).to_dataframe()
    df = df.rename(columns={f'p{i}': p for i, p in enumerate(packages)})
    df['month'] = pd.to_datetime(df.month).dt.to_period('M')
    df.columns.name = 'pkg_name'
    df = df.set_index('month')

    return df