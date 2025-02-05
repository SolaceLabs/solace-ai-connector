# MongoDBSearchComponent

Searches a MongoDB database.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: mongo_search
component_config:
  database_host: <string>
  database_port: <integer>
  database_user: <string>
  database_password: <string>
  database_name: <string>
  database_collection: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| database_host | True |  | MongoDB host |
| database_port | True |  | MongoDB port |
| database_user | False |  | MongoDB user |
| database_password | False |  | MongoDB password |
| database_name | True |  | Database name |
| database_collection | False |  | Collection name - if not provided, all collections will be used |


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
