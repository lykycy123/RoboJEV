# RoboJEV

<img src="site/media/banner.svg" alt="RoboJEV — State. Intent. Motion." width="100%">

**在 MuJoCo 中，通过两阶段 JEV 控制 Franka Panda 完成三种操作任务。**

[展示网站](https://lykycy123.github.io/RoboJEV/) · [English](README.md) · [评测报告](docs/evaluation.md)

JEV 不接收图像。程序将仿真的物体位姿、末端位姿、夹爪开度和接触关系转换为结构化状态；JEV 先选择意图，再选择 XYZ 方向及夹爪动作。控制器把方向转换成总长 1 cm 的位移，用 IK 和真实接触物理执行。

| 任务 | 行为与边界 | 演示 |
|---|---|---|
| 抓放 | 抓起方块，搬入目标区并释放 | [视频](site/media/pick_place.mp4) |
| 推移 | 用闭合夹爪推入目标区，禁止夹取或抬升；布局沿 +X 变化 | [视频](site/media/push.mp4) |
| 堆叠 | 将方块放到固定底座上，不是两个自由物体堆叠 | [视频](site/media/stack.mp4) |

视频概率来自真实 API 响应，按照仿真时间播放，省略 API 等待；视频长度不等于真实运行时间。规则策略仅用于独立对照，绝不代替 JEV 决策。

正式评测完成：抓放 JEV 10/10，规则 10/10；推移 JEV 10/10，规则 10/10；堆叠 JEV 8/10，规则 10/10。合计 60/60 轮，完整结果与置信区间见评测报告。

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

正式评测使用每任务种子 0–9、每策略 10 轮，共 60 轮；调试和演示使用独立种子。成功判据由物理评估器决定，失败不会被成功重跑覆盖。最新成绩、置信区间和失败说明见 [评测报告](docs/evaluation.md)。

项目仅支持 MuJoCo；不包含视觉感知、真实机器人部署或通用规划能力。公开仓库保留代码、配置、许可证、精选截图、压缩视频和脱敏成绩；完整日志、token 审计、计算集群信息、真实密钥和代理设置均不公开。

代码采用 Apache-2.0。MuJoCo、Panda 资产和 TypeSafe JEV 的来源见 [第三方说明](THIRD_PARTY.md)。本项目不宣称两阶段策略为原创方法。
