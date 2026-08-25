# IMG Node Editor

本地网页工具，用于同步编辑一对松散的客户端 `.img` 与服务端
`.img.xml` 文件。

```bash
cd tool/wz-python
python3 -m img_editor --port 5017
```

浏览器打开 `http://127.0.0.1:5017/`，通过“选择”按钮选取 IMG 与对应
XML，也可以直接输入路径。
仓库 `clien/Data/<WZ名>/...` 下的 IMG 可自动推断
`gms-server/wz/<WZ名>.wz/...img.xml`。

支持新增的类型：`SubProperty`、`Null`、`Short`、`Int`、`Long`、
`Float`、`Double`、`String`、`Vector`、`UOL`。Canvas、Sound 等媒体
节点可以查看、重命名和删除，但不提供媒体导入。

每次修改会先同时生成并验证 IMG/XML，再替换原文件。首次修改会在
原文件旁创建 `.web-editor.bak` 基线备份。若文件被其他程序修改，编辑器
会拒绝继续写入，重新打开文件后才能操作。
