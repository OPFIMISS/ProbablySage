---
name: probably-stolen-network-upgrades
description: 新增或排查深空当铺（Probably Stolen）王尔德人脉网络升级，处理原生卡片、注册时序、购买即时效果、存档恢复和调价。适用于 AddNetworkUpgrade、人脉升级缺失或买下后无效果；不用于其他游戏或通用 UI。
---

# 深空当铺原生人脉升级

先查本机游戏和官方说明，使用`ModHelper.AddNetworkUpgrade`与原生网络窗口。若ProbablySage已连接，调用`development_guide(topic="network")`读取完整案例；未连接时读取本仓库`src/probablysage/practice/network-upgrades.md`，或按以下关键点检查。

- 2026-11-10本机实践：`RegisterModUpgrade`访问`PlayerStore.Instance`，主菜单直接调用曾触发空引用。`Init/OnEnable`只订阅，在`OnGameLoadedLate`及`OnNewGameStarted`就绪后注册。不要把该版本经验当成永久官方限制。
- `OnGameLoadedInit`在本机反序列化前发生，不能当作完整读档完成。
- `subtitle`控制原生分组，`tab`控制标签页。使用稳定MOD前缀ID和明确前置，复用原生卡片及图标。
- 当前本机`Unlock`先标记已购，再执行`onUnlock`。购买立即应用效果；读档独立查询已购状态恢复，不重复扣钱或重买。
- 定义和运行记录分开。调价同步`GetNetworkUpgrade(id).cost`，保留购买状态，不用默认对象替换玩家记录。
- 对称退订和移除自有定义；不补丁加载器、信任或扫描保护。
- 卡片、购买、真实效果和提示分别确认。已确认0.12.1卡片恢复；0.12.2出水与提示统一修复尚待玩家复测。不能说卡片出现就等于所有功能通过。
- 若提示仍旧，查提示是否读取原生字段而效果使用私有缓存。恢复点覆盖购买、载入、新局和换日；检查实际消费者，不靠修改文案掩盖数据分歧。
- 购买前的旧存档不含后来购买，不能靠读旧档验证购买立即生效。

源码仅供本机核对，不把游戏DLL、反编译实现、私人路径、存档和索引放入Git。经验文档保留来源与实机边界。
