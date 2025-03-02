from django.db import OperationalError, InterfaceError
import clickhouse_connect.driver.exceptions as ch_exceptions


DATABASE_CONNECTION_ERRORS = [
    OperationalError,
    ch_exceptions.OperationalError,
    InterfaceError,
    ch_exceptions.InterfaceError,
]

