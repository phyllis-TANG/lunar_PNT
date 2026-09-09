# 针对性文献证据矩阵

审计日期：2026-09-08。

## 证据规则与访问状态

本矩阵只把能够定位到全文页码、章节、公式、表格、图或官方数据说明具体字段的内容记为“直接证据”。找不到证据时写“未报告”，不根据常见做法补造状态、先验或噪声模型。

本轮建立的是**文献证据审计框架**，不是已经完成的文献审计。运行环境可访问 GitHub API/Raw，但对 PMC、arXiv、NASA NTRS 和 DOI 出版站的全文请求均由网络代理返回 HTTP 403，Web 浏览工具返回 HTTP 401。因此七项指定来源中，本轮只直接取得并核查了 **LuSNAR 官方仓库的论文配套说明**；其余六项未取得可分页全文，下面保留待核字段并明确标为“全文待核”，而不把摘要或题名扩写成证据。这个限制意味着本文件尚不能用于宣称研究空白。

## 汇总矩阵

| 来源 | 本轮证据载体 | 观测与传感器 | 状态、钟与先验 | 几何、时间窗与退化 | 评价与主要结果 | 数据/代码 | 与候选问题的重合 | 仍待解决的空间 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Degeneration-Aware Localization with Arbitrary Global-Local Sensor Fusion | 指定 [PMC 全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC8230883/) 未能下载；全文待核 | 由题名可知涉及 global/local sensor fusion；具体观测类型、LiDAR/IMU/轮速组合：**未报告（待全文核）** | 是否含原始伪距、接收机钟差/钟漂和初始先验：**未报告** | 退化方向定义、检测量、窗口：**未报告** | 绝对位置或相对位移、基线与数值：**未报告** | 代码/数据：**未报告** | “退化感知全局—局部融合”概念直接重合，必须优先排除重复 | 未核实其 arbitrary global sensor 是否覆盖带钟 nuisance state 的原始稀疏 range；不能据此声称空白 |
| Factor Graph Fusion of Raw GNSS Sensing with IMU and Lidar for Precise Robot Localization without a Base Station | 指定 [arXiv 全文](https://arxiv.org/abs/2209.14649) 未能下载；全文待核 | 题名直接支持 raw GNSS、IMU、LiDAR 与 factor graph；伪距/多普勒/载波具体组合：**未报告** | 接收机钟状态、过程模型与初始先验：**未报告** | 卫星数量、几何与窗口：**未报告** | 绝对/相对指标、基线与结果：**未报告** | 数据/代码：**未报告** | 原始 GNSS—IMU—LiDAR 因子建模和融合实现高度重合，不能把模块组合当贡献 | 是否研究局部弱方向与钟边缘化后的有限窗口收益预测：待全文核 |
| Single-Satellite Lunar Navigation via Doppler Shift Observables for the NASA Endurance Mission | 指定 [Navigation DOI](https://doi.org/10.33012/navi.710) 未能下载；全文待核 | 题名直接支持**单星月球多普勒**；不能外推为伪距或载波结果 | 状态、钟漂、星历和先验：**未报告** | 单星、Endurance 场景由题名支持；积累时长和几何：**未报告** | 指标与数值：**未报告** | 代码/数据：**未报告** | 稀疏月球观测与时间积累直接相关，但观测类型不同 | 伪距—钟差—里程计弱方向的结论不能借用其多普勒结果；需全文核对可观测性假设 |
| Digital Lunar Exploration Sites Unreal Simulation Tool (DUST) | 指定 [NASA NTRS PDF](https://ntrs.nasa.gov/api/citations/20220014707/downloads/DUST_IEEE2023Paper.pdf) 未能下载；全文待核 | Unreal 地形、车辆与传感器具体输出：**未报告** | 不适用或未报告卫星钟状态 | 场景范围、路线、光照、岩石程序化参数：**未报告** | 仿真验证与数值：**未报告** | 工具公开性与许可：**未报告** | 与 Unreal 场景和传感器输出直接相关 | 坐标、时间、元数据和外部伪距接口不能在未读全文时声称兼容 DUST；本轮接口采用显式项目约定 |
| LuSNAR | [arXiv](https://arxiv.org/abs/2407.06512) PDF 未能下载；核查了[官方仓库说明](https://github.com/zqyu9/LuSNAR-dataset)的 “Key Features”“Dataset Statistics”“Sensor Specifications”“Data Format” | 双目 RGB/深度 10 Hz；128 线旋转 LiDAR 10 Hz；IMU 100 Hz；真值位姿。仓库说明 “Key Features”、 “Sensor Specifications” | `Rover_pose.txt` 声明位置、四元数、速度、陀螺/加计 bias 字段；接收机钟：**未报告**。仓库说明 “Data Format” | 九个 Unreal 场景；LiDAR 360° 水平、-25° 至 +27° 垂直、≤30 m。导航窗口/退化方向：**未报告** | 仓库列出语义分割和三维重建基线；SLAM 绝对/相对指标详细数值：**未报告（待论文核）** | 仓库与数据入口公开；仓库标注 MIT，但同时要求商业用途联系作者，实际使用前需核许可文本 | 可复用传感器字段和场景分层；不包含本项目外部稀疏伪距/钟模型 | 点云公开格式只列 `x y z category_id`，逐点时间、ring、外参和时钟域需下载样本核查 |
| Challenges of SLAM in Extremely Unstructured Environments: The DLR Planetary Stereo, Solid-State LiDAR, Inertial Dataset | 指定 [arXiv 全文](https://arxiv.org/abs/2207.06815) 未能下载；全文待核 | 题名支持 stereo、solid-state LiDAR、inertial；具体型号/频率：**未报告** | 接收机钟不属于题名范围；传感器同步/初始化：**未报告** | 极端无结构环境由题名支持；退化检测定义：**未报告** | SLAM 指标与数值：**未报告** | 数据入口/许可：**未报告（待全文核）** | 可提供真实类行星里程计困难，但不是月面实测或卫星融合证据 | 是否有独立真值、逐点时间及足够长方向退化窗口必须通过样本审计 |
| The S3LI Vulcano Dataset | 指定 [arXiv 全文](https://arxiv.org/abs/2601.19557) 未能下载；全文待核 | 观测类型、传感器型号与字段：**未报告** | 同步、外参和初始化：**未报告** | Vulcano 采集范围、路线与退化：**未报告** | 基线与结果：**未报告** | 数据/代码/许可：**未报告** | 可能是 S3LI 的更新数据说明，但与 2022 工作的增量关系尚未核实 | 必须先核对版本关系、真值、许可和实际下载字段，不能把两篇 S3LI 工作混为一套已验证数据 |

## LuSNAR 可直接定位的配套说明证据

以下定位指官方仓库 README 的章节标题，而不是论文页码：

- “Key Features”：1024×1024 双目图像、10 Hz、310 mm baseline；LiDAR 与 IMU/pose 的名义提供情况。
- “Dataset Statistics”：九场景、约 108 GB；图像、点云、IMU 和真值的名义频率/规模。
- “Sensor Specifications”：相机 80°×80° FOV、焦距 610.17784 px；128 线 LiDAR、10 Hz、360° 水平 FOV、-25° 至 +27° 垂直 FOV、≤30 m；IMU 100 Hz。
- “Data Format”：LiDAR 文本 `x y z category_id`；`Rover_pose.txt` 与 `IMU.txt` 的声明字段。

这些证据只能冻结 Unreal MVP 的**候选输出兼容字段和频率**，不能证明 LuSNAR 传感器噪声、真值精度或 SLAM 退化适用于现实月球任务。

## 针对候选问题的暂时判断

### 有直接证据支持

1. 最近工作题目层面已经覆盖退化感知全局—局部融合、原始 GNSS/IMU/LiDAR 因子融合和单星月球多普勒导航；因此“融合”“退化感知”或“单星时间积累”本身不能作为创新声明。
2. LuSNAR 的官方配套说明提供了可复用的合成双目、深度、LiDAR、IMU 和真值字段及名义频率，但没有报告接收机钟或月球卫星观测。

### 尚不能确认

- 是否已有工作把带接收机钟 nuisance state 的原始稀疏伪距与 LiDAR 弱方向放在同一有限窗口内评价；
- 是否已有指标预测“加入某组稀疏 range 后的实际边际误差收益”；
- 指定月球多普勒论文中的钟漂、星历、初始状态和时间积累条件；
- DUST、S3LI 2022 和 S3LI Vulcano 的精确输出、许可、坐标和实验数值。

因此，**创新性门禁仍未通过**。取得六篇缺失全文并补齐页码/公式/表图定位之前，不应把本矩阵写成完整综述，也不应开始围绕所谓研究空白扩建算法。
