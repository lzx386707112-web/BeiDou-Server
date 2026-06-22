## OrzRepacker

### I18n 多语言配置方法
创建 config.ini 文件
```ini
# zh_CN / en_US
language = zh_CN
```

### MCP连接方式

将配置里的
`spring.main.web-application-type=none`
改为
`spring.main.web-application-type=servlet`
启用web端口

本地默认开启10002端口

参考配置

```json
{
  "mcpServers": {
    "orange-wz": {
      "url": "http://127.0.0.1:10002/mcp"
    }
  }
}
```

