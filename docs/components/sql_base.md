# SQLBaseComponent

Base component for SQL database operations.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: sql_base
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
  <freeform-object>
}
```


## Component Output Schema

```
{
  <freeform-object>
}
```
