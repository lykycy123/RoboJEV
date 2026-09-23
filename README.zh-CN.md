# RoboJEV

## 新增仿真任务

- **插销插孔 `peg_insert`**：直径 20 mm、长 60 mm 的插销插入直径 30 mm 的固定孔，径向余量 5 mm；插入至少 30 mm 后释放并稳定。近孔阶段采用 4 mm 动作，避免把任务设为过于精细的装配。
- **门框过障碍抓放 `obstacle_pick_place`**：抓取 40 mm 方块，在两根立柱之间越过 120 mm 高的横梁，门宽 70 mm；通过时底部净空至少 5 mm，机器人与物体不能碰撞门框，随后放入目标区。

每项任务固定种子 0–9，JEV 和独立规则基线各 10 次，共新增 40 轮。失败保留在分母，记录终止步骤、物理测量、违反的边界以及模型响应错误。结果见[新增任务评测报告](docs/challenge-evaluation.md)；原有三项任务的 60 轮结果保留原始版本来源。

| 新增任务 | JEV | 独立规则基线 |
|---|---:|---:|
| 宽松插销 | **10/10** | 10/10 |
| 跨障碍抓放 | **5/10** | 8/10 |

新增 40/40 轮已完成，与原有 60 轮合计 100 轮，两个批次分别保留冻结源码指纹。跨障碍 JEV 的失败：种子 0、9 在下降时机械臂 link5 碰门柱（44.00、26.59 N，阈值 0.05 N）；种子 1、8 持续请求错误方向，分别被拒绝 302、305 次后耗尽 350 次决策；种子 7 的 Y 选择概率 0.49 小于另一选项 0.50，校验拒绝执行。规则基线种子 0、4 也发生 link5 碰撞（17.39、15.03 N）。逐次证据和边界见报告。

[插销成功录像](site/media/peg_insert-success.mp4) · [跨障碍成功录像](site/media/obstacle_pick_place-success.mp4) · [跨障碍失败录像](site/media/obstacle_pick_place-failure.mp4)。插销全部成功，无自然失败录像；每项十次不足以推断普适成功率或极限尺寸。

```bash
robojev --task peg_insert --policy rule --seed 1000
robojev --task obstacle_pick_place --policy jev --seed 1000
python scripts/evaluate_suite.py --tasks peg_insert obstacle_pick_place --workers 4 --capture-video-state
python scripts/render_captured_episode.py runs/robojev-evaluation/RUN_ID
```

录像直接渲染正式回合中保存的物理状态，不重跑模型或物理轨迹。每项选择种子最小的成功和自然失败回合；若全部成功则注明无自然失败录像。末尾附带两秒结果静帧，播放省略 API 等待。下方演示展示按成功、失败两部分列出全部五个任务。

<img src="site/media/banner.svg" alt="RoboJEV — State. Intent. Motion." width="100%">

**在 MuJoCo 中，通过两阶段 JEV 控制 Franka Panda 执行五种操作任务。**

[展示网站](https://lykycy123.github.io/RoboJEV/) · [English](README.md) · [评测报告](docs/evaluation.md)

JEV 不接收图像。程序将仿真的物体位姿、末端位姿、夹爪开度和接触关系转换为结构化状态；JEV 先选择意图，再选择 XYZ 方向及夹爪动作。控制器把方向转换成通常总长 1 cm 的位移，插销近孔阶段为 4 mm，用 IK 和真实接触物理执行。

## 演示展示

### Part 1 — 成功演示

| 抓放 | 表面推移 | 固定底座堆叠 | 插销 | 跨障碍抓放 |
|:---:|:---:|:---:|:---:|:---:|
| [![抓放](site/media/pick_place.jpg)](https://lykycy123.github.io/RoboJEV/?task=pick_place&outcome=success#experiments)<br>[MP4](site/media/pick_place.mp4) · seed 1000 | [![表面推移](site/media/push.jpg)](https://lykycy123.github.io/RoboJEV/?task=push&outcome=success#experiments)<br>[MP4](site/media/push.mp4) · seed 1000 | [![固定底座堆叠](site/media/stack.jpg)](https://lykycy123.github.io/RoboJEV/?task=stack&outcome=success#experiments)<br>[MP4](site/media/stack.mp4) · seed 1000 | [![插销](site/media/peg_insert-success.jpg)](https://lykycy123.github.io/RoboJEV/?task=peg_insert&outcome=success#experiments)<br>[MP4](site/media/peg_insert-success.mp4) · seed 0 | [![跨障碍抓放](site/media/obstacle_pick_place-success.jpg)](https://lykycy123.github.io/RoboJEV/?task=obstacle_pick_place&outcome=success#experiments)<br>[MP4](site/media/obstacle_pick_place-success.mp4) · seed 2 |

### Part 2 — 失败演示

| 抓放 | 表面推移 | 固定底座堆叠 | 插销 | 跨障碍抓放 |
|:---:|:---:|:---:|:---:|:---:|
| 10/10 成功，无自然失败录像。 | 10/10 成功，无自然失败录像。 | 2/10 失败；原评测未录制失败视频。<br>[失败证据](docs/evaluation.md#response-validation-failure) | 10/10 成功，无自然失败录像。 | [![跨障碍抓放](site/media/obstacle_pick_place-failure.jpg)](https://lykycy123.github.io/RoboJEV/?task=obstacle_pick_place&outcome=failure#experiments)<br>[MP4](site/media/obstacle_pick_place-failure.mp4) · seed 0 |

上下两部分均按相同顺序展示五个任务。前三项成功录像使用独立演示种子；新增两项录像来自正式评测。堆叠使用固定底座，其两次响应校验失败在原评测中未录制视频，失败证据保留在报告中。视频按仿真时间播放，省略 API 等待，概率来自真实 API 响应。

原始三任务评测：抓放 JEV 10/10，规则 10/10；推移 JEV 10/10，规则 10/10；堆叠 JEV 8/10，规则 10/10。该版本合计 60/60 轮，完整结果与置信区间见评测报告。新增两项任务的 40 轮评测单独记录版本、失败边界与录像来源。

## 安装与运行

测试环境为 Linux、Python 3.11、MuJoCo 3.3.7；所有依赖使用统一的 `jev-vla-sim` 环境。CPU 物理和规则策略不需要 GPU 或 API 密钥。

```bash
git clone https://github.com/lykycy123/RoboJEV.git
cd RoboJEV
conda env create -f environment.yml
conda activate jev-vla-sim
pip install -e '.[test,video]'
python scripts/fetch_panda.py
robojev --task pick_place --policy rule --seed 1000
```

真实 JEV 需要 TypeSafe API 密钥，调用可能产生费用。复制 `.env.example` 到 `.env`，在本地编辑 `TYPESAFE_API_KEY`；真实配置不上传。模型调用期间暂停仿真。

```bash
robojev --task push --policy jev --seed 1000
robojev --task stack --policy jev --record-video
python scripts/evaluate_suite.py --workers 4
```

正式评测使用每任务种子 0–9、每策略 10 轮：原有三任务 60 轮，新增两任务 40 轮。调试使用独立种子；新增录像直接来自正式评测。成功判据由物理评估器决定，失败不会被成功重跑覆盖。最新成绩、置信区间和失败说明见 [评测报告](docs/evaluation.md)。

项目仅支持 MuJoCo；不包含视觉感知、真实机器人部署或通用规划能力。公开仓库保留代码、配置、许可证、精选截图、压缩视频和脱敏成绩；完整日志、token 审计、计算集群信息、真实密钥和代理设置均不公开。

代码采用 Apache-2.0。MuJoCo、Panda 资产和 TypeSafe JEV 的来源见 [第三方说明](THIRD_PARTY.md)。本项目不宣称两阶段策略为原创方法。
### 浏览器实验控制台

安装一次可选依赖后，可以在本地浏览器中配置和运行 RoboJEV，无需修改配置文件：

```bash
python -m pip install -e '.[ui]'
robojev-ui
# 打开 http://127.0.0.1:8767/
```

控制台支持六个任务，包括新增的错位双门框，以及规则策略或 JEV、配对批量实验、种子、并发数和原始状态捕获。**正常使用仍默认原有输入。** 完整几何依赖现实中难以完整获取的仿真特权信息，仅作为可选对照。“配置 40 次对照实验”可对两种门框任务分别比较两种输入，详见[实验协议](docs/observation-experiment.md)。

历史记录保存在被 Git 忽略的 `runs/ui/` SQLite 目录中；停止批次后已经完成的试次会保留。TypeSafe Key 默认只在本次会话使用，不会进入命令行或日志；勾选“Remember on this machine”后才会以严格权限写入用户私有配置文件。远程 Linux 服务器可使用 `ssh -N -L 8767:127.0.0.1:8767 user@host`，然后打开同一个本地地址。控制台只监听本机。

控制台需要 Linux 或 WSL2；当前验证的 MuJoCo 环境和离屏渲染使用 Linux 图形后端。物理计算不需要 GPU；录像生成需要可用的 EGL 或 OSMesa，若当前节点没有图形设备，可在 GPU 节点上从运行详情页重新生成。
