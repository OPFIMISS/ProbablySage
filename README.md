# ProbablySage

**深空当铺（Probably Stolen）本地源码与官方 MOD 文档查询 MCP。**

让 AI / Agent 先查本机真实类型、方法、调用位置与官方规则，再编写 MOD，减少猜测 API、误读返回值和使用过期签名。

## 最快开始：把地址发给 Agent

将下面这段发给**能操作本机、支持 MCP 的 Agent**，填写实际游戏目录：

> 帮我安装这个 MCP 项目地址：https://github.com/OPFIMISS/ProbablySage 。游戏目录：`D:/Steam/steamapps/common/Probably Stolen`。请阅读 README 和 docs/AGENT_GUIDE.zh-CN.md，运行本地部署，使用生成的真实路径配置 MCP，保留其他配置。连接后调用 doctor 并查询、读取一个实际游戏方法，告诉我结果；不要启动游戏或改存档。

这段话是给 Agent 的安装指令，不是点击即安装链接。Agent 需要文件访问和命令执行权限，客户端需要支持 MCP。

**状态：0.1.1 开发预览。** 新增可直接查询的原生UI融合实践，修复泛型调用漏查，解析问题提供文件和行号。升级后重建索引。本地查询工具，不包含游戏内 Agent、后台测试、多开或无头运行。它能提供代码证据，不能保证 MOD 没有 BUG。

[English](README.en.md) · [Agent 分步指南](docs/AGENT_GUIDE.zh-CN.md) · [官方 MOD 开发文档](https://github.com/dragonpan2/probably-stolen-modding)

## 本地快捷部署

需要 Python 3.10+、Git、正版已安装游戏及 .NET 10 SDK。自动安装的固定版 ILSpy 需要 .NET 10 运行时；已有其他可运行的 `ilspycmd` 时可自行通过 `--ilspy` 提供。

```powershell
git clone https://github.com/OPFIMISS/ProbablySage.git C:/Projects/ProbablySage
cd C:/Projects/ProbablySage
.\setup.ps1 -GamePath 'D:/Steam/steamapps/common/Probably Stolen'
```

脚本在项目内创建 `.venv`、安装固定版本依赖，按本机游戏程序集生成索引，并下载官方中文指南、API 变更及规则。第一次可能需要几分钟。若脚本执行被本机策略阻止，可以使用下方 Python 命令，不必永久更改系统策略。

已有 ILSpy 时：

```powershell
.\setup.ps1 -GamePath 'D:/Steam/steamapps/common/Probably Stolen' `
  -Ilspy 'C:/Tools/ilspycmd.exe'
```

也可以手动部署：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -e .
.\.venv\Scripts\python.exe -m probablysage setup --game 'D:/Steam/steamapps/common/Probably Stolen'
```

索引默认在用户目录 `.probablysage`，与仓库分开。自定义路径时，后续配置、重建和查询使用同一个 `--data`：

```powershell
.\.venv\Scripts\python.exe -m probablysage --data 'D:/Private/ProbablySage' setup `
  --game 'D:/Steam/steamapps/common/Probably Stolen'
```

## 连接客户端

部署会输出**当前机器的完整 MCP JSON**，并在数据目录生成：

- `mcp.local.json`：支持 `mcpServers` 的客户端配置片段。
- `codex.local.toml`：使用 TOML 格式的 Codex MCP 配置片段。

将单个 `probablysage` 条目合并到客户端配置，保留其他设置；不要整份覆盖。客户端配置文件的位置以其官方说明为准。重新连接 MCP 后先调用 `doctor`。

通用 JSON 示例，**路径必须替换**：

```json
{
  "mcpServers": {
    "probablysage": {
      "command": "C:/Projects/ProbablySage/.venv/Scripts/python.exe",
      "args": ["-m", "probablysage", "--data", "C:/Users/YOUR_NAME/.probablysage", "serve"]
    }
  }
}
```

完整示例见 [examples/mcp.json](examples/mcp.json) 和 [examples/codex.toml](examples/codex.toml)。
不依赖当前工作目录，不需要激活虚拟环境，不需要开启 HTTP 端口。

## 能查询什么

| 工具 | 用途 |
|---|---|
| `doctor` | 首先检查索引覆盖、程序集／索引版本是否变化、解析问题位置、官方文档提交及限制 |
| `search_symbols` | 搜索类型、方法、重载、属性、字段，返回真实签名和 ID |
| `read_symbol` | 按返回的 ID 读取声明和实现 |
| `search_source` | 按字面文本查询物品 ID、标签、钩子或任意代码片段 |
| `read_lines` | 按已发现的文件 ID 和行号读取上下文，支持继续读取 |
| `find_references` | 查询同名语法调用／成员访问，定位调用者及前置检查 |
| `search_official_docs` | 查询本地缓存的官方指南、迁移说明和发布规则 |
| `development_guide` | 按物品、库存、对话、UI、场景、高亮等主题给出研究步骤；UI相关主题直接返回融合实践 |

每条证据带来源文件、行号、程序集或官方提交；分页结果给出下一步参数。工具名和参数保持简单，返回下一步动作，适合需要明确操作步骤的模型。详见 [Agent 指南](docs/AGENT_GUIDE.zh-CN.md)。

默认反编译本机 `Assembly-CSharp.dll`，存在时同时处理 `Assembly-CSharp-firstpass.dll`；使用 Tree-sitter C# 语法树建立声明和引用索引，不用正则表达式猜方法边界。

`find_references` 是**语法匹配**，不是完整语义调用图：同名方法可能属于不同对象，反射和委托调用可能遗漏。反编译代码出现语法错误时会报告数量，应结合文本上下文及必要的 IL 核对。

## 原生 UI 与场景融合

新增 [原生 UI 融合实践](src/probablysage/practice/native-ui.md)，随工具安装，AI不必另外寻找本机Skill。内容包括：

- 克隆原生平板、复用字体与控件、清理输入焦点及关闭回调。
- 顾客终端的像素、透视、场景锚点、透明画布裁切与局部点击。
- 展示柜外观和真实库存分离，保持原生格子尺度及拖放逻辑。
- 区分精灵Alpha轮廓、单槽矩形边框、库存逐格提示。
- 常驻窗口拦截Enter、重复点击、共享资源清理、库存扩格读档等踩坑。

直接通过MCP读取：

```text
development_guide(topic="ui")
development_guide(topic="scene")
development_guide(topic="highlight")
search_source(query="PixelWindow", corpus="practice")
```

`practice`是项目实践，`official`是官方文档，`game`是本机游戏源码。工具明确区分三者；实践里的项目辅助类和历史坐标不应被当作全游戏通用API或完美视觉保证。

## 更新与其他源码

游戏更新后，重新运行原来的部署／setup 命令。重建成功才替换旧索引；失败保留旧快照，`doctor` 会标记已变化的程序集。新索引的数字 ID 不能沿用。

官方文档在建立索引时解析到具体提交并下载；日常查询不联网，也不会自动声称文档仍是最新。

升级ProbablySage后也需要重建。`doctor`的`index_upgrade_needed`会标出旧版索引，旧结果仍可读取，但`stale=true`，不能当作新版索引证据。解析问题现在会给出`file_id`、文件、行号及类型；`read_lines`保留原始文本，并附当前文件的诊断。

可以加入**你有权读取的** MOD 源码：

```powershell
.\.venv\Scripts\python.exe -m probablysage setup `
  --game 'D:/Steam/steamapps/common/Probably Stolen' `
  --source 'D:/MyMods/MyMod/src'
```

可重复传 `--source`。离线可加 `--skip-docs`，但该快照不会包含官方文档；工具会显示缺少提交号。只有源码没有游戏时，也不能声称查询结果来自当前安装游戏。

## 边界与来源

- 游戏源码、DLL、资源和索引留在本机，不上传，不随仓库分发。源码查询仅提供给你选择的 MCP 客户端；客户端是否将上下文发送给模型服务，取决于你的客户端与模型设置。
- 查询服务只读本地快照，不提供任意路径读取、代码执行、游戏控制或保护绕过。
- 官方支持范围和限制依据 [probably-stolen-modding](https://github.com/dragonpan2/probably-stolen-modding)；实际签名依据本机程序集。官方文档不会让尚未安装的新接口凭空出现。
- 新鲜度检查使用文件大小与修改时间，不做逐次哈希。相同大小且保留时间戳的替换可能无法发现，此时主动重建。
- 只建立本机索引；不提供公开游戏源码服务。不要把索引目录提交到自己的仓库。
- 灵感来自 [RimSage](https://github.com/realloon/RimSage)，本项目独立实现；MCP 使用[官方 Python SDK](https://github.com/modelcontextprotocol/python-sdk)，反编译使用 [ILSpy](https://github.com/icsharpcode/ILSpy)。

## 验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m probablysage doctor
```

发布前执行本机程序集索引、真实 stdio 连接和查询验证；记录见 [验证范围](docs/VALIDATION.md)。这些检查不等于 Unity 游戏内测试。
