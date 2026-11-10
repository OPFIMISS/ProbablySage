# 给 Agent 的操作说明

## 你正在安装什么

这是本地源码与官方文档查询工具，不是游戏 MOD，也不是自动测试工具。
它不会代替你编译 MOD，不会启动游戏，不会修改存档。
用户需要自己安装正版游戏；仓库不提供游戏 DLL、源码或资源。

## 安装流程

1. 克隆 https://github.com/OPFIMISS/ProbablySage 到用户指定的工具目录。
2. 确认用户游戏目录中存在 `Probably Stolen_Data/Managed/Assembly-CSharp.dll`。不要把 MOD 目录当作游戏目录。
3. 使用 Python 3.10+；需要本地反编译时还要可运行的 ILSpy。`setup.ps1` 会在找不到 ILSpy 时安装固定版本的 dotnet tool。
4. 执行 README 的安装命令。失败就阅读错误，修复缺失条件；不要重复执行完整安装来碰运气。
5. 安装结果会输出真正可用的 MCP 配置，并在数据目录生成 JSON 和 TOML。不要原样使用示例中的 `YOUR_NAME`。
6. 根据客户端支持的格式合并单个 `probablysage` 条目，保留其他配置。客户端无 MCP 支持时，说明该限制。
7. 连接 MCP，调用 `doctor`。确认不是过期索引，有游戏程序集证据，有官方文档提交号。
8. 调用 `search_symbols(query="ModHelper")`，读取一个返回的 `symbol_id`。这才完成连接验证。

## 每次开发固定走这几步

1. `doctor()`。若 `stale=true`，重新建立索引。不要把旧签名写成当前版本。
2. `development_guide(topic="items")` 等；选择接近任务的主题。
3. `search_official_docs(query="OnGameLoaded")` 等。一次查询一个关键词；中文文档里的英文 API 名通常更容易命中。
4. `search_symbols(query="目标类型或短方法名")`。返回同名重载时逐个看参数。
5. `read_symbol(symbol_id=返回的数字)`。不能自己猜数字；它只在本轮索引内有效。
6. `find_references(member="短方法名")`。返回的是语法匹配，不保证接收对象属于同一类型。
7. 使用 `read_symbol` 或 `read_lines` 阅读调用者前后的合法性检查、状态、所有权、返回值和保存行为。
8. 有证据后再写 MOD。编译引用当前安装的程序集，按官方规则扫描；游戏内效果另行验证。

涉及原生平板、墙面终端、展示柜或高亮，先调用`development_guide(topic="ui")`，直接读取返回的`practice.content`。`scene`、`inventory`、`highlight`也会返回融合参考。它是项目经验，不是官方接口承诺；再按其中的原生类型查本机签名。

需要找具体经验时，使用`search_source(query="输入焦点", corpus="practice")`等。不要把practice命中解释成官方文档或游戏本体实现。

涉及王尔德人脉升级，先调用`development_guide(topic="network")`。当前本机AddNetworkUpgrade会触及PlayerStore，主菜单直接注册曾导致空引用，应在载入／新局就绪后注册。分别检查卡片、购买、真实效果和提示的数据来源；购买前旧档不含后来的购买。详情与验证边界均在返回的practice中，独立Skill位于skills/probably-stolen-network-upgrades。

## 具体例子

用户：“做一个能放物品的展示柜。”

```text
doctor()
development_guide(topic="inventory")
search_official_docs(query="机器窗口")
search_symbols(query="GameGridInventory")
read_symbol(symbol_id=<上一步的真实ID>)
search_symbols(query="TryAcceptAll")
read_symbol(symbol_id=<实际返回的ID>)
find_references(member="TryAcceptAll")
read_lines(file_id=<返回的文件ID>, start_line=<调用行前10行>, count=40)
```

这能避免看到名字就把 `TryAcceptAll` 的返回值当成“成功数量”。
必须阅读真实代码，判断返回的是剩余数量、成功数量、布尔条件还是其他含义。

## 工具结果怎样处理

| 情况 | 正确处理 |
|---|---|
| matches 为空 | 换短关键词，查官方文档；仍为空就明确未找到，不发明 API |
| next_offset 不为 null | 将其作为下一次查询的 offset，继续翻页 |
| next_line 不为 null | 用同一个 file_id 和 next_line 继续读取，尤其是长方法 |
| stale 为 true | 先重建；若仅研究旧版本，明确写出旧版本边界 |
| parser_errors 大于零 | AST索引可能遗漏；退回文本搜索和上下文，必要时人工核对IL |
| parser_issues 有内容 | 按其中的file_id／start调用read_lines；原始文本未被删改或“修正” |
| index_upgrade_needed 为 true | 工具升级过，旧索引还未重建；重跑setup后再用新版结果 |
| 只有官方文档、无程序集 | 不能保证本机提供文档中的接口 |
| 查询到 SteamManager/加载器等 | 可理解启动行为，不代表允许打补丁；先读官方限制 |
| 编译或扫描通过 | 只汇报对应结果，不等于游戏内功能通过 |

## 不要做的事

- 不把 RimWorld 的 Def、Tick、`-quicktest` 或存档参数套到本游戏。
- 不把载入回调当作逐帧更新；不在主菜单初始化时访问局内单例。
- 不通过修改信任、加载器或 Steam 保护来让代码运行。
- 不把游戏源码上传到 GitHub、在线索引或公共日志。
- 不声称查询工具可以保证没有 BUG。

0.1.1起，`find_references(member="GetComponent")`会包含`GetComponent<T>()`等泛型调用。仍应读取接收对象及上下文，不能把同名调用视作已完成类型绑定。
