import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import geopandas as gpd
from shapely.geometry import Point
from pathlib import Path
from scipy import stats
from matplotlib.colors import LinearSegmentedColormap

# --- Nature 风格图表设置 ---
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial'],
    'font.size': 24,
    'axes.labelsize': 24,
    'axes.titlesize': 24,
    'xtick.labelsize': 20,
    'ytick.labelsize': 28,
    'legend.fontsize': 24,
    'figure.dpi': 300,
    'axes.linewidth': 1.2,
    'xtick.major.width': 1.2,
    'ytick.major.width': 1.2,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
})

def assign_ipcc_region(lat, lon, ipcc_regions_gdf):
    """将岛屿坐标分配到IPCC区域"""
    point = Point(lon, lat)
    possible_matches_index = list(ipcc_regions_gdf.sindex.intersection(point.bounds))
    possible_matches = ipcc_regions_gdf.iloc[possible_matches_index]
    precise_matches = possible_matches[possible_matches.contains(point)]
    if not precise_matches.empty:
        return precise_matches.iloc[0]['Acronym']
    return 'Unknown'

# --- 数据加载与处理 ---
# 路径锚定到脚本所在目录, 与运行时的工作目录无关
SCRIPT_DIR = Path(__file__).resolve().parent
data_path = SCRIPT_DIR / "../result/island_viability_summary_electric.csv"
df = pd.read_csv(data_path)
ipcc_regions = gpd.read_file(SCRIPT_DIR / "IPCC-WGI-reference-regions-v4.geojson")
df['ipcc_region'] = df.apply(
    lambda row: assign_ipcc_region(row['lat'], row['lon'], ipcc_regions),
    axis=1
)
MIN_ISLANDS_PER_REGION = 10  # 只保留岛屿数量超过10个的区域
region_counts = df['ipcc_region'].value_counts()
valid_regions = region_counts[region_counts >= MIN_ISLANDS_PER_REGION].index.tolist()

# 获取三种情景的数据：基准、气候压力和TP2050
df_ideal = df[(df['scenario'] == 'output_0') & (df['ipcc_region'].isin(valid_regions))].copy()  # 基准情景
df_climate = df[(df['scenario'] == 'output_2050') & (df['ipcc_region'].isin(valid_regions))].copy()  # 气候压力情景
df_tp2050 = df[(df['scenario'] == 'output_future_2050') & (df['ipcc_region'].isin(valid_regions))].copy()  # TP2050技术进步情景

# 合并数据计算偏移量
merged_climate = pd.merge(
    df_ideal[['island_id', 'tariff_breakeven', 'ipcc_region']],
    df_climate[['island_id', 'tariff_breakeven']],
    on='island_id',
    suffixes=('_ideal', '_climate')
)
merged_climate['cost_change'] = merged_climate['tariff_breakeven_climate'] - merged_climate['tariff_breakeven_ideal']
merged_climate['scenario_type'] = 'climate_stress'  # 标记为气候压力情景(output_2050)

merged_tp2050 = pd.merge(
    df_ideal[['island_id', 'tariff_breakeven', 'ipcc_region']],
    df_tp2050[['island_id', 'tariff_breakeven']],
    on='island_id',
    suffixes=('_ideal', '_tp2050')
)
merged_tp2050['cost_change'] = merged_tp2050['tariff_breakeven_tp2050'] - merged_tp2050['tariff_breakeven_ideal']
merged_tp2050['scenario_type'] = 'tp2050'  # 标记为TP2050技术进步情景(output_future_2050)

# 合并两种情景数据
merged_data = pd.concat([
    merged_climate[['island_id', 'ipcc_region', 'cost_change', 'scenario_type']],
    merged_tp2050[['island_id', 'ipcc_region', 'cost_change', 'scenario_type']]
], ignore_index=True)

merged_data['abs_change'] = abs(merged_data['cost_change'])
significant_changes = merged_data[merged_data['abs_change'] > 0.01]  # 只保留显著变化的岛屿
regions_with_changes = sorted(significant_changes['ipcc_region'].unique())

print(f"发现 {len(regions_with_changes)} 个有显著变化的IPCC区域: {regions_with_changes}")

# --- 绘图部分 ---
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 12), gridspec_kw={'width_ratios': [1.5, 1]})  # 增加图像宽度以容纳两种情景

# 定义基础颜色
climate_color = '#982B2D'  # 气候压力情景基础颜色（红色）
tp2050_color = '#1f77b4'  # TP2050情景基础颜色（蓝色）
outline_color = 'black'  # 所有轮廓线使用黑色


# === 左侧山脊图（ridge plot）===
all_changes = significant_changes['cost_change'].values
x_min, x_max = all_changes.min() - 0.02, all_changes.max() + 0.02  # X轴范围，左右各留0.02的边距
x_range = np.linspace(x_min, x_max, 500)  # 生成500个均匀分布的x值用于密度估计
ridge_height = 1.4  # 每个山脊的最大高度，控制密度峰的视觉突出程度
ridge_spacing = 1.5  # 山脊之间的垂直间距，影响整体布局的紧凑性

for i, region in enumerate(regions_with_changes):
    # 获取该区域的气候压力数据
    climate_data = significant_changes[
        (significant_changes['ipcc_region'] == region) &
        (significant_changes['scenario_type'] == 'climate_stress')
    ]['cost_change'].values

    # 获取该区域的TP2050数据
    tp2050_data = significant_changes[
        (significant_changes['ipcc_region'] == region) &
        (significant_changes['scenario_type'] == 'tp2050')
    ]['cost_change'].values

    y_offset = (len(regions_with_changes) - i - 1) * ridge_spacing

    # 绘制气候压力情景的密度分布
    if len(climate_data) > 1:
        kde_climate = stats.gaussian_kde(climate_data, bw_method=0.2)  # 核密度估计带宽
        density_climate = kde_climate(x_range)
        density_sqrt_climate = np.sqrt(density_climate)  # 开平方根使分布更平缓
        density_normalized_climate = density_sqrt_climate / density_sqrt_climate.max() * ridge_height  # 归一化到ridge_height

        # 填充气候压力密度峰（红色）
        ax1.fill_between(x_range, y_offset, y_offset + density_normalized_climate,
                         color=climate_color, alpha=0.8, linewidth=0)  # 填充透明度

        # 绘制密度轮廓（黑色）
        ax1.plot(x_range, y_offset + density_normalized_climate,
                 color=outline_color, linewidth=1.5, alpha=0.9)  # 轮廓线宽度和透明度
    elif len(climate_data) == 1:
        # 单个数据点用垂直线表示
        ax1.vlines(climate_data[0], y_offset, y_offset + ridge_height,
                  color=climate_color, linewidth=3, alpha=0.8)  # 单点线宽度

    # 绘制TP2050情景的密度分布
    if len(tp2050_data) > 1:
        kde_tp2050 = stats.gaussian_kde(tp2050_data, bw_method=0.2)  # 核密度估计带宽
        density_tp2050 = kde_tp2050(x_range)
        density_sqrt_tp2050 = np.sqrt(density_tp2050)  # 开平方根使分布更平缓
        density_normalized_tp2050 = density_sqrt_tp2050 / density_sqrt_tp2050.max() * ridge_height  # 归一化到ridge_height

        # 填充TP2050密度峰（蓝色）
        ax1.fill_between(x_range, y_offset, y_offset + density_normalized_tp2050,
                         color=tp2050_color, alpha=0.5, linewidth=0)  # 填充透明度

        # 绘制密度轮廓（黑色）
        ax1.plot(x_range, y_offset + density_normalized_tp2050,
                 color=outline_color, linewidth=1.5, alpha=0.9)  # 轮廓线宽度和透明度
    elif len(tp2050_data) == 1:
        # 单个数据点用垂直线表示
        ax1.vlines(tp2050_data[0], y_offset, y_offset + ridge_height,
                  color=tp2050_color, linewidth=3, alpha=0.8)  # 单点线宽度

    # 添加区域标签
    ax1.text(x_min - 0.025, y_offset + ridge_height/2, region,
             ha='right', va='center', fontsize=18)

# 设置左侧图的样式
# ax1.set_xlabel('Cost Recovery Price Change (USD kWh$^{-1}$)')
# 限制x轴显示范围，避免极端值影响可视化效果
x_display_min = max(x_min, -0.2)  # 左侧最小值限制，防止过度拉伸
x_display_max = min(x_max, 0.5)   # 右侧最大值限制，保持图表比例平衡
ax1.set_xlim(x_display_min - 0.02, x_display_max + 0.02)  # X轴显示范围，额外留0.02边距
ax1.set_ylim(-0.5, len(regions_with_changes) * ridge_spacing)  # Y轴范围，底部留-0.5边距
ax1.set_yticks([])  # 隐藏Y轴刻度，因为使用文本标签标识区域
ax1.grid(False)  # 关闭网格，保持简洁的视觉效果
ax1.spines['top'].set_visible(False)  # 隐藏上边框
ax1.spines['right'].set_visible(False)  # 隐藏右边框
ax1.spines['left'].set_visible(False)  # 隐藏左边框
ax1.axvline(x=0, color='black', linestyle='--', alpha=0.5, linewidth=1.2)  # 零值参考线，虚线样式

# === 右侧条形图（左右分离式）===
# 计算每个区域两种情景的岛屿总数
region_stats = []
for region in regions_with_changes:
    climate_region_data = significant_changes[
        (significant_changes['ipcc_region'] == region) &
        (significant_changes['scenario_type'] == 'climate_stress')
    ]
    tp2050_region_data = significant_changes[
        (significant_changes['ipcc_region'] == region) &
        (significant_changes['scenario_type'] == 'tp2050')
    ]

    n_climate = len(climate_region_data)  # 气候压力情景总岛屿数
    n_tp2050 = len(tp2050_region_data)    # TP2050情景总岛屿数

    region_stats.append({
        'region': region,
        'climate_total': n_climate,
        'tp2050_total': n_tp2050
    })

stats_df = pd.DataFrame(region_stats)

y_positions = [(len(regions_with_changes) - i - 1) * ridge_spacing + ridge_height/2
               for i in range(len(regions_with_changes))]
bar_height = ridge_height * 0.8  # 条形高度，适中大小

# 计算左右分离式条形图的最大值，用于设置X轴范围
max_value = max(stats_df['climate_total'].max(), stats_df['tp2050_total'].max())

# 绘制左右分离式条形图
for i, (y_pos, row) in enumerate(zip(y_positions, stats_df.itertuples())):
    # 绘制TP2050条形（蓝色，位于左侧，负方向）
    if row.tp2050_total > 0:
        ax2.barh(y_pos, -row.tp2050_total, height=bar_height,  # 负值放在左侧
                color=tp2050_color, alpha=0.9, edgecolor='black', linewidth=1.5, 
                label='TP2050' if i == 0 else "")  # 只在第一个添加图例

    # 绘制气候压力条形（红色，位于右侧，正方向）
    if row.climate_total > 0:
        ax2.barh(y_pos, row.climate_total, height=bar_height,  # 正值放在右侧
                color=climate_color, alpha=0.9, edgecolor='black', linewidth=1.5, 
                label='Climate Stress' if i == 0 else "")  # 只在第一个添加图例

    # 可选：添加数值标签
    # if row.tp2050_total > 0:
    #     ax2.text(-row.tp2050_total - 1, y_pos, str(row.tp2050_total),
    #             va='center', ha='right', fontsize=10)  # 蓝色条形左侧标签
    # if row.climate_total > 0:
    #     ax2.text(row.climate_total + 1, y_pos, str(row.climate_total),
    #             va='center', ha='left', fontsize=10)  # 红色条形右侧标签

# 设置右侧图的样式
ax2.set_ylim(-0.5, len(regions_with_changes) * ridge_spacing)  # Y轴范围与左图一致
ax2.set_yticks([])  # 隐藏Y轴刻度
ax2.grid(False)  # 关闭网格
ax2.spines['top'].set_visible(False)  # 隐藏上边框
ax2.spines['right'].set_visible(False)  # 隐藏右边框
ax2.spines['left'].set_visible(False)  # 隐藏左边框

# 设置X轴范围（左右对称）
x_limit = max_value * 1.2  # 留出一些边距
ax2.set_xlim(-x_limit, x_limit)  # 左右对称范围

# 添加零值参考线（中间的垂直线）
ax2.axvline(x=0, color='black', linestyle='-', alpha=0.8, linewidth=1.5)  # 零值线样式


# 最终调整与保存
plt.subplots_adjust(wspace=0.05)  # 子图间距，较小值使左右图更紧密
plt.savefig(SCRIPT_DIR / 'climate_stress_cost_analysis.png', dpi=300, bbox_inches='tight')  # 高分辨率保存，自动裁剪空白

# === 创建单独的图例图 ===
fig_legend, ax_legend = plt.subplots(figsize=(4, 1.5))  # 调整图例画布大小以容纳两个图例项
ax_legend.axis('off')
from matplotlib.patches import Rectangle

# 包含两种情景的图例项
legend_elements = [
    Rectangle((0, 0), 1, 1, facecolor=climate_color, alpha=0.8, label='Climate Stress'),
    Rectangle((0, 0), 1, 1, facecolor=tp2050_color, alpha=0.8, label='TP2050')
]
legend = ax_legend.legend(handles=legend_elements, loc='center', frameon=False, ncol=2, fontsize=18)
plt.savefig(SCRIPT_DIR / 'climate_stress_cost_reduction_legend.png', dpi=300, bbox_inches='tight')  # 更新文件名
plt.close(fig_legend)
# plt.show()


# === 打印统计信息 ===
print(f"\n=== 气候压力和TP2050相对于Ideal情景的成本变化统计 ===")
print(f"总共分析了 {len(regions_with_changes)} 个IPCC区域")

# 计算总体统计
total_climate = stats_df['climate_total'].sum()
total_tp2050 = stats_df['tp2050_total'].sum()

print(f"\n气候压力情景(output_2050)总岛屿数: {total_climate}")
print(f"TP2050技术进步情景(output_future_2050)总岛屿数: {total_tp2050}")

# 各区域详细统计
for _, row in stats_df.iterrows():
    print(f"\n{row['region']}:")
    print(f"   气候压力情景(output_2050): {row['climate_total']} 个岛屿")
    print(f"   TP2050技术进步情景(output_future_2050): {row['tp2050_total']} 个岛屿")
    