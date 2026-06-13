# 岛屿能源系统优化与气候韧性

基于混合整数线性规划(MILP)的岛屿能源系统韧性设计综合优化框架。该模型集成多能源系统与先进的可靠性建模和气候情景分析，为偏远岛屿的可持续能源规划提供支持。

*英文文档请参见 [README.md](README.md)*

---

## 🌊 概述

本项目实现了专门为面临气候变化挑战的岛屿社区设计的复杂能源系统优化模型(MILP)。该系统在确保极端天气条件下高可靠性的同时，优化集成电-热-冷能源网络的设计和运行。

### 核心特性
- **多能源集成**: 电力、供热、制冷系统的同步优化
- **气候韧性**: 基于风速和波高阈值的先进灾害建模
- **技术学习**: 纳入新兴技术的预期成本下降
- **可靠性分析**: 蒙特卡洛仿真与智能场景聚类
- **经济优化**: 包含CAPEX、OPEX和运行惩罚的总成本最小化

## 🏗️ 系统架构

### 能源技术(14种类型)

**可再生发电:**
- **WT (风力发电机)**: 陆上风力发电
- **PV (光伏发电)**: 太阳能发电
- **WEC (波浪能转换器)**: 海洋波浪能发电

**传统能源系统:**
- **LNG (液化天然气)**: 周期性采购的燃料储存
- **CHP (热电联产)**: 天然气热电联产机组

**能源转换:**
- **EB (电锅炉)**: 电力转热能
- **AC (空调系统)**: 电力转冷能
- **PEM (质子交换膜电解槽)**: 电解水制氢
- **FC (燃料电池)**: 氢气发电与废热利用
- **LNGV (LNG气化器)**: LNG气化与冷能回收

**储能系统:**
- **ESS (电储能系统)**: 电池储能
- **TES (热储能)**: 热水/蒸汽储存系统
- **CES (冷储能)**: 冷冻水储存系统
- **H2S (氢储能)**: 压缩氢气储存

### 可靠性建模

系统采用基于环境条件的复杂故障建模:

**设备故障概率:**
- **基于脆弱性曲线**

**维修约束:**
- 风电/光伏系统: 仅在风速≤20 m/s时可维修
- 波浪能系统: 需要风速≤20 m/s且波高≤2m
- 维修时间: WT/WEC(14天), PV(4天)

## 📊 情景分析

模型包含六个不同情景，代表不同的气候条件和技术成熟度水平:

| 情景文件 | 气候数据 | 技术成本 | 用途 | 输出目录 |
|----------|----------|----------|------|----------|
| `disaster_free.py` | 理想(无灾害) | 2020年当前 | 当前理想性能 | `output_0/` |
| `disaster_2020.py` | 2020年基线 | 2020年当前 | 当前基线性能 | `output_2020/` |
| `disaster_2050.py` | 2050年预测 | 2020年当前 | 当前技术下的气候影响 | `output_2050/` |
| `disaster_future_2030.py` | 2050年预测 | 2030年预测 | 早期技术采用效益 | `output_future_2030/` |
| `disaster_future_2040.py` | 2050年预测 | 2040年预测 | 中期技术成熟化 | `output_future_2040/` |
| `disaster_future_2050.py` | 2050年预测 | 2050年预测 | 完全技术学习效应 | `output_future_2050/` |

### 技术成本学习曲线

模型纳入关键技术的现实成本预测:

**氢能技术:**
- PEM电解槽: $1,120/kW → $915/kW → $748/kW (2020→2030→2050)
- 燃料电池: $2,000/kW → $1,800/kW → $1,600/kW (2020→2030→2050)

**储能技术:**
- 电池储能: $784/kWh → $686/kWh → $588/kWh (2020→2030→2050)

**固定成本:** 风电、光伏、LNG等成熟技术在各情景中保持恒定成本。

## 📋 系统要求

**操作系统:**

- Windows 10/11
- Linux (Ubuntu 20.04+, CentOS 8+)
- macOS 11+ (Big Sur或更高版本)

**Python:** >= 3.9 (已在3.9, 3.10, 3.11上测试)

**必需的Python包:**

*详见requirements.txt*
- pandas >= 1.3.0
- numpy >= 1.21.0
- xarray >= 0.19.0
- netCDF4 >= 1.5.7
- gurobipy >= 9.5.0
- scipy >= 1.7.0
- geopy >= 2.2.0
- pvlib >= 0.9.0
- timezonefinder >= 5.2.0
- scikit-learn >= 0.24.0
- openpyxl >= 3.0.9

**关键依赖:**

- Gurobi优化器 11.0+ 及有效许可证
- 下载: <https://www.gurobi.com/downloads/>
- 学术许可证: <https://www.gurobi.com/academia/academic-program-and-licenses/>

**硬件要求:**

- **推荐配置**: 32 GB内存, 16+核心CPU
- **存储空间**: 完整CMIP6数据需要70+ GB


## 🔧 安装

### 步骤1: 安装Python依赖

```bash
pip install -r requirements.txt
或
pip install pandas numpy xarray netCDF4 scipy geopy pvlib timezonefinder scikit-learn openpyxl gurobipy
```

### 步骤2: 配置Gurobi许可证

```bash
# 从 https://www.gurobi.com 获取许可证密钥
grbgetkey YOUR-LICENSE-KEY

# 验证安装
python -c "import gurobipy as gp; print(gp.gurobi.version())"
```

**预计安装时间**: 标准台式机上5-10分钟

**可选: 虚拟环境** (推荐)

```bash
# 使用conda
conda create -n island_env python=3.11
conda activate island_env

# 或使用venv
python -m venv island_env
source island_env/bin/activate  # Windows: island_env\Scripts\activate
```

## 🎯 快速入门演示

### 使用合成数据演示

为快速测试而无需下载大型CMIP6数据集，我们提供了合成气候数据生成。

**位置**: 所有演示文件位于 [`test/`](test/) 目录。详细说明请参见 [`test/test.md`](test/test.md)。

### 运行演示

**步骤1: 生成样本气候数据** (~30秒)

```bash
cd test
python create_sample_data.py
```

这将创建4个NetCDF文件(总计~2 MB)。

**步骤2: 运行理想情景测试** (~1分钟)

```bash
python disaster_free_test.py --island_lat 24.455253 --island_lon 122.988732 --pop 500
```

**步骤3: 运行基线情景测试** (~2分钟)

```bash
python disaster_2020_test.py --island_lat 24.455253 --island_lon 122.988732 --pop 500
```

### 预期演示输出

输出文件生成在 `test/output_sample/`:

1. **`*_best_cost_*.csv`** (8行): 系统成本分解
   - 年化投资、LNG成本、运维、运行惩罚
   - 预期总成本: 500人口的$100k-$500k

2. **`*_capacity_*.csv`** (14行): 最优技术容量
   - 可再生发电 (WT, PV, WEC)
   - 能源转换系统 (CHP, EB, AC, PEM, FC, LNGV)
   - 储能系统 (ESS, TES, CES, H2S)

3. **`*_results_*.csv`** (2,920行): 详细运行数据
   - 逐时发电量、储能状态、能源流
   - 供需平衡、削减负荷事件

### 演示运行时间

- **总计**: ~3分钟(取决于CPU核心数)
- **测试平台**: Intel i9-14900HX (24核心), 16 GB内存, Windows 11

详情请参见 [`test/test.md`](test/test.md)。

**关于完整研究的说明**: 手稿中发布的完整研究结果是在Linux高性能计算(HPC)集群上计算的，具有更强大的计算资源，能够高效计算数千个岛屿的多个气候情景。



## 📖 使用说明

### 数据目录结构

```
project_root/
├── demand/                         # 能源需求曲线
│   ├── demand_{lat}_{lon}.csv      # 逐时供热/制冷
│   ├── pv_{lat}_{lon}.csv          # 太阳能潜力
│   └── wt_{lat}_{lon}.csv          # 风能潜力
├── CMIP6/                          # 气候模型预测
│   ├── MRI_2020_uas/              # U风分量 (NetCDF)
│   ├── MRI_2020_vas/              # V风分量 (NetCDF)
│   ├── MRI_2050_uas/              # 未来预测
│   └── MRI_2050_vas/              # 未来预测
├── wave/                           # 波浪能数据
│   ├── wave_2020.nc               # 波浪能密度 (kW/m)
│   ├── waveheight_2020.nc         # 有效波高 (m)
│   ├── wave_2050.nc               # 未来波浪预测
│   └── waveheight_2050.nc         # 未来波高
└── LNG/
    └── LNG_Terminals.xlsx         # 全球LNG终端数据库
```

**数据格式要求:**

- **需求文件**: 带时间戳索引的CSV，列: heating_demand, cooling_demand
- **可再生潜力**: 带时间戳索引的CSV，列: electricity
- **气候数据**: NetCDF4格式，3小时时间分辨率，WGS84坐标
- **CMIP6数据访问**: 从ESGF门户下载

### 单岛优化

```bash
# 运行理想情景
python disaster_free.py --island_lat 25.5 --island_lon 120.0 --pop 1000
# 运行基线情景
python disaster_2020.py --island_lat 25.5 --island_lon 120.0 --pop 1000
# 运行当前技术下的气候压力情景
python disaster_2050.py --island_lat 25.5 --island_lon 120.0 --pop 1000
# 运行技术学习的未来情景
python disaster_future_2030.py --island_lat 25.5 --island_lon 120.0 --pop 1000
python disaster_future_2040.py --island_lat 25.5 --island_lon 120.0 --pop 1000
python disaster_future_2050.py --island_lat 25.5 --island_lon 120.0 --pop 1000
```

**命令行参数:**

- `--island_lat`: 纬度(十进制度数，WGS84)
- `--island_lon`: 经度(十进制度数，WGS84)
- `--pop`: 岛屿人口(缩放能源需求)

### 批量处理多个岛屿

创建CSV文件 `chosen_island.csv`:

```csv
island_name,latitude,longitude,population
Island_A,25.5,120.0,1000
Island_B,24.2,122.5,500
```

运行批处理:

```bash
chmod +x run_jobs_all.sh
nohup ./run_jobs_all.sh > logs/run_tasks.log 2>&1 &
```

### 修改模型参数

可在Python情景文件中调整关键参数:

| 参数 | 位置 | 描述 |
|------|------|------|
| 投资成本 | 第295-301行 | 技术CAPEX ($/kW 或 $/kWh) |
| 效率 | 第303-306行 | 转换/储能效率 |
| LNG定价 | 第310-313行 | 燃料成本、运输、固定租船 |
| 惩罚系数 | 第316-320行 | 弃能、削减负荷惩罚 |
| 维修时间 | 第333-335行 | 设备恢复持续时间 |
| 蒙特卡洛情景 | 第513行 | 故障情景数量(默认: 10,000) |
| 可靠性目标 | 第869行 | EENS限制(默认: 需求的0.1%) |

### 重现说明

重现手稿结果：

1. **准备可再生能源潜力和需求数据** 在 `demand_get/` 文件夹中，并从外部下载气候模型数据
   - 按照手稿"方法: 可再生潜力与需求评估 和 补充信息: 补充方法3"
   - 从ESGF门户下载CMIP6气候数据
     - 模型: MRI-AGCM3-2-S_highresSST
     - 变量: uas, vas (风分量)
     - 情景: SSP5-8.5

2. **运行优化代码** 在 `code/` 文件夹中
   - 为数据库中的所有岛屿执行情景脚本
   - 生成所有气候和技术情景的优化结果

3. **处理结果** 在 `result/` 文件夹中
   - 汇编各情景的优化输出
   - 计算汇总统计和性能指标

4. **可视化结果** 在 `visualization_checklist/` 文件夹中
   - 运行可视化脚本重现手稿图表
   - 脚本对应图表: `fig1_*.ipynb` → 图1, `fig2_*.ipynb` → 图2, 等

## ⚙️ 模型公式

### 目标函数
最小化系统年化总成本:

```
min: CAPEX年化 + OPEX固定 + LNG成本 + 弃能惩罚 + 削减负荷惩罚
```

**成本组成:**
- **投资成本**: 20年寿命期，5%贴现率年化
- **固定运维**: 与容量成比例的年度维护成本
- **LNG成本**: 采购 + 运输(基于距离) + 固定租船费
- **运行惩罚**: 可再生能源弃能、削减负荷、能量溢出

### 关键约束

**能源平衡(多能源):**
- 电力: 发电 + 储能放电 = 需求 + 转换负荷 + 储能充电
- 热能: EB + CHP热 + FC热 + TES放热 = 供热需求 + TES储热
- 冷能: AC + LNGV冷 + CES放冷 = 制冷需求 + CES储冷
- 氢气: PEM产氢 + H2S释放 = FC消耗 + H2S储存
- 天然气: LNGV气化 = CHP消耗

**可靠性要求:**
- 各能源载体的期望未服务能量(EENS) ≤ 总需求的0.1%

**储能运行:**
- 循环边界条件(结束状态 = 初始状态)
- 自放电损失: ESS/H2S(0.01%/小时), TES/CES(5%/小时)
- 功率限制: 充放电 ≤ 储能容量的25%

**LNG采购:**
- 每14天周期性采购(3小时分辨率下112个时间步)
- 灾害敏感: 极端天气期间不可采购
- 储存平衡与CHP及气化消耗

### 可靠性分析方法

**1. 蒙特卡洛仿真:**
- 生成10000个独立的设备故障情景
- 可再生技术的天气相关故障概率
- 具有天气约束的维修时间建模

**2. 情景缩减:**
- 提取统计特征: 总停机时间、最大连续故障、事件频率
- 使用轮廓系数自动选择聚类数的K-means聚类
- 选择最接近聚类中心的代表性情景

**3. 鲁棒优化:**
- 确保系统在所有代表性故障情景下的可靠性

## 📁 输出结构

### 目录组织
```
project_root/
├── output_0/              # 理想情景结果
├── output_2020/           # 基线情景结果
├── output_2050/           # 气候变化影响
├── output_future_2030/    # 早期技术采用(2030)
├── output_future_2040/    # 中期技术发展(2040)
├── output_future_2050/    # 成熟技术情景(2050)
└── logs/                  # 执行日志和错误跟踪
```

### 结果文件(每个岛屿)
**成本分析:**
- `{lat}_{lon}_best_cost.csv`: 完整成本分解(CAPEX、OPEX、燃料、惩罚)

**系统设计:**
- `{lat}_{lon}_capacity.csv`: 所有14种技术类型的最优容量

**运行结果:**
- `{lat}_{lon}_results.csv`: 2,920个时间步的详细运行数据，包括:
  - 各技术发电量
  - 储能充放电循环
  - 能源转换流量
  - 供需平衡
  - 削减负荷和弃能

### 性能监控
- `logs/main_log.log`: 气候情景详细执行日志
- `logs/main_future_log.log`: 技术情景执行日志
- `logs/gap_failure_islands.csv`: 超过1% MIP最优性间隙的岛屿

## 🔬 研究应用

### 气候韧性研究
- **影响评估**: 量化气候变化对能源系统性能的影响
- **适应规划**: 识别未来条件下的最优技术组合
- **风险分析**: 评估系统对极端天气事件的脆弱性

### 技术经济学
- **学习曲线分析**: 建模新兴技术成本下降的效益
- **投资时机**: 优化技术部署时间表
- **经济可行性**: 比较可再生能源与传统系统经济性

### 能源安全
- **可靠性增强**: 设计满足严格可用性要求的系统
- **燃料安全**: 通过本地可再生能源最小化对进口燃料的依赖
- **电网韧性**: 确保设备故障期间的稳定运行

### 政策支持
- **基础设施规划**: 支持长期能源基础设施投资
- **技术激励**: 评估促进可再生能源采用的政策
- **气候适应**: 指导韧性基础设施发展策略

---

## 📄 许可与引用

本项目为学术研究目的开发。使用该模型时，请引用相关出版物并确认综合气候和可靠性建模方法。

**技术联系**: 如有模型实施问题或合作机会。
