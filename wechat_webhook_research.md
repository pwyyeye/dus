# WeChat Work Webhook Research

## Webhook URL Format

```
https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={KEY}
```

Where `{KEY}` is a 32-character alphanumeric string obtained when creating a group bot.

Example:
```
https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc123def456ghi789jkl012mno345pq
```

## Message Format

```json
{
  "msgtype": "markdown",
  "markdown": {
    "content": "**Bold** and *italic* text\n> Quote\n- List item 1\n- List item 2"
  }
}
```

### Supported Markdown Syntax
- `**text**` - Bold
- `*text*` - Italic
- `> text` - Quote block
- `- text` - Unordered list
- `[text](url)` - Links
- `<@user_id>` - @ mentions (optional)
- `<!channel>` or `<!here>` - @ all (optional)

## Rate Limits

- **20 messages per minute** per group bot
- Exceeding the limit results in error code 45029

## Curl Test Command

```bash
curl -X POST "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "msgtype": "markdown",
    "markdown": {
      "content": "**DUS System Test**\n> Hello from DUS distributed AI system\n- Test item 1\n- Test item 2"
    }
  }'
```

## Creating a Group Bot (Manual Steps)

1. Open WeChat Work (desktop or mobile)
2. Navigate to the target group chat
3. Click group settings (右上角群设置)
4. Click "添加群机器人" (Add Bot)
5. Click "创建一个机器人" (Create a Bot)
6. Give it a name (e.g., "DUS Alert Bot")
7. Copy the webhook URL from the bot configuration
8. Update `cloud/.env` with the actual `WECHAT_WEBHOOK_URL`
