# Unreal MVP 第一次引擎内 smoke test 执行包

状态：**待在安装了 Unreal Engine 的本地机器执行**。本仓库云端环境未安装 `UnrealEditor`，因此没有引擎实测数据、完整校验通过报告或引擎行为回归结论。本目录只交付可放入工程的 C++ 组件、安装步骤和拒绝伪造证据的人工验收脚本。

## 基线与不可变边界

组件实现 `unreal-mvp-interface-v1` 的既有 `p_N=C_NU p_U/100` 和 `R_NB=C_NU R_UF C_FB`，同时保存 UE 原始输出；不修改接口来适配任何尚未核验的插件。卫星、钟和伪距继续留在 Unreal 外部。本轮不搭建月面场景。

## 安装

1. 建立一个空白 UE C++ 项目，关闭 Starter Content。
2. 将 `unreal/UnrealMvpSmoke` 复制到 `<Project>/Plugins/UnrealMvpSmoke`。
3. 重新生成工程文件并编译；启动编辑器后启用该插件。
4. 在空关卡放置一个简单 Cube/Pawn，并添加 `UnrealMvpSmokeExportComponent`。
5. Project Settings → General Settings：启用固定帧率，并使固定步长与组件 `FixedStepNanoseconds` 一致（建议 0.01 s）。不要用墙钟生成时间戳。
6. 将实际 Engine 完整版本、渲染/RHI、操作系统、固定步长和传感器插件名称/版本写入输出 `engine_config.json`；组件生成的 `sensor_plugin: not configured by exporter` 必须被真实配置替换。

## 传感器接线与真实性要求

- 组件只负责已知动作、原始 Actor CSV 和转换后 truth CSV。它**不会制造相机、深度、IMU 或 LiDAR 结果**。
- 双目和左深度必须由实际 SceneCapture/已选插件在同一仿真 tick 触发；RGB 必须是非空有效 PNG，深度必须是非空有效 EXR。
- IMU 必须记录插件原始 frame、单位、是否含重力及角速度定义。不能先假定角速度可以像极向量一样换手性。
- LiDAR 至少导出一帧真实 raycast/plugin 结果，含合法 `ring` 和扫描内 `time_offset_ns`。
- 若插件已经输出 ENU、FLU 或 optical frame，记录该事实并禁止再次转换。

最终目录应满足 `docs/unreal_mvp_interface.md`，另外包含 `raw/actor.csv` 和以下实际配置。运行：

```bash
python tools/check_unreal_engine_smoke.py /path/to/smoke_run --report /path/to/smoke_run/precheck_report.json
python tools/validate_unreal_dataset.py /path/to/smoke_run --scope complete --report /path/to/smoke_run/validation_report.json
```

只有两条命令都返回 0，并完成人工方向核对，才可以称为第一次引擎 smoke test 通过。文件存在和文件头合法仍不代表图像内容或深度单位已经正确。

## 已知动作与人工实测对照表

以下“预期”来自冻结接口；“实测”必须从 `raw/actor.csv`、编辑器视口及转换后 truth 填写，禁止预填为通过。

| 动作 | UE 命令轴（组件） | 接口下的具体预期 | 实测 UE 原始 | 实测 ENU/FLU | 状态 |
| --- | --- | --- | --- | --- | --- |
| 单位姿态/静止 | 初始 Actor quaternion | 车体 forward 指向 North；不是 ENU 单位姿态 | 待填 | 待填 | 待引擎实测 |
| 直线 | native `+X`, 1 m | North 增加 1 m，East 不变 | 待填 | 待填 | 待引擎实测 |
| `+90° yaw` | `FQuat(Up,+π/2)` | 必须用导出矩阵和已知方向确认，不凭 `FRotator` 名称判定 | 待填 | 待填 | 待引擎实测 |
| `+90° pitch` | `FQuat(Right,+π/2)` | 同上 | 待填 | 待填 | 待引擎实测 |
| `+90° roll` | `FQuat(Forward,+π/2)` | 同上 | 待填 | 待填 | 待引擎实测 |
| 时间 | frame index × fixed step | 整数 ns、严格递增；与各传感器 tick 对齐 | 待填 | 不适用 | 待引擎实测 |
| 双目 | 同 tick 捕获 | 左右 RGB 同时间戳、基线与标定一致 | 待填 | 待填 | 待引擎实测 |
| 深度 | 左目同 tick | 非空 EXR；抽查平面距离验证单位为 m | 待填 | 待填 | 待引擎实测 |
| LiDAR | 至少一真实 scan | ring 与逐点时间覆盖实际扫描区间 | 待填 | 待填 | 待引擎实测 |
| IMU | 插件原始输出 | 静止比力、旋转角速度及 frame 由独立解析值核对 | 待填 | 待填 | 待引擎实测 |

## 必须保留的未验证项

- UE 版本对应的旋转乘法语义及三个正旋转的视口方向；
- 插件是否改变相机、LiDAR、IMU 的 frame、单位或时间戳；
- 角速度作为轴向矢量的跨手性转换；
- fixed frame rate 下 tick、physics、SceneCapture 和插件回调的实际同步；
- RGB/EXR 内容、深度单位、曝光及 gamma；
- LiDAR ring 编号、扫描方向、逐点时刻和遮挡；
- IMU specific force、重力、bias/noise 开关和杆臂效应。

只针对上述表中**实际测得且有原始证据**的行为增加回归测试。当前不得把组件源代码的预期重复写成“引擎实测”。

## PR #6 冲突整理后的执行状态（2026-09-09）

主分支曾通过 PR #5 回退 PR #4。此分支为导出执行包恢复其依赖的坐标模块、合成样例及校验器，并保留此前修复：生成器不删除非空输出目录、校验器拒绝空文件/目录、矩阵转四元数保留 180° 混合轴的相对符号。C++ 转换函数同步采用最大分量分支；Python 测试通过不能替代 C++ 编译或引擎验证。

当前组件仍有明确的集成缺口：

- truth CSV 只含时间、位置和姿态，尚未输出接口必需的速度和角速度。因此组件单独输出不能通过完整 schema 校验；需实现这些字段并核验坐标及单位，不能填零占位。
- 时间戳是 frame index × 配置步长，尚未检查实际 Tick 的 DeltaTime、物理子步或传感器回调。规则间隔本身不能证明引擎同步正确。
- 相机、深度、LiDAR、IMU、标定元数据和外部导航表未由此组件提供。完整校验要求这些数据，不能仅运行组件便宣称 complete 通过。
- 三段旋转当前顺序累积；初始姿态取 Actor 的实际姿态。上表的单位姿态预期仅适用于初始旋转为零的 Actor，独立轴验收需分别重置初始姿态。
- 输出使用固定目录名并覆盖已有的自身输出文件；每轮本地测试必须配置新目录以保留原始证据。
- 预检脚本只检查部分结构与文件签名，不能证明动作数值正确、图像可解码或深度单位正确；仍须独立的方向、时间和已知距离验证。

下一轮先完成本地 UE 编译及“原始位姿 → ENU/FLU”短轨迹核对，补齐 truth 字段和实际时间验证，再逐个接入传感器并运行完整校验。当前没有新增 Unreal 实测结论、真实轨道、真实里程计融合或定位性能结果。
