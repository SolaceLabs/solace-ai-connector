# SlackInput

Slack input component. The component connects to Slack using the Bolt API and receives messages from Slack channels.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: slack_input
component_config:
  slack_bot_token: <string>
  slack_app_token: <string>
  max_file_size: <number>
  max_total_file_size: <number>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| slack_bot_token | False |  | The Slack bot token to connect to Slack. |
| slack_app_token | False |  | The Slack app token to connect to Slack. |
| max_file_size | False | 20 | The maximum file size to download from Slack in MB. Default: 20MB |
| max_total_file_size | False | 20 | The maximum total file size to download from Slack in MB. Default: 20MB |



## Component Output Schema

```
{
  event:   {
    text:     <string>,
    files: [
      {
        name:         <string>,
        content:         <string>,
        mime_type:         <string>,
        filetype:         <string>,
        size:         <number>
      },
      ...
    ],
    user_email:     <string>,
    mentions: [
      <string>,
      ...
    ],
    type:     <string>,
    user_id:     <string>,
    client_msg_id:     <string>,
    ts:     <string>,
    channel:     <string>,
    subtype:     <string>,
    event_ts:     <string>,
    channel_type:     <string>
  }
}
```
| Field | Required | Description |
| --- | --- | --- |
| event | True |  |
| event.text | False |  |
| event.files | False |  |
| eventfiles[].name | False |  |
| eventfiles[].content | False |  |
| eventfiles[].mime_type | False |  |
| eventfiles[].filetype | False |  |
| eventfiles[].size | False |  |
| event.user_email | False |  |
| event.mentions | False |  |
| event.type | False |  |
| event.user_id | False |  |
| event.client_msg_id | False |  |
| event.ts | False |  |
| event.channel | False |  |
| event.subtype | False |  |
| event.event_ts | False |  |
| event.channel_type | False |  |
