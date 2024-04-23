# Built-in Transforms

| Component | Description |
| --- | --- |
| [append](append.md) | Select a source value and append it to a destination list.  |
| [copy](copy.md) | Copy Transform - copy a value from one field to another. |
| [copy_list_item](copy_list_item.md) | Select a source list. Iterate over the list and copy the value of a field to a destination list at the same index. This can be used to create multiple lists from a single list or vice versa. NOTE: this transform is deprecated - use 'map' instead. |
| [filter](filter.md) | Filter a list based on a filter function |
| [map](map.md) | This is a map transform where a list is iterated over, processed and then placed at the same index in the destination list. |
| [reduce](reduce.md) | Reduce a list to a single value |
