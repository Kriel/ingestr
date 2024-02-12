"""Source that loads tables form any SQLAlchemy supported database, supports batching requests and incremental loads."""

from typing import Any, Iterable, List, Optional, Union

import dlt
from dlt.sources import DltResource
from dlt.sources.credentials import ConnectionStringCredentials
from sqlalchemy import MetaData, Table
from sqlalchemy.engine import Engine

from .helpers import (
    SqlDatabaseTableConfiguration,
    engine_from_credentials,
    get_primary_key,
    table_rows,
)
from .schema_types import table_to_columns


@dlt.source
def sql_database(
    credentials: Union[ConnectionStringCredentials, Engine, str] = dlt.secrets.value,
    schema: Optional[str] = dlt.config.value,
    metadata: Optional[MetaData] = None,
    table_names: Optional[List[str]] = dlt.config.value,
    detect_precision_hints: Optional[bool] = dlt.config.value,
) -> Iterable[DltResource]:
    """
    A DLT source which loads data from an SQL database using SQLAlchemy.
    Resources are automatically created for each table in the schema or from the given list of tables.

    Args:
        credentials (Union[ConnectionStringCredentials, Engine, str]): Database credentials or an `sqlalchemy.Engine` instance.
        schema (Optional[str]): Name of the database schema to load (if different from default).
        metadata (Optional[MetaData]): Optional `sqlalchemy.MetaData` instance. `schema` argument is ignored when this is used.
        table_names (Optional[List[str]]): A list of table names to load. By default, all tables in the schema are loaded.
        detect_precision_hints (bool): Set column precision and scale hints for supported data types in the target schema based on the columns in the source tables.
            This is disabled by default.
    Returns:
        Iterable[DltResource]: A list of DLT resources for each table to be loaded.
    """

    # set up alchemy engine
    engine = engine_from_credentials(credentials)
    engine.execution_options(stream_results=True)
    metadata = metadata or MetaData(schema=schema)

    # use provided tables or all tables
    if table_names:
        tables = [Table(name, metadata, autoload_with=engine) for name in table_names]
    else:
        metadata.reflect(bind=engine)
        tables = list(metadata.tables.values())

    for table in tables:
        yield dlt.resource(
            table_rows,
            name=table.name,
            primary_key=get_primary_key(table),
            spec=SqlDatabaseTableConfiguration,
            columns=table_to_columns(table) if detect_precision_hints else None,
        )(engine, table)


def sql_table(
    credentials: Union[ConnectionStringCredentials, Engine, str] = dlt.secrets.value,
    table: str = dlt.config.value,
    schema: Optional[str] = dlt.config.value,
    metadata: Optional[MetaData] = None,
    incremental: Optional[dlt.sources.incremental[Any]] = None,
    detect_precision_hints: Optional[bool] = dlt.config.value,
) -> DltResource:
    """
    A dlt resource which loads data from an SQL database table using SQLAlchemy.

    Args:
        credentials (Union[ConnectionStringCredentials, Engine, str]): Database credentials or an `Engine` instance representing the database connection.
        table (str): Name of the table to load.
        schema (Optional[str]): Optional name of the schema the table belongs to.
        metadata (Optional[MetaData]): Optional `sqlalchemy.MetaData` instance. If provided, the `schema` argument is ignored.
        incremental (Optional[dlt.sources.incremental[Any]]): Option to enable incremental loading for the table.
            E.g., `incremental=dlt.sources.incremental('updated_at', pendulum.parse('2022-01-01T00:00:00Z'))`
        write_disposition (str): Write disposition of the resource.
        detect_precision_hints (bool): Set column precision and scale hints for supported data types in the target schema based on the columns in the source tables.
            This is disabled by default.

    Returns:
        DltResource: The dlt resource for loading data from the SQL database table.
    """
    if not isinstance(credentials, Engine):
        engine = engine_from_credentials(credentials)
    else:
        engine = credentials
    engine.execution_options(stream_results=True)
    metadata = metadata or MetaData(schema=schema)

    table_obj = Table(table, metadata, autoload_with=engine)

    return dlt.resource(
        table_rows,
        name=table_obj.name,
        primary_key=get_primary_key(table_obj),
        columns=table_to_columns(table_obj) if detect_precision_hints else None,
    )(engine, table_obj, incremental=incremental)
