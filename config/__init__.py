import pymysql
pymysql.install_as_MySQLdb()

# Bypass MySQL version check for MySQL 8.0 compatibility
from django.db.backends.base.base import BaseDatabaseWrapper
BaseDatabaseWrapper.check_database_version_supported = lambda self: None
