# 改进版回归分析:使用成本回收电价下降率作为因变量

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.preprocessing import StandardScaler
import seaborn as sns
from scipy import stats
from statsmodels.stats.outliers_influence import variance_inflation_factor
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['axes.unicode_minus'] = False

print("\n" + "="*80)
print("改进版回归分析:能源成本结构对技术进步收益的影响(使用成本回收电价下降率)")
print("="*80)

# 加载实际数据
try:
    # 读取详细成本数据
    df_cost_base = pd.read_csv('../result/island_cost_summary_2050.csv')  # Climate Stress情景
    df_cost_compare = pd.read_csv('../result/island_cost_summary_future_2050.csv')  # TP2050情景

    # 读取成本回收电价数据
    df_viability = pd.read_csv('../result/island_viability_summary_electric.csv')
    df_viability_2050 = df_viability[df_viability['scenario'] == 'output_2050'].copy()
    df_viability_future = df_viability[df_viability['scenario'] == 'output_future_2050'].copy()

    print(f"成本基础数据形状: {df_cost_base.shape}")
    print(f"可行性数据形状: {df_viability.shape}")

    # 成本组成部分列表
    cost_components = [
        'renewable_cost_per_capita',
        'storage_cost_per_capita',
        'lng_cost_per_capita',
        'other_equipment_cost_per_capita',
        'discard_cost_per_capita',
        'load_shedding_cost_per_capita'
    ]

    # 创建岛屿ID(基于经纬度)
    df_cost_base['island_key'] = df_cost_base['lat'].astype(str) + '_' + df_cost_base['lon'].astype(str)
    df_cost_compare['island_key'] = df_cost_compare['lat'].astype(str) + '_' + df_cost_compare['lon'].astype(str)
    df_viability_2050['island_key'] = df_viability_2050['lat'].astype(str) + '_' + df_viability_2050['lon'].astype(str)
    df_viability_future['island_key'] = df_viability_future['lat'].astype(str) + '_' + df_viability_future['lon'].astype(str)

    # 合并成本数据
    cost_merged = pd.merge(
        df_cost_base[['island_key', 'lat', 'lon'] + cost_components],
        df_cost_compare[['island_key'] + cost_components],
        on='island_key',
        suffixes=('_base', '_compare')
    )

    # 合并成本回收电价数据
    tariff_merged = pd.merge(
        df_viability_2050[['island_key', 'tariff_breakeven']],
        df_viability_future[['island_key', 'tariff_breakeven']],
        on='island_key',
        suffixes=('_base', '_compare')
    )

    # 合并所有数据
    merged_data = pd.merge(cost_merged, tariff_merged, on='island_key')

    print(f"成功匹配的岛屿数量: {len(merged_data)}")

except FileNotFoundError as e:
    print(f"错误:找不到数据文件 {e}")
    merged_data = pd.DataFrame()
except Exception as e:
    print(f"数据加载出错:{e}")
    merged_data = pd.DataFrame()

if len(merged_data) > 0:
    # --- 1. 数据预处理:计算成本占比 ---
    print("正在计算成本占比...")

    # 计算基础情景下总成本
    merged_data['total_cost_base'] = merged_data[[f'{comp}_base' for comp in cost_components]].sum(axis=1)

    # 计算各成本组成部分占比(%)
    merged_data['renewable_pct'] = (merged_data['renewable_cost_per_capita_base'] / merged_data['total_cost_base']) * 100
    merged_data['storage_pct'] = (merged_data['storage_cost_per_capita_base'] / merged_data['total_cost_base']) * 100
    merged_data['lng_pct'] = (merged_data['lng_cost_per_capita_base'] / merged_data['total_cost_base']) * 100
    merged_data['other_pct'] = (merged_data['other_equipment_cost_per_capita_base'] / merged_data['total_cost_base']) * 100
    merged_data['discard_pct'] = (merged_data['discard_cost_per_capita_base'] / merged_data['total_cost_base']) * 100
    merged_data['load_shedding_pct'] = (merged_data['load_shedding_cost_per_capita_base'] / merged_data['total_cost_base']) * 100

    # 计算成本回收电价下降率(%)
    merged_data['tariff_reduction_pct'] = ((merged_data['tariff_breakeven_base'] - merged_data['tariff_breakeven_compare']) /
                                           merged_data['tariff_breakeven_base']) * 100

    # 筛选有显著变化的岛屿
    significant_mask = merged_data['tariff_reduction_pct'] > 0.0
    cost_merged = merged_data[significant_mask].copy()

    print(f"有显著成本回收电价下降的岛屿数量: {len(cost_merged)}")

    # --- 2. 回归分析 ---
    X_vars = ['renewable_pct', 'storage_pct', 'lng_pct']
    X = cost_merged[X_vars].copy()
    y = cost_merged['tariff_reduction_pct']

    # 检查数据有效性
    valid_mask = ~(X.isnull().any(axis=1) | y.isnull())
    X_clean = X[valid_mask]
    y_clean = y[valid_mask]

    print(f"\n有效样本数:{len(X_clean)}")

    # 标准化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_clean)

    # 回归建模
    model = LinearRegression()
    model.fit(X_scaled, y_clean)

    # 预测
    y_pred = model.predict(X_scaled)
    r2 = r2_score(y_clean, y_pred)
    mse = mean_squared_error(y_clean, y_pred)

    print(f"\n回归结果:")
    print(f"R2 = {r2:.4f}")
    print(f"RMSE = {np.sqrt(mse):.4f}")

    # 系数分析
    coefficients = pd.DataFrame({
        '变量': X_vars,
        '系数': model.coef_,
        '重要性': np.abs(model.coef_)
    }).sort_values('重要性', ascending=False)

    print(f"\n回归系数(按重要性排序):")
    print(coefficients[['变量', '系数', '重要性']].round(4))

    # --- 3. 统计显著性检验 ---
    n = len(X_clean)
    k = len(X_vars)
    df = n - k - 1

    mse_model = np.sum((y_clean - y_pred)**2) / df
    X_with_intercept = np.column_stack([np.ones(len(X_scaled)), X_scaled])
    cov_matrix = mse_model * np.linalg.inv(X_with_intercept.T @ X_with_intercept)
    std_errors = np.sqrt(np.diag(cov_matrix)[1:])

    t_stats = model.coef_ / std_errors
    p_values = 2 * (1 - stats.t.cdf(np.abs(t_stats), df))

    significance_results = pd.DataFrame({
        '变量': X_vars,
        '系数': model.coef_,
        '标准误': std_errors,
        't统计量': t_stats,
        'p值': p_values,
        '显著性': ['***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else '' for p in p_values]
    })

    print(f"\n统计显著性:")
    print(significance_results.round(4))
    print("\n显著性水平: *** p<0.001, ** p<0.01, * p<0.05")

    # --- 4. 共线性诊断 ---
    print(f"\n" + "="*80)
    print("共线性诊断")
    print("="*80)

    # 计算相关性矩阵
    corr_matrix = X_clean.corr()
    print("\n自变量相关系数矩阵:")
    print(corr_matrix.round(3))

    # 计算方差膨胀因子(VIF)
    print("\n方差膨胀因子(VIF)分析:")
    vif_data = pd.DataFrame()
    vif_data["变量"] = X_clean.columns
    vif_data["VIF"] = [variance_inflation_factor(X_clean.values, i) for i in range(len(X_clean.columns))]
    print(vif_data)
    print("\n注: VIF > 10 表示存在严重共线性, VIF > 5 表示存在中度共线性")

    # 可视化共线性诊断
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5), dpi=300)

    # 相关性热力图
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
    sns.heatmap(corr_matrix, mask=mask, annot=True, fmt='.3f', cmap='RdYlBu_r',
                center=0, square=True, linewidths=.5, cbar_kws={"shrink": .8}, ax=ax1)
    ax1.set_title('Correlation Matrix of Independent Variables', fontsize=14, fontweight='bold')

    # VIF柱状图
    colors_vif = ['red' if vif >= 10 else 'orange' if vif >= 5 else 'green' for vif in vif_data['VIF']]
    bars = ax2.bar(range(len(vif_data)), vif_data['VIF'], color=colors_vif, alpha=0.7, edgecolor='black')
    ax2.set_xlabel('Variables', fontsize=12, fontweight='bold')
    ax2.set_ylabel('VIF Value', fontsize=12, fontweight='bold')
    ax2.set_title('Variance Inflation Factor (VIF) Analysis', fontsize=14, fontweight='bold')
    ax2.set_xticks(range(len(vif_data)))

    var_labels = []
    for var in vif_data['变量']:
        if var == 'renewable_pct':
            var_labels.append('Renewable')
        elif var == 'storage_pct':
            var_labels.append('Storage')
        elif var == 'lng_pct':
            var_labels.append('LNG')
        elif var == 'total_cost_base':
            var_labels.append('Total Cost')
        else:
            var_labels.append(var.replace('_pct', ''))

    ax2.set_xticklabels(var_labels, rotation=45, ha='right')
    ax2.axhline(y=10, color='red', linestyle='--', alpha=0.7, linewidth=1.5, label='Severe (VIF=10)')
    ax2.axhline(y=5, color='orange', linestyle='--', alpha=0.7, linewidth=1.5, label='Moderate (VIF=5)')
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3, axis='y')

    # 添加VIF数值标注
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 0.2,
                f'{height:.1f}', ha='center', va='bottom', fontsize=10)

    plt.tight_layout()
    plt.savefig('multicollinearity_diagnostics.png', dpi=300, bbox_inches='tight')
    plt.close()

    print("\n共线性诊断图已保存: multicollinearity_diagnostics.png")

    # --- 5. Nature风格可视化 ---
    fig, ax = plt.subplots(1, 1, figsize=(12, 6), dpi=300)
    plt.rcParams['font.family'] = 'Arial'
    plt.rcParams['font.size'] = 24

    coef_data = coefficients.copy()
    coef_data = coef_data.sort_values('重要性', ascending=True)

    clean_labels = []
    for var in coef_data['变量']:
        if var == 'renewable_pct':
            clean_labels.append('Renewable Energy')
        elif var == 'storage_pct':
            clean_labels.append('Energy Storage')
        elif var == 'lng_pct':
            clean_labels.append('LNG')
        elif var == 'total_cost_base':
            clean_labels.append('Total Cost Baseline')
        else:
            clean_labels.append(var.replace('_pct', ''))

    colors = ['#0B75B3' if x > 0 else '#982B2D' for x in coef_data['系数']]

    bars = ax.barh(range(len(coef_data)), coef_data['系数'],
                   color=colors, alpha=0.9, edgecolor='black', linewidth=1.2)

    ax.set_yticks(range(len(coef_data)))
    ax.set_yticklabels(clean_labels, fontsize=20)
    ax.set_xlabel('Regression Coefficient (β)', fontsize=24)
    ax.tick_params(axis='x', labelsize=24)
    ax.axvline(x=0, color='black', linestyle='-', alpha=0.8, linewidth=1.5)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(1.5)
    ax.spines['bottom'].set_linewidth(1.5)

    plt.tight_layout()
    plt.savefig('tariff_reduction_regression_nature_style.png',
                dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"\n图表已保存: tariff_reduction_regression_nature_style.png")

else:
    print("错误:未找到数据")