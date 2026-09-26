# 空间输入对照实验 / Spatial observation ablation

实验日期：2026-09-23。**正常使用仍以原有 `legacy` 输入为主；`full_geometry` 只用于主动选择的仿真对照。** 完整连杆碰撞几何、全部空间位姿和精确几何距离，在真实部署中难以完整获取，不能据此提高默认输入要求。

## 协议与范围

本轮为两个任务 × 两种输入 × 固定 seeds 0–9，共 40 次 JEV 尝试。同 seed 的物理初始状态经哈希核对一致，偶数 seed 先运行原有输入，奇数 seed 先运行完整几何。模型、物理参数、动作接口、提示中的动作规则和判定阈值保持一致；只增加观测信息。同 seed 不能固定远端模型响应，因此单对结果变化不能单独建立因果。

- JEV 模型：`jev-1.13.0`；两阶段选择意图与动作，无规则策略回退。
- 单门框：40 mm 方块，70 mm 开口，120 mm 横梁，350 次决策上限。
- 错位双门框：两道 90 mm 开口，横梁高 100/120 mm，中心横向错位 90 mm；依次过门、中途换道，500 次决策上限。
- 全程机器人或物体对门框的接触力总和 >0.05 N 即失败；跨越时底部净空 ≥5 mm，方块投影须在开口内。双门框还检查漏门、过门顺序和抓持状态；最终释放到目标区并稳定 0.5 s。
- 保留全部已结束试次，没有以重跑成功替换失败；录像直接渲染原始状态，不重跑 API 或物理。

冻结仿真源码指纹：`5925c8250ff703004a1e0e915bfdabc28e526849df3f77f0aafaeeb90a91ec33`。实现版本 `8bb9a86`，之后的报告和录像标注修正不改变本轮仿真源码。先前单门框 5/10 的历史评测保留在独立报告中，不与本轮合并。

## 结果：分清任务失败与基础设施中断

| 任务 | 输入 | 成功 / 全部尝试 | 碰撞等任务失败 | 响应校验失败 | API 中断 | 成功 / 可评估尝试 |
|---|---|---:|---:|---:|---:|---:|
| 单门框 | 原有输入（默认） | 0/10 | 1 | 1 | 8 | 0/2 |
| 单门框 | 完整几何（仅仿真对照） | 1/10 | 1 | 0 | 8 | 1/2 |
| 错位双门框 | 原有输入（默认） | 1/10 | 6 | 2 | 1 | 1/9 |
| 错位双门框 | 完整几何（仅仿真对照） | 2/10 | 4 | 3 | 1 | 2/9 |

全部 40 次尝试保留在主分母。辅助的“可评估尝试”只排除 API/运行中断和无法分类的策略错误，**响应校验失败仍算失败**。排除中断不是统计偏差校正；尤其单门框大量中断，不能把这些数字解释为可靠的能力成功率。

| 任务 | 输入 | 全部尝试 Wilson 95% |
|---|---|---|
| 单门框 | 原有输入（默认） | 0.0%–27.8% |
| 单门框 | 完整几何（仅仿真对照） | 1.8%–40.4% |
| 错位双门框 | 原有输入（默认） | 1.8%–40.4% |
| 错位双门框 | 完整几何（仅仿真对照） | 5.7%–51.0% |

## 同 seed 对照

| 任务 | Seed | 原有输入 | 完整几何 | 双方均可评估 |
|---|---:|---|---|---|
| 单门框 | 0 | obstacle_collision | obstacle_collision | 是 |
| 单门框 | 1 | 响应校验失败 | 成功 | 是 |
| 单门框 | 2 | API 传输/服务中断 | API 传输/服务中断 | 否 |
| 单门框 | 3 | API 传输/服务中断 | API 传输/服务中断 | 否 |
| 单门框 | 4 | API 传输/服务中断 | API 传输/服务中断 | 否 |
| 单门框 | 5 | API 传输/服务中断 | API 传输/服务中断 | 否 |
| 单门框 | 6 | API 传输/服务中断 | API 传输/服务中断 | 否 |
| 单门框 | 7 | API 传输/服务中断 | API 传输/服务中断 | 否 |
| 单门框 | 8 | API 传输/服务中断 | API 传输/服务中断 | 否 |
| 单门框 | 9 | API 传输/服务中断 | API 传输/服务中断 | 否 |
| 错位双门框 | 0 | API 传输/服务中断 | API 传输/服务中断 | 否 |
| 错位双门框 | 1 | 响应校验失败 | 成功 | 是 |
| 错位双门框 | 2 | obstacle_collision | obstacle_collision | 是 |
| 错位双门框 | 3 | obstacle_collision | obstacle_collision | 是 |
| 错位双门框 | 4 | 成功 | 成功 | 是 |
| 错位双门框 | 5 | obstacle_collision | obstacle_collision | 是 |
| 错位双门框 | 6 | obstacle_collision | 响应校验失败 | 是 |
| 错位双门框 | 7 | 响应校验失败 | obstacle_collision | 是 |
| 错位双门框 | 8 | obstacle_collision | 响应校验失败 | 是 |
| 错位双门框 | 9 | obstacle_collision | 响应校验失败 | 是 |

- 单门框：2/10 对可评估；双方成功 0 对，仅完整几何成功 1 对，仅原有输入成功 0 对，双方失败 1 对。
- 错位双门框：9/10 对可评估；双方成功 1 对，仅完整几何成功 1 对，仅原有输入成功 0 对，双方失败 7 对。

## 失败证据与边界

碰撞部件和力由保存的终止物理状态重建，并核对与当时记录的总接触力一致。“发生在下降阶段”等描述是观测证据，不代表已隔离所有因果。

| 任务 | 输入 | Seed | 决策 | 终止原因与证据 |
|---|---|---:|---:|---|
| 单门框 | 原有输入（默认） | 0 | 120 | obstacle_collision; lower / x=zero, y=zero, z=negative, gripper=hold; gate ↔ link5 24.405 N >0.05 N |
| 单门框 | 完整几何（仅仿真对照） | 0 | 134 | obstacle_collision; lower / x=zero, y=zero, z=negative, gripper=hold; gate ↔ link5 73.153 N >0.05 N |
| 单门框 | 原有输入（默认） | 1 | 138 | policy_error; intent intent=lift，所选概率 0.49 < 最大概率 0.50；该次动作未执行 |
| 错位双门框 | 原有输入（默认） | 1 | 148 | policy_error; intent intent=lift，所选概率 0.36 < 最大概率 0.37；该次动作未执行 |
| 错位双门框 | 原有输入（默认） | 2 | 141 | obstacle_collision; lower / x=zero, y=zero, z=negative, gripper=hold; gate_2 ↔ link5 15.229 N >0.05 N |
| 错位双门框 | 完整几何（仅仿真对照） | 2 | 139 | obstacle_collision; lower / x=zero, y=zero, z=negative, gripper=hold; gate_2 ↔ link6 8.710 N >0.05 N |
| 错位双门框 | 完整几何（仅仿真对照） | 3 | 199 | obstacle_collision; approach / x=zero, y=zero, z=negative, gripper=open; gate_2 ↔ link5 68.459 N >0.05 N |
| 错位双门框 | 原有输入（默认） | 3 | 61 | obstacle_collision; lift / x=positive, y=zero, z=positive, gripper=hold; gate_1 ↔ link7 17.118 N >0.05 N |
| 错位双门框 | 完整几何（仅仿真对照） | 5 | 138 | obstacle_collision; lower / x=zero, y=zero, z=negative, gripper=hold; gate_2 ↔ link5 9.773 N >0.05 N |
| 错位双门框 | 原有输入（默认） | 5 | 58 | obstacle_collision; lift / x=positive, y=zero, z=positive, gripper=hold; gate_1 ↔ link7 4.013 N >0.05 N |
| 错位双门框 | 原有输入（默认） | 6 | 63 | obstacle_collision; lift / x=positive, y=zero, z=positive, gripper=hold; gate_1 ↔ hand 7.844 N >0.05 N |
| 错位双门框 | 完整几何（仅仿真对照） | 6 | 132 | policy_error; intent intent=lift，所选概率 0.49 < 最大概率 0.50；该次动作未执行 |
| 错位双门框 | 完整几何（仅仿真对照） | 7 | 129 | obstacle_collision; lower / x=zero, y=zero, z=negative, gripper=hold; gate_2 ↔ link7 29.293 N >0.05 N |
| 错位双门框 | 原有输入（默认） | 7 | 132 | policy_error; intent intent=lift，所选概率 0.49 < 最大概率 0.50；该次动作未执行 |
| 错位双门框 | 原有输入（默认） | 8 | 147 | obstacle_collision; lower / x=zero, y=zero, z=negative, gripper=hold; gate_2 ↔ link5 25.931 N >0.05 N |
| 错位双门框 | 完整几何（仅仿真对照） | 8 | 296 | policy_error; intent intent=lift，所选概率 0.49 < 最大概率 0.50；该次动作未执行 |
| 错位双门框 | 完整几何（仅仿真对照） | 9 | 137 | policy_error; intent intent=lift，所选概率 0.49 < 最大概率 0.50；该次动作未执行 |
| 错位双门框 | 原有输入（默认） | 9 | 65 | obstacle_collision; lift / x=positive, y=zero, z=positive, gripper=hold; gate_1 ↔ hand 6.268 N >0.05 N |

跨障碍时方块/TCP 的净空不等于整条机械臂的净空。单门框 seed 0 两组均在目标 XY 尚未对齐时下降，并发生 link5 碰柱。双门框原有输入 seed 3、5、6 在 `lift` 意图下同时向前和向上运动，撞到第一道门框；完整几何也存在第二道门框附近下降时的连杆碰撞。完整几何提供当前几何和距离，不提供候选动作的未来碰撞预测，也未增加全臂路径规划器或避障安全层。

## 输入与时间代价

下表按已结束试次统计请求大小，决策 API 延迟为 intent 与 motor 两阶段计时之和，包含重试。中断试次长短不同，这些均值不等于完成一个成功任务的成本。

| 任务 | 输入 | 每请求字节均值（按试次平均） | 每决策 API 中位数 ms | P95 ms |
|---|---|---:|---:|---:|
| 单门框 | 原有输入（默认） | 7018 | 1232 | 2407 |
| 单门框 | 完整几何（仅仿真对照） | 19587 | 1471 | 3552 |
| 错位双门框 | 原有输入（默认） | 8820 | 1304 | 2119 |
| 错位双门框 | 完整几何（仅仿真对照） | 25440 | 1645 | 2787 |

逐试次 token 用量、观测耗时与完整诊断保存在本地实验产物中，依照项目发布边界不上传原始请求、响应或用量审计。

## 原始试次录像

| 任务 | 输入 | 结果 | Seed | 视频 |
|---|---|---|---:|---|
| 错位双门框 | 完整几何（仅仿真对照） | 失败 | 2 | [MP4](media/observation/double_gate_pick_place-full_geometry-failure.mp4) |
| 错位双门框 | 完整几何（仅仿真对照） | 成功 | 1 | [MP4](media/observation/double_gate_pick_place-full_geometry-success.mp4) |
| 错位双门框 | 原有输入（默认） | 失败 | 2 | [MP4](media/observation/double_gate_pick_place-legacy-failure.mp4) |
| 错位双门框 | 原有输入（默认） | 成功 | 4 | [MP4](media/observation/double_gate_pick_place-legacy-success.mp4) |
| 单门框 | 完整几何（仅仿真对照） | 失败 | 0 | [MP4](media/observation/obstacle_pick_place-full_geometry-failure.mp4) |
| 单门框 | 完整几何（仅仿真对照） | 成功 | 1 | [MP4](media/observation/obstacle_pick_place-full_geometry-success.mp4) |
| 单门框 | 原有输入（默认） | 失败 | 0 | [MP4](media/observation/obstacle_pick_place-legacy-failure.mp4) |
| 单门框 | 原有输入（默认） | 成功 | — | 无自然成功录像 |

失败演示优先选择真实任务失败，再选响应校验或其他错误；同类取最小 seed。本轮七份录像均来自正式试次，失败录像均为自然碰撞。影片标注 `LEGACY / DEFAULT` 或 `FULL GEOMETRY / Simulation ablation only`，末尾有两秒结果静帧。播放使用仿真时间，省略 API 等待。

## 可支持的结论

在本轮小样本中，新增信息伴随部分试次结果变化，但没有消除整臂碰撞、意图/动作不一致或响应校验问题。单门框的可用配对尤其少，不能据此宣称完整几何普遍优于原有输入。正常复现继续使用原有输入；完整几何用于诊断信息不足是否可能参与失败，并作为后续独立实验的参考。

## API interruption retry (separate status)

The 18 slots classified as infrastructure interruptions in the original 40-trial comparison were resubmitted through `scripts/with_proxy.sh` and the hpc3 proxy bridge (Slurm job `647519`, retry job `4ab478783ebb4c7a9eead28c44495ce7`). The retry completed with 18/18 first-decision transport failures after three attempts per slot: no action executed, no physical failure occurred, and no recording was produced. It is not merged into the original 40 trials or the public 100-episode statistics. API transport errors, response-validation failures, and physical collisions remain separate categories.

A separate credentialed request using a captured first-decision payload raised `httpx.ReadError` before any HTTP response. Anonymous GET/POST probes reached the endpoint through the bridge (405/403), whereas bypassing the bridge produced a connection error. This narrows the failure to the credentialed request path but does not distinguish a proxy closure from a provider-side closure, and it does not establish whether the key is valid. No raw payload, response, key or proxy address is published.
