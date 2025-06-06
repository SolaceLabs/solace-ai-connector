# SQLExecuteComponent

Executes an arbitrary SQL query against the database.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: sql_execute
component_config:
  database_type: <string>
  sql_host: <string>
  sql_port: <integer>
  sql_user: <string>
  sql_password: <string>
  sql_database: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| database_type | True | postgres | Type of SQL database. Supported: 'postgres', 'mysql'. |
| sql_host | True |  | SQL database host. |
| sql_port | True |  | SQL database port. |
| sql_user | True |  | SQL database user. |
| sql_password | True |  | SQL database password. |
| sql_database | True |  | SQL database name. |


## Component Input Schema

```
{
  query:   <string>,
  params:   <['object', 'array']>,
  fetch_results:   <boolean>
}
```
| Field | Required | Description |
| --- | --- | --- |
| query | True | The SQL query to execute. |
| params | False | Optional. Parameters to bind to the query. Use a list/tuple for positional placeholders (e.g., %s) or a dictionary for named placeholders (e.g., %(name)s), if supported by the DB driver. |
| fetch_results | False | Optional. Whether to fetch and return results (e.g., for SELECT queries). If False, might return row count for DML operations. |


## Component Output Schema

```
{
  results:   <['array', 'integer']>,
  query:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| results | False | Query results. For SELECT, typically a list of dictionaries. For DML (if fetch_results=false), typically the number of affected rows. |
| query | False | The executed query. |
