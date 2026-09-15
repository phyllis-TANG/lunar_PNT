# ROS Car 双车协同定位与 UWB 实施计划

**文档性质：设计与验证计划（非已完成实现）**
**版本基线：仓库当前 `main` 内容；计划日期：2026-09-15**

## 1. 目标、范围与成功定义

本增量把现有月面 PNT 研究问题收敛为一个可在两台 ROS 小车上执行的协同定位最小闭环：每车独立估计自身里程计，UWB 提供车间距离，后端联合估计两车相对状态，并在独立真值上评估。第一阶段不宣称 UWB 单独提供全局位置，也不把仿真结果表述为实车性能。

### 1.1 研究问题

在一辆车的局部里程计发生方向性退化、短时中断或漂移时，**单条双向 UWB 车间测距**在什么运动激励、量测质量和公共参考条件下，能够降低两车的相对位置误差？

### 1.2 MVP 验收指标

| 类别 | 必须报告 | 建议门槛（不是预先结论） |
| --- | --- | --- |
| 功能 | 两车命名空间隔离；时间戳、坐标系和 UWB 序列检查通过；rosbag 可重放 | 100% 必需 topic 在袋中存在 |
| 精度 | 每车 ATE/RPE、车间相对位置 RMSE、UWB range residual | 协同方案相对独立里程计的相对位置 RMSE 中位数改善 ≥ 20% |
| 稳健性 | 50/95 百分位、失败率、NLOS 分层结果 | 不以均值掩盖长尾；严重 NLOS 场景允许判定失败 |
| 实时性 | 端到端延迟、更新率、CPU | 后端 10 Hz 时 p95 延迟 < 100 ms |
| 复现性 | 固定配置、提交号、bag 清单、标定与随机种子 | 同一 bag 重放两次指标差异 < 1% |

门槛用于继续/停止决策，未满足时应报告无收益或不可辨识，而不是调整真值、时间同步或噪声参数制造提升。

## 2. 关键假设与可观测性边界

两车状态简化为平面位姿与速度偏置：

\[
\mathbf{x}_i=[x_i,y_i,\psi_i,\mathbf{b}_i],\quad
z_{12}=\|\mathbf{p}_1-\mathbf{p}_2\|+b_r+n_r.
\]

单个标量距离只约束两车连线方向，不能独立确定全局平移、全局航向，也不能在缺少运动激励时恢复完整相对位姿。因此 MVP 必须至少具备以下一种“规范固定”来源：首帧相对位姿先验、共享地图中的绝对位姿、固定 UWB 锚点或外部真值仅用于初始化。用于评测的真值不得在未声明时进入在线估计。

需显式审计：

1. 同速同向、静止、恒定基线等弱激励轨迹；
2. 两车交叉、绕行及基线方向变化的强激励轨迹；
3. UWB 天线杆臂与车体旋转中心不重合时的测距模型；
4. 时延/时钟偏差与几何误差的混淆；
5. NLOS 正偏差不能简单当作零均值高斯噪声。

## 3. 系统架构与 ROS 接口

建议以 ROS 2 Humble/Jazzy 可移植接口设计，实际发行版须在实验清单中冻结。所有 frame 遵循 REP-105 的 `map → odom → base_link` 语义；双车资源用命名空间隔离而不是复用同名全局 topic。

```text
/car1/sensors ──> /car1/local_odometry ─┐
                                        ├─> /cooperative_localizer ─> /car1|car2/cooperative/odometry
/car2/sensors ──> /car2/local_odometry ─┤                         └> /diagnostics
/uwb/range/car1_car2 ───────────────────┘
                      rosbag2 + independent ground truth ──> offline evaluator
```

### 3.1 最小 topic 合同

| Topic | 类型 | 频率目标 | frame / 语义 | QoS |
| --- | --- | ---: | --- | --- |
| `/<car>/imu/data` | `sensor_msgs/Imu` | 100–200 Hz | `<car>/imu_link` | sensor data / best effort |
| `/<car>/wheel/odometry` | `nav_msgs/Odometry` | 20–50 Hz | `<car>/odom` → `<car>/base_link` | keep last 10 |
| `/<car>/local/odometry` | `nav_msgs/Odometry` | 20–50 Hz | 同上，含协方差 | reliable |
| `/uwb/range/car1_car2` | 自定义 `RangeStamped` 或 `sensor_msgs/Range` | 5–20 Hz | 天线间距离，米 | reliable, depth 20 |
| `/<car>/cooperative/odometry` | `nav_msgs/Odometry` | 10–20 Hz | `<car>/map` → `<car>/base_link` | reliable |
| `/diagnostics` | `diagnostic_msgs/DiagnosticArray` | 1–10 Hz | 丢包、NLOS、残差、延迟 | reliable |

若使用自定义 `RangeStamped`，字段至少包括 `header.stamp`、`initiator_id`、`responder_id`、`range_m`、`variance_m2`、`quality`、`sequence` 和 `nlos_flag`。禁止用消息到达时间替代硬件量测时间。静态外参通过 `/tf_static` 发布；每车 frame 前缀固定为 `car1/`、`car2/`。

## 4. 分阶段实施

### Phase 0 — 台账与接口冻结（1 周）

- 冻结 ROS 发行版、DDS、主机时钟方案、UWB 固件和天线型号；建立设备序列号表。
- 录制 10 分钟空载 bag，验证 topic、单位、frame、时间单调性、序列丢失率。
- 定义 bag manifest（提交号、参数、地图、标定、操作者、场景标签）。

**门禁：** 自动接口检查通过，跨车时间偏移 p95 小于 5 ms；否则先修复采集链路。

### Phase 1 — 单车基线与标定（1–2 周）

- 分别标定轮径/轮距、IMU 零偏与 `base_link → uwb_link` 杆臂。
- 运行仅轮速、轮速+IMU 两个基线；不得提前加入 UWB。
- 用测量尺在 LOS 条件下覆盖 0.5–20 m，拟合常值偏置与方差；按距离留出测试点。

**门禁：** 基线可重复、协方差非零且量纲正确；UWB 校准残差和温漂有记录。

### Phase 2 — 离线协同后端（2 周）

- 首选滑窗因子图：两车各自里程计/IMU 因子 + UWB 距离因子 + 最小规范固定先验。
- 先实现高斯模型，再加入基于质量/NLOS 标志的门控与鲁棒核；保留无门控消融。
- 对时间偏移（0/5/10/20/50 ms）和杆臂误差做扫描。

**门禁：** 在仿真和实车 LOS bag 上残差方向、Jacobian 数值检查和重放确定性均通过。

### Phase 3 — 在线集成与故障注入（1–2 周）

- 组件化节点、参数 YAML、launch 与诊断；先影子运行，不接管底盘控制。
- 注入 UWB 丢包、NLOS 正偏、车 1 里程计中断、时间偏移和单车静止。
- 超阈值时降级到独立里程计，并发布原因与恢复条件。

**门禁：** 无崩溃、无 TF 环、在线/离线输出在容差内一致，降级可检测。

### Phase 4 — 独立测试与论文证据（1 周）

- 冻结参数后才运行未见过的路线、速度、光照/地形和 NLOS 测试集。
- 报告 bootstrap 置信区间、逐场景结果和失败案例；保留原始 bag 的校验和。
- 与“独立里程计”“事后 UWB 门控”“无鲁棒核”“不同先验”公平比较。

## 5. 实验矩阵

| 维度 | 水平 |
| --- | --- |
| 几何 | 并行恒距、交叉、领航-跟随、绕行、会合/分离 |
| 可见性 | LOS、人体遮挡、墙角/金属附近 NLOS |
| 里程计 | 正常、打滑、10 s/30 s 中断、航向漂移 |
| UWB | 5/10/20 Hz；随机丢包 0/10/30%；受控正偏 |
| 同步 | 标称、5/10/20/50 ms 人工偏移 |
| 后端 | 独立、普通最小二乘、鲁棒核、质量门控 |

每个条件至少 5 次独立运行；开发集用于调参，测试集仅在冻结后运行。核心指标用轨迹对齐方式、采样规则和时间窗口完整定义，并同时给出绝对与相对指标，避免仅报告最有利结果。

## 6. 风险、停止条件与安全

| 风险 | 监测 | 缓解 / 停止条件 |
| --- | --- | --- |
| 单距离不可辨识 | 滑窗信息矩阵秩、条件数 | 增加运动激励或合法先验；仍不可辨识则停止“完整相对位姿”主张 |
| NLOS 长尾 | quality、残差分位数、场景标签 | 门控/鲁棒核；若错误接受率过高则只报告 LOS 范围 |
| 时间不同步 | 硬件时间与到达时间差 | PTP/触发同步；p95 > 5 ms 不进入融合评测 |
| TF/杆臂错误 | 静态旋转与闭环路线 | 独立量测复核；不得靠调噪声吸收系统误差 |
| 在线跳变影响控制 | innovation、状态跳变、watchdog | 首轮仅影子模式；急停独立于 ROS 网络 |

## 7. 可复现交付物

计划完成后应新增（本次只交付计划、资料和演示稿）：`ros2_ws/src/uwb_msgs`、`cooperative_localization`、双车 launch/config、bag manifest/schema、接口与数值单元测试、回放集成测试以及指标生成脚本。大体积 bag 不进 Git，只提交许可、下载/采集说明、SHA-256 和小型脱敏 fixture。

引用编号与可访问入口见[参考资料导读](reference_materials.md)，BibTeX 数据见仓库根目录 [`references.bib`](../references.bib)。
