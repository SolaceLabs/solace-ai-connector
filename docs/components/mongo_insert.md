# MongoDBInsertComponent

Inserts data into a MongoDB database.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: mongo_insert
component_config:
  database_host: <string>
  database_port: <integer>
  database_user: <string>
  database_password: <string>
  database_name: <string>
  database_collection: <string>
  data_types: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| database_host | True |  | MongoDB host |
| database_port | True |  | MongoDB port |
| database_user | False |  | MongoDB user |
| database_password | False |  | MongoDB password |
| database_name | True |  | Database name |
| database_collection | False |  | Collection name - if not provided, all collections will be used |
| data_types | False |  | Key value pairs to specify the data types for each field in the data. Used for non-JSON types like Date. Supports nested dotted names |


## Component Input Schema

```
{
  collection:   <string>,
  query:   {
    <freeform-object>
  }
}
```
| Field | Required | Description |
| --- | --- | --- |
| collection | False | The collection to search in. |
| query | False | The query pipeline to execute. if string is provided, it will be converted to JSON. |
