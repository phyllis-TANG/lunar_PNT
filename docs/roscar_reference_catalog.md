# ROS Car 双车协同定位资料目录

整理日期：2026-09-15。本目录服务于当前“两辆 ROS1 Melodic 小车 + 轮速/IMU/LiDAR + UWB”的地面验证。它不是完整综述，也不表示下列仓库已在本项目运行成功。

## 1. 本月必读与必用

| 资源 | 类型 | 当前用途 | 使用方式 |
| --- | --- | --- | --- |
| [Mourikis & Roumeliotis, Performance Analysis of Multirobot Cooperative Localization](https://doi.org/10.1109/TRO.2006.878957) | 基础论文 | 理解相对观测、观测图和不确定性增长；说明一条车间距离不能自动给出全局二维位姿 | 精读问题定义、假设和主要结论；写一页状态/观测/不可观自由度笔记 |
| [Wang et al., UWB-Based Localization for Multi-UAV and Multi-Robot Systems: a Survey](https://arxiv.org/abs/2004.08174) | UWB综述 | 比较 TWR/TDoA、固定基站与无基站协同定位、UWB与惯性/视觉/雷达融合 | 重点读测距模式、协同定位、NLoS和数据集部分 |
| [robot_localization Melodic 文档](https://docs.ros.org/en/melodic/api/robot_localization/html/index.html) | ROS实现文档 | 完成每辆车的轮速+IMU独立定位基线 | 为两车建立独立YAML；记录输入变量、协方差、频率和坐标系 |
| [REP-103](https://www.ros.org/reps/rep-0103.html) / [REP-105](https://www.ros.org/reps/rep-0105.html) | ROS标准 | 统一单位、轴向、`map/odom/base_link` 与多车TF | 形成项目自己的话题和TF约定表 |
| [GTSAM](https://github.com/borglab/gtsam) | 开源估计库 | 实现二维里程计因子和车间距离因子的最小离线原型 | 先运行 `Pose2` 示例，再写两个机器人、少量时刻的合成测试 |
| [evo](https://github.com/MichaelGrupp/evo) | 开源评价工具 | 统一 APE/ATE、RPE、轨迹关联和画图 | 固定命令、对齐方法和时间阈值，生成CSV与图片 |

## 2. UWB接入、标定与鲁棒处理

### 设备驱动候选：必须先按硬件型号选择

| 仓库 | 适用条件 | 结论 |
| --- | --- | --- |
| [TIERS/ros-dwm1001-uwb-localization](https://github.com/TIERS/ros-dwm1001-uwb-localization) | Decawave/Qorvo DWM1001-DEV，ROS1/catkin，设备使用默认RTLS/UART接口 | 若硬件一致，可优先借鉴串口解析、节点ID和距离话题；不要在型号未确认前安装 |
| [linorobot/ros_dwm1000](https://github.com/linorobot/ros_dwm1000) | DWM1000、Arduino固件、固定基站三边定位 | 可参考锚点TF和距离阈值设计；代码较旧，不能视为即插即用 |
| [ntu-aris/uwb_driver](https://github.com/ntu-aris/uwb_driver) | Humatics/PulsON P440 或读取 NTU VIRAL 消息 | 适合借鉴消息定义与数据集接口，不适用于其他UWB硬件驱动 |
| [aau-cns/uwb_init](https://github.com/aau-cns/uwb_init) | 需要估计UWB锚点位置，ROS1 | 第二阶段再用；本月先采用已知位置或人工测量基站 |

### 论文

| 论文 | 借鉴点 | 本项目对应实验 |
| --- | --- | --- |
| [Zhu & Kia, Decentralized Cooperative Localization With LoS and NLoS UWB Inter-Agent Ranging](https://doi.org/10.1109/JSEN.2021.3083724) | NLoS产生正偏差，LoS/NLoS不能总用同一高斯模型；文中使用偏差补偿和多模型估计 | LoS、人体遮挡、车体遮挡分别统计；先做门限/稳健权重，再决定是否需要复杂模型 |
| [Song et al., UWB/LiDAR Fusion for Cooperative Range-Only SLAM](https://arxiv.org/abs/1811.02854) | 把UWB节点和LiDAR测量放进共同估计问题；说明局部几何与无线距离可互补 | 后期比较“独立LiDAR/地图定位”与“加入UWB距离因子”，不要求本月复现全文系统 |
| [Fusing Odometry, UWB Ranging, and Spatial Detections for Relative Multi-Robot Localization](https://arxiv.org/abs/2304.06264) / [代码](https://github.com/TIERS/uwb-cooperative-mrs-localization) | 里程计+UWB+协同视觉检测的相对定位，以及公开的粒子滤波/ROS2原型 | 仅借鉴相对状态定义、输入输出和实验对比；当前ROS1项目不直接移植整个仓库 |

## 3. 公开数据集

| 数据集 | 传感器与特点 | 优先级 | 本项目用途和限制 |
| --- | --- | --- | --- |
| [LUCOOP](https://data.uni-hannover.de/dataset/lucoop-leibniz-university-cooperative-perception-and-urban-navigation-dataset) | 三车、LiDAR、IMU、GNSS、V2V/V2X UWB、高精度参考轨迹与3D地图 | A：主数据 | 最接近双车UWB协同结构；先选两车最小片段。道路车辆、GNSS与本项目轮式小车不同 |
| [NTU VIRAL](https://github.com/ntu-aris/ntu_viral_dataset) | ROS bag、双相机、多IMU、双3D LiDAR、多UWB、激光跟踪真值与标定 | B：辅助 | 适合检查多源接口、标定、UWB+惯性/激光融合；无人机平台且单序列数GB |
| [UTIAS MR.CLAM](https://asrl.utias.utoronto.ca/datasets/mrclam/) | 多地面机器人、里程计、相对观测与真值 | B：教学辅助 | 适合从简单观测模型验证协同定位；不是UWB、传感器配置较旧 |
| [S3E](https://pengyu-team.github.io/S3E/) | 多机器人、多模态、LiDAR/相机/IMU/UWB/RTK，ROS2 bag | C：后期 | 适合协同SLAM和昼夜/退化场景；ROS2与系统规模超出本月范围 |
| [MILUV](https://www.decar.ca/miluv/) | 多无人机UWB、视觉、IMU、CIR和动捕真值，附Python开发工具 | C：后期 | 适合研究原始UWB质量与视觉辅助；不是地面车辆，且不用于ROS1双车首版 |
| [Kimera-Multi-Data](https://github.com/MIT-SPARK/Kimera-Multi-Data) | 多机器人视觉、深度、IMU rosbag | C：后期 | 适合后续协同视觉SLAM；当前没有UWB主线需求时不下载 |

数据集使用顺序：页面与论文 → README/许可 → 最小样本 → 字段和标定表 → 一组基线 → 再决定是否下载完整数据。禁止同时处理多套大型数据造成工作分散。

## 4. 后期协同SLAM与视觉定位

| 资源 | 能学到什么 | 当前处理 |
| --- | --- | --- |
| [COVINS](https://github.com/v4rl-ucy/covins) | 集中式协同视觉惯性SLAM、前端/服务器后端、跨机器人回环与地图融合 | 阅读系统架构；待双车基础定位稳定且有相机后再评估 |
| [Kimera-Multi](https://github.com/MIT-SPARK/Kimera-Multi) | 分布式多机器人度量—语义SLAM、鲁棒跨机器人回环 | 阅读分布式设计和鲁棒性；不用于首版UWB距离融合 |
| [CCNY imu_tools](https://github.com/CCNYRoboticsLab/imu_tools) | Madgwick/互补滤波与IMU可视化 | 当底层IMU不提供可信姿态时评估；不能替代IMU噪声标定 |
| [imu_utils](https://github.com/gaowenliang/imu_utils) | 基于Allan方差估计IMU白噪声与随机游走 | 需要较长静止数据；输出参数仍需结合估计器与实车测试检查 |

## 5. 月球与Unreal迁移参考

| 资源 | 用途 | 与当前双车工作的连接 |
| --- | --- | --- |
| [McKee, A Survey of Autonomous Navigation Techniques Applicable to Lunar Surface Exploration](https://ntrs.nasa.gov/api/citations/20250000720/downloads/Lunar_Surface_Nav_Survey_AAS_GNC_011825.pdf?attachment=true) | 月面局部/全局导航、VO、IMU、轮速、LiDAR、地形相对导航与通信/PNT背景 | 用来说明地面双车只是传感器融合与协同定位验证，不等同月面验证 |
| [LuPNT](https://github.com/Stanford-NavLab/LuPNT) | 开源月球PNT、轨道、伪距/多普勒、钟差、IMU、相机、LOLA DEM和滤波示例 | 后期用其生成有物理依据的月球测距，不用任意“造卫星位置” |
| [LunarNav](https://arxiv.org/abs/2301.01350) | 基于陨石坑的长距离全局定位 | 对应未来 DEM/陨石坑全局校正，不应与当前UWB协同定位混为一项任务 |
| [PUTvision/LunarSim](https://github.com/PUTvision/LunarSim) | 高视觉真实度、ROS2连接的月球车视觉仿真 | 可借鉴月面场景、传感器和数据生成；其ROS2接口需要与当前ROS1路线分开 |
| [HERCULES](https://github.com/lunarlab-gatech/HERCULES) | Unreal Engine 5 多机器人仿真、ROS2接口和协同感知/SLAM架构 | 适合负责Unreal的同学阅读场景—机器人—传感器—ROS桥接结构；不是现成月球PNT系统 |

## 6. 推荐阅读顺序

1. REP-103、REP-105、`robot_localization`：先把两辆车各自的状态与坐标系讲清楚。
2. Mourikis & Roumeliotis：理解“协同定位提供了什么、仍缺什么绝对约束”。
3. UWB综述与LUCOOP论文/README：确定设备模式、消息字段和实验设计。
4. UWB LoS/NLoS论文：完成标定和遮挡实验，而不是先训练分类器。
5. GTSAM的Pose2与RangeFactor：先做合成离线原型，再读取rosbag。
6. NTU VIRAL或MR.CLAM二选一：交叉检查代码，不追求一次兼容所有数据。
7. COVINS/Kimera-Multi、LuPNT、LunarSim/HERCULES：双车首版完成后再进入视觉协同与月球迁移。

## 7. 每篇论文和仓库的记录模板

```text
标题/仓库：
版本或 commit：
ROS/Ubuntu/依赖：
许可证：
研究状态与观测：
坐标系和时间假设：
噪声、偏差和异常值模型：
真值与评价指标：
可直接复用的接口/代码：
不能迁移到本项目的假设：
本项目运行状态：未检查 / 已阅读 / 已编译 / 已回放 / 已实车验证
```

只把实际读过或运行过的内容写进PPT结论；其他资源标记为“参考架构”或“计划评估”。
