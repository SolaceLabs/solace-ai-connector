# SQLInsertComponent

Inserts data into a SQL database table.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: sql_insert
component_config:
  database_type: <string>
  sql_host: <string>
  sql_port: <integer>
  sql_user: <string>
  sql_password: <string>
  sql_database: <string>
  default_on_duplicate_update_columns: <array>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| database_type | True | postgres | Type of SQL database. Supported: 'postgres', 'mysql'. |
| sql_host | True |  | SQL database host. |
| sql_port | True |  | SQL database port. |
| sql_user | True |  | SQL database user. |
| sql_password | True |  | SQL database password. |
| sql_database | True |  | SQL database name. |
| default_on_duplicate_update_columns | False | [] | Optional. Default list of column names to update if a duplicate key conflict occurs. Used if not provided in the input message. |


## Component Input Schema

```
{
  table_name:   <string>,
  data:   <['object', 'array']>,
  on_duplicate_update_columns: [
    <string>,
    ...
  ]
}
```
| Field | Required | Description |
| --- | --- | --- |
| table_name | True | The name of the table to insert data into. |
| data | True | The data to insert. A single dictionary for one row, or a list of dictionaries for multiple rows. Keys should match column names. |
| on_duplicate_update_columns | False | Optional. List of column names to update if a duplicate key conflict occurs (e.g., for INSERT ... ON DUPLICATE KEY UPDATE or ON CONFLICT ... DO UPDATE). |


## Component Output Schema

```
{
  affected_rows:   <integer>,
  table_name:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| affected_rows | False | The number of rows affected by the insert operation. |
| table_name | False | The table into which data was inserted. |
