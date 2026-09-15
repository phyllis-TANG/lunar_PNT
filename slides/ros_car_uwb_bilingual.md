---
title: ROS Car 双车协同定位与 UWB 计划 / Dual-Robot Cooperative Localization with UWB
format: 16:9 PowerPoint
status: Design and validation plan—not an implementation claim
date: 2026-09-15
---

# 1. 目标 / Objective
- 中文：用两车自身里程计与车间 UWB 距离，验证协同约束能否在退化时降低相对定位误差。
- English: Combine per-robot odometry with inter-robot UWB ranges and test whether cooperation reduces relative error under degradation.
- 成功不是“总会更准”；无收益与不可辨识也是有效结论。
- Success is not guaranteed improvement; no-benefit and unobservable cases are valid outcomes.

# 2. 研究边界 / Scope
- 中文：MVP 聚焦两台地面 ROS 小车、平面运动、单条车间测距与独立真值评测。
- English: The MVP targets two ground robots, planar motion, one inter-robot range, and independent ground truth.
- 中文：第一阶段不接管控制，不声称 UWB 单独提供全局位置。
- English: Phase 1 runs in shadow mode and does not claim that UWB alone provides global position.

# 3. 可观测性 / Observability
- 中文：一个距离只约束两车连线方向；全局平移和全局航向存在规范自由度。
- English: One range constrains only the baseline direction; global translation and yaw remain gauge freedoms.
- 中文：需要首帧相对先验、共享地图或固定锚点之一，并需要改变基线方向的运动激励。
- English: Use an initial relative prior, shared map, or fixed anchor, plus motion that changes baseline direction.

# 4. 数据流 / Data Flow
- 中文：车 1 与车 2 各自产生轮速、IMU 和局部里程计；UWB 节点发布带硬件时间戳的距离。
- English: Each robot produces wheel/IMU/local odometry; UWB publishes hardware-timestamped ranges.
- 中文：协同后端输出两车位姿、残差与健康状态；rosbag2 保存全部输入和独立真值。
- English: The backend outputs both poses, residuals, and health; rosbag2 records inputs and independent ground truth.

# 5. ROS 接口 / ROS Interfaces
- `/<car>/imu/data` · `sensor_msgs/Imu` · 100–200 Hz
- `/<car>/local/odometry` · `nav_msgs/Odometry` · 20–50 Hz
- `/uwb/range/car1_car2` · `RangeStamped` · 5–20 Hz
- `/<car>/cooperative/odometry` · `nav_msgs/Odometry` · 10–20 Hz
- 中文/English：`car1/`、`car2/` frame 前缀；REP-105 `map → odom → base_link`。

# 6. UWB 标定 / UWB Calibration
- 中文：测量 `base_link → uwb_link` 杆臂；LOS 下覆盖 0.5–20 m，分离校准点与测试点。
- English: Measure the antenna lever arm; cover 0.5–20 m LOS and separate calibration from test points.
- 中文：保存偏置、方差、温度、质量字段和 NLOS 标签；不把宣传典型值当系统保证。
- English: Record bias, variance, temperature, quality, and NLOS labels; do not treat marketing typicals as guarantees.

# 7. 融合后端 / Fusion Backend
- 中文：滑窗因子图 = 每车里程计/IMU 因子 + UWB 距离因子 + 最小规范固定先验。
- English: Sliding-window graph = per-robot odometry/IMU factors + UWB range factors + a minimal gauge prior.
- 中文：先高斯基线，再比较鲁棒核与质量门控，并保留全部消融。
- English: Start with a Gaussian baseline, then compare robust loss and quality gating with full ablations.

# 8. 分阶段路线 / Phased Roadmap
- P0（1 周/week）：接口、版本、时钟与 bag 台账 / freeze interfaces, versions, clocks, bags
- P1（1–2 周/weeks）：单车基线、杆臂与 UWB 标定 / single-robot baselines and calibration
- P2（2 周/weeks）：离线因子图、Jacobian 与重放 / offline graph, Jacobians, replay
- P3（1–2 周/weeks）：在线影子模式与故障注入 / online shadow mode and fault injection
- P4（1 周/week）：参数冻结后的独立测试 / held-out testing after parameter freeze

# 9. 实验矩阵 / Experiment Matrix
- 几何 / Geometry：并行、交叉、跟随、绕行、会合 / parallel, crossing, following, orbiting, rendezvous
- 可见性 / Visibility：LOS、人体遮挡、墙角/金属 NLOS
- 故障 / Faults：打滑、10/30 s 中断、0–30% 丢包、正偏、5–50 ms 时差
- 后端 / Backends：独立、普通最小二乘、鲁棒核、质量门控
- 重复 / Repeats：每条件至少 5 次 / at least five runs per condition

# 10. 指标与门禁 / Metrics & Gates
- 中文：ATE/RPE、相对位置 RMSE、range residual、50/95 分位数、失败率与 p95 延迟。
- English: ATE/RPE, relative-position RMSE, range residual, 50/95 percentiles, failure rate, and p95 latency.
- 建议继续门槛 / Proposed go gate：相对 RMSE 中位数改善 ≥20%；10 Hz 后端 p95 <100 ms。
- 时间门禁 / Timing gate：跨车时间偏移 p95 <5 ms；否则不进入融合评测。

# 11. 风险与降级 / Risks & Degradation
- 不可辨识 / Unobservable → 增加激励或合法先验；收窄主张 / add excitation or a valid prior; narrow claims
- NLOS 长尾 / NLOS tails → 门控、鲁棒核、分层报告 / gate, robustify, stratify
- TF/杆臂错误 / TF-lever-arm error → 独立复核；不靠调噪声掩盖 / independently verify; never hide with noise tuning
- 在线跳变 / Online jump → 影子模式、watchdog、退回独立里程计 / shadow mode, watchdog, fall back

# 12. 交付与下一步 / Deliverables & Next Steps
- 当前 / Now：计划、参考资料、BibTeX、双语 PPT / plan, reading guide, BibTeX, bilingual deck
- 后续 / Next：ROS 2 packages、消息、launch/config、bag schema、测试与评测脚本
- 中文：先通过 Phase 0 时间与接口门禁，再编写融合后端。
- English: Pass Phase 0 timing and interface gates before building the fusion backend.
- 参考 / References：REP-105; IEEE 802.15.4z; Alarifi et al. (2016); Ledergerber et al. (2015); Dellaert & Kaess (2017)
