# ROS Car 双车协同定位参考资料导读

本页区分“接口规范”“方法依据”和“硬件资料”。链接用于设计复核；具体实现仍需固定 ROS 发行版、硬件修订版和访问日期。文献条目键与根目录 [`references.bib`](../references.bib) 一致。

## ROS、坐标与消息

1. **REP-105：移动平台坐标系约定**（`rep105`）
   <https://www.ros.org/reps/rep-0105.html>
   用于定义 `map`、`odom`、`base_link` 的连续性与全局/局部语义；双车通过 frame 前缀隔离。
2. **ROS 2 QoS 概念**（`ros2_qos`）
   <https://docs.ros.org/en/rolling/Concepts/Intermediate/About-Quality-of-Service-Settings.html>
   用于选择 IMU 的 sensor-data 配置和融合输出的可靠传输。Rolling 文档用于概念入口，实施时必须切换到冻结发行版页面。
3. **`nav_msgs/Odometry` 消息定义**（`nav_msgs_odometry`）
   <https://docs.ros.org/en/rolling/p/nav_msgs/msg/Odometry.html>
   明确 pose 所属 frame 与 twist 所属 child frame，避免双车 TF 语义混淆。
4. **`robot_localization` 状态估计节点**（`robot_localization`）
   <https://docs.ros.org/en/noetic/api/robot_localization/html/state_estimation_nodes.html>
   可作为单车 EKF 基线的接口参考；不是协同距离因子图的替代品。

## UWB 与协同定位

5. **IEEE 802.15.4z 标准**（`ieee802154z`）
   <https://standards.ieee.org/standard/802_15_4z-2020.html>
   UWB 增强测距的标准背景；购买/访问许可和具体芯片实现需另行确认。
6. **UWB 定位技术综述**（`alarifi2016uwb`）
   <https://doi.org/10.3390/s16050707>
   用于梳理 ToA/TDoA、误差来源和定位架构，不作为特定硬件精度保证。
7. **去中心化多机器人相对定位**（`ledergerber2015robot`）
   <https://doi.org/10.1109/IROS.2015.7353930>
   说明测距与运动信息结合的多机器人相对定位思路；本项目仍需单独验证双车、地面运动和传感器组合。
8. **因子图与 GTSAM**（`dellaert2017factor`）
   <https://doi.org/10.1561/2200000048>
   支持滑窗/因子图建模、非线性最小二乘和概率解释。
9. **鲁棒 M-estimation**（`huber1981robust`）
   <https://doi.org/10.1002/0471725250>
   支持 NLOS/异常值实验中的鲁棒核设计；仍须报告门控造成的拒绝率。

## 评测与工程核查建议

- 将 LOS 标定集、开发路线和最终测试路线分开，记录原始测距与质量字段。
- 对每个来源记录版本/访问日期；不要把芯片宣传页的典型值当作整车系统保证。
- 论文撰写前核对 DOI 元数据、标准修订状态与 ROS 发行版对应文档；本清单是工程起点，不是系统综述。
