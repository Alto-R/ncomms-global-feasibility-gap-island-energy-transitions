import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.pyplot as plt
import seaborn as sns
import os
from scipy import stats
from sklearn.preprocessing import StandardScaler

# 切换到脚本所在目录，使所有相对路径（../result 等）不依赖启动时的工作目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

for _d in ('pdf', 'svg', 'png'):
    os.makedirs(_d, exist_ok=True)


def get_significance_stars(p_value):
    """根据p值返回显著性星号"""
    if p_value < 0.001:
        return '***'
    elif p_value < 0.01:
        return '**'
    elif p_value < 0.05:
        return '*'
    else:
        return ''


def set_axis_scientific(ax):
      ax.ticklabel_format(style='sci', axis='both', scilimits=(0, 0), useMathText=True)
      ax.xaxis.offsetText.set_fontsize(24)  # 增大科学计数法字体
      ax.xaxis.offsetText.set_fontfamily('Arial')
      ax.yaxis.offsetText.set_fontsize(24)  # 增大科学计数法字体
      ax.yaxis.offsetText.set_fontfamily('Arial')

def get_cost_variable_names():
    """
    定义六种能源成本类型的变量名映射
    Returns a dictionary mapping original cost names to display names and other variants
    """
    cost_mapping = {
        # 原始变量名作为key，包含显示名称和简化名称
        'Log Renewable Cost': {
            'display_name': 'Renewable Generation Cost',
            'short_name': 'RGC',
            'original_name': 'Renewable Cost',
            'color': '#4C72B0'
        },
        'Log Storage Cost': {
            'display_name': 'Energy Storage System Cost',
            'short_name': 'ESC',
            'original_name': 'Storage Cost',
            'color': '#009988'
        },
        'Log LNG Cost': {
            'display_name': 'Conventional Generation Cost',
            'short_name': 'CGC',
            'original_name': 'Conventional Cost',
            'color': '#808080'
        },
        'Log Other Equipment Cost': {
            'display_name': 'Sector-Coupling System Cost',
            'short_name': 'SCC',
            'original_name': 'Other Equipment Cost',
            'color': '#8172B3'
        },
        'Log Discard Cost': {
            'display_name': 'Penalty Cost of Curtailment',
            'short_name': 'CEC',
            'original_name': 'Discard Cost',
            'color': '#d47d49'
        },
        'Log Load Shedding Cost': {
            'display_name': 'Cost of Unserved Energy',
            'short_name': 'CUE',
            'original_name': 'Load Shedding Cost',
            'color': '#C44E52'
        }
    }
    return cost_mapping
      
def run_island_energy_cost_analysis():
    """
    对岛屿能源系统的成本进行全面的回归分析和多重共线性检验。
    This function performs a comprehensive regression analysis and multicollinearity check for island energy system costs.
    """
    # --- 0. 环境设置 (Environment Setup) ---
    sns.set(style="white", rc={'figure.dpi': 600})  # 使用white样式避免网格线

    # 获取成本变量名映射
    cost_mapping = get_cost_variable_names()

    # --- 1. 数据加载与预处理 (Data Loading and Preprocessing) ---
    print("开始加载和处理数据 (Starting to load and process data)...")

    cost_summary_path = '../result/island_cost_summary_0.csv'
    if not os.path.exists(cost_summary_path):
        print(f"错误: 成本汇总文件未找到 '{cost_summary_path}'。请检查路径。")
        return
    cost_df = pd.read_csv(cost_summary_path)

    island_data = []

    for idx, island in cost_df.iterrows():
        lat, lon = island['lat'], island['lon']

        # --- 加载需求数据 ---
        demand_file = f'../demand_get/data/get1/demand_{lat}_{lon}.csv'
        if not os.path.exists(demand_file):
            print(f"警告: 未找到岛屿 ({lat}, {lon}) 的需求文件，跳过该岛屿。")
            continue
        demand_df = pd.read_csv(demand_file)
        
        # --- NEW: Calculate Demand Fluctuations ---
        demand_datetime_series = pd.date_range(start='2020-01-01', periods=len(demand_df), freq='3h')
        demand_df['month'] = demand_datetime_series.month

        # Heating Demand Total and Seasonal Variation (CV方法)
        heating_demand_total = demand_df['heating_demand'].sum()
        h_monthly_mean = demand_df.groupby('month')['heating_demand'].mean()
        h_monthly_mean_filtered = h_monthly_mean[h_monthly_mean > 0.01]
        heating_demand_seasonal = h_monthly_mean_filtered.std() / h_monthly_mean_filtered.mean() if len(h_monthly_mean_filtered) >= 2 and h_monthly_mean_filtered.mean() > 0 else 0

        # Cooling Demand Total and Seasonal Variation (CV方法)
        cooling_demand_total = demand_df['cooling_demand'].sum()
        c_monthly_mean = demand_df.groupby('month')['cooling_demand'].mean()
        c_monthly_mean_filtered = c_monthly_mean[c_monthly_mean > 0.01]
        cooling_demand_seasonal = c_monthly_mean_filtered.std() / c_monthly_mean_filtered.mean() if len(c_monthly_mean_filtered) >= 2 and c_monthly_mean_filtered.mean() > 0 else 0
        
        # --- 加载可再生能源输出数据 ---
        output_file = f'../result/output_0/{lat}_{lon}_results.csv'
        if not os.path.exists(output_file):
            print(f"警告: 未找到岛屿 ({lat}, {lon}) 的能源输出文件，跳过该岛屿。")
            continue
        
        output_df = pd.read_csv(output_file)
        num_steps = len(output_df)
        datetime_series = pd.date_range(start='2020-01-01', periods=num_steps, freq='3h')
        output_df['month'] = datetime_series.month
        output_df['dayofyear'] = datetime_series.dayofyear # For daily fluctuation calculation

        # 计算各可再生能源的总量和季节性/日度变化
        renewables = {'wind': 'WT', 'pv': 'PV', 'wave': 'WEC'}
        renewable_stats = {}

        for name, col in renewables.items():
            if col in output_df.columns and not output_df[col].empty:
                total_utilization = output_df[col].sum()

                # Seasonal Variation (变异系数方法 - Coefficient of Variation)
                monthly_mean = output_df.groupby('month')[col].mean()
                monthly_mean_filtered = monthly_mean[monthly_mean > 0.01]  # 过滤掉发电量很小的月份

                if len(monthly_mean_filtered) >= 2:
                    seasonal_variation = monthly_mean_filtered.std() / monthly_mean_filtered.mean()
                else:
                    seasonal_variation = 0

                # Daily Fluctuation (变异系数CV的平均值 - Coefficient of Variation)
                daily_mean = output_df.groupby('dayofyear')[col].mean()
                daily_std = output_df.groupby('dayofyear')[col].std()
                # 避免除零错误，只计算平均值大于0.1的天数的变异系数
                valid_days = daily_mean > 0.1
                daily_cv = daily_std[valid_days] / daily_mean[valid_days]
                daily_fluctuation = daily_cv.mean() if not daily_cv.empty else 0
                
            else:
                total_utilization, seasonal_variation, daily_fluctuation = 0, 0, 0

            renewable_stats[f'{name}_total'] = total_utilization
            renewable_stats[f'{name}_seasonal'] = seasonal_variation  # 变异系数方法
            renewable_stats[f'{name}_daily'] = daily_fluctuation

        # 汇总该岛屿的所有数据
        island_data.append({
            'lat': lat, 'lon': lon,
            'Heating Demand': heating_demand_total, 'Heating Demand Variation': heating_demand_seasonal,
            'Cooling Demand': cooling_demand_total, 'Cooling Demand Variation': cooling_demand_seasonal,
            'Total Wind Utilization': renewable_stats['wind_total'], 'Wind Seasonal Variation': renewable_stats['wind_seasonal'], 'Wind Daily Fluctuation': renewable_stats['wind_daily'],
            'Total PV Utilization': renewable_stats['pv_total'], 'PV Seasonal Variation': renewable_stats['pv_seasonal'], 'PV Daily Fluctuation': renewable_stats['pv_daily'],
            'Total Wave Utilization': renewable_stats['wave_total'], 'Wave Seasonal Variation': renewable_stats['wave_seasonal'], 'Wave Daily Fluctuation': renewable_stats['wave_daily'],
            'Renewable Cost': island['renewable_cost_per_capita'], 'Storage Cost': island['storage_cost_per_capita'],
            'Electrical Storage Cost': island['electrical_storage_cost_per_capita'], 'Thermal Storage Cost': island['thermal_storage_cost_per_capita'],
            'LNG Cost': island['lng_cost_per_capita'], 'Other Equipment Cost': island['other_equipment_cost_per_capita'],
            'Discard Cost': island['discard_cost_per_capita'], 'Load Shedding Cost': island['load_shedding_cost_per_capita'],
            'Total Cost': island['renewable_cost_per_capita']+island['storage_cost_per_capita']+island['lng_cost_per_capita']+island['other_equipment_cost_per_capita']+island['discard_cost_per_capita']+island['load_shedding_cost_per_capita']
        })
    
    if not island_data:
        print("错误: 未能处理任何岛屿数据。")
        return
        
    final_df = pd.DataFrame(island_data).fillna(0)
    print("数据处理完成 (Data processing complete).")

    # --- Log变换处理 (Log Transformation) ---
    print("\n正在进行成本变量的log变换 (Applying log transformation to cost variables)...")

    # 定义需要log变换的成本变量
    cost_variables = ['Renewable Cost', 'Storage Cost', 'Electrical Storage Cost',
                     'Thermal Storage Cost', 'LNG Cost', 'Other Equipment Cost',
                     'Discard Cost', 'Load Shedding Cost', 'Total Cost']

    # 对成本变量进行log(x+1)变换，避免零值问题
    for cost_var in cost_variables:
        if cost_var in final_df.columns:
            original_name = cost_var
            log_name = f'Log {cost_var}'

            # 计算log变换
            final_df[log_name] = np.log(final_df[original_name] + 1)

            # 输出变换前后的统计信息
            print(f"\n{original_name} 变换结果:")
            print(f"  原始数据 - 均值: {final_df[original_name].mean():.2f}, 标准差: {final_df[original_name].std():.2f}")
            print(f"  Log变换后 - 均值: {final_df[log_name].mean():.2f}, 标准差: {final_df[log_name].std():.2f}")
            print(f"  偏度改善: {final_df[original_name].skew():.2f} -> {final_df[log_name].skew():.2f}")

    print("Log变换完成 (Log transformation complete).")

    # 打印可再生能源相关变量的描述性统计
    print("\n=== 波浪能变量描述性统计 (Wave Energy Variables Statistics) ===")
    wave_columns = ['Total Wave Utilization', 'Wave Seasonal Variation', 'Wave Daily Fluctuation']
    for col in wave_columns:
        if col in final_df.columns:
            print(f"\n{col}:")
            print(final_df[col].describe())
        else:
            print(f"\n{col}: 列不存在")
    print("=" * 60)

    print("\n=== 光伏变量描述性统计 (PV Energy Variables Statistics) ===")
    pv_columns = ['Total PV Utilization', 'PV Seasonal Variation', 'PV Daily Fluctuation']
    for col in pv_columns:
        if col in final_df.columns:
            print(f"\n{col}:")
            print(final_df[col].describe())
        else:
            print(f"\n{col}: 列不存在")
    print("=" * 60)
    
    print("\n=== 风能变量描述性统计 (Wind Energy Variables Statistics) ===")
    wind_columns = ['Total Wind Utilization', 'Wind Seasonal Variation', 'Wind Daily Fluctuation']
    for col in wind_columns:
        if col in final_df.columns:
            print(f"\n{col}:")
            print(final_df[col].describe())
        else:
            print(f"\n{col}: 列不存在")
    print("=" * 60)
    
    
    # --- 2. 多元回归分析 (Multiple Regression Analysis) ---
    print("正在进行两阶段多元回归分析 (Performing two-stage multiple regression analysis)...")

    # 定义变量组
    all_vars = [
        'Heating Demand', 'Heating Demand Variation',
        'Cooling Demand', 'Cooling Demand Variation',
        'Total Wind Utilization', 'Wind Seasonal Variation', 'Wind Daily Fluctuation',
        'Total PV Utilization', 'PV Seasonal Variation', 'PV Daily Fluctuation',
        'Total Wave Utilization', 'Wave Seasonal Variation', 'Wave Daily Fluctuation'
    ]

    # Stage 1: 去掉总利用量变量
    stage1_vars = [
        'Heating Demand', 'Heating Demand Variation',
        'Cooling Demand', 'Cooling Demand Variation',
        'Wind Seasonal Variation', 'Wind Daily Fluctuation',
        'PV Seasonal Variation', 'PV Daily Fluctuation',
        'Wave Seasonal Variation', 'Wave Daily Fluctuation'
    ]

    # Stage 2: 进一步去掉制冷需求和波浪能日变化
    stage2_vars = [
        'Heating Demand', 'Heating Demand Variation',
        'Cooling Demand', 'Cooling Demand Variation',
        'Wind Seasonal Variation', 'Wind Daily Fluctuation',
        'PV Seasonal Variation', 'PV Daily Fluctuation',
        'Wave Seasonal Variation'
    ]

    # 因变量定义 - 使用Log变换后的成本变量
    stage1_dependent_vars = ['Log Renewable Cost', 'Log Storage Cost', 'Log LNG Cost', 'Log Total Cost']
    stage2_dependent_vars = ['Log Renewable Cost', 'Log Storage Cost', 'Log LNG Cost',
                           'Log Other Equipment Cost', 'Log Discard Cost', 'Log Total Cost']  

    # 筛选可用变量
    stage1_vars = [v for v in stage1_vars if v in final_df.columns and final_df[v].nunique() > 1]
    stage2_vars = [v for v in stage2_vars if v in final_df.columns and final_df[v].nunique() > 1]

    print(f"Stage 1 变量数量: {len(stage1_vars)}")
    print(f"Stage 2 变量数量: {len(stage2_vars)}")
    print(f"Stage 1 因变量数量: {len(stage1_dependent_vars)}")
    print(f"Stage 2 因变量数量: {len(stage2_dependent_vars)}")

    # --- 详细的变量统计分析 (Detailed Variable Statistics) ---
    print("\n" + "="*80)
    print("详细变量统计分析 (Detailed Variable Statistics Analysis)")
    print("="*80)

    # 分析所有相关变量的统计特征
    all_analysis_vars = list(set(stage1_vars + stage2_vars + stage1_dependent_vars))

    print(f"\n=== 自变量统计信息 (Independent Variables Statistics) ===")
    for var in stage1_vars:
        if var in final_df.columns:
            stats = final_df[var].describe()
            cv = final_df[var].std() / final_df[var].mean() if final_df[var].mean() != 0 else 0
            print(f"\n{var}:")
            print(f"  均值: {stats['mean']:.6f}, 标准差: {stats['std']:.6f}")
            print(f"  最小值: {stats['min']:.6f}, 最大值: {stats['max']:.6f}")
            print(f"  变异系数(CV): {cv:.6f}")
            print(f"  数量级: {np.log10(abs(stats['mean']) + 1e-10):.2f}")

    print(f"\n=== 因变量统计信息 (Log-Transformed Dependent Variables Statistics) ===")
    for var in stage1_dependent_vars:
        if var in final_df.columns:
            stats = final_df[var].describe()
            cv = final_df[var].std() / final_df[var].mean() if final_df[var].mean() != 0 else 0
            print(f"\n{var}:")
            print(f"  均值: {stats['mean']:.6f}, 标准差: {stats['std']:.6f}")
            print(f"  最小值: {stats['min']:.6f}, 最大值: {stats['max']:.6f}")
            print(f"  变异系数(CV): {cv:.6f}")
            print(f"  偏度: {final_df[var].skew():.4f}")

    # 相关性矩阵分析（重点关注供暖需求）
    print(f"\n=== 供暖需求相关性分析 (Heating Demand Correlation Analysis) ===")
    if 'Heating Demand' in final_df.columns:
        correlations = final_df[stage1_vars + stage1_dependent_vars].corr()['Heating Demand'].sort_values(key=abs, ascending=False)
        print("供暖需求与其他变量的相关系数（按绝对值排序）:")
        for var, corr in correlations.items():
            if var != 'Heating Demand':
                print(f"  {var}: {corr:.4f}")

    print("="*80)

    variability_vars = [
        'Heating Demand Variation', 'Cooling Demand Variation',
        'Wind Seasonal Variation', 'PV Seasonal Variation', 'Wave Seasonal Variation'
    ]

    # 辅助函数：进行回归分析
    def perform_regression_analysis(independent_vars, dependent_vars, stage_name):
        """进行回归分析并返回结果"""
        print(f"正在进行 {stage_name} 回归分析...")
        regression_results = {}

        for y_var in dependent_vars:
            for x_var in independent_vars:
                if x_var in variability_vars:
                    # 针对不同可再生能源类型使用不同的筛选策略
                    if 'Wave' in x_var:
                        # 波浪能：需要有显著的总利用量和变异性才纳入分析
                        wave_utilization_condition = final_df['Total Wave Utilization'] > 100
                        wave_variability_condition = final_df[x_var] > 0.2
                        current_df = final_df[wave_utilization_condition & wave_variability_condition].copy()
                    else:
                        # 其他可再生能源：使用变异系数阈值
                        current_df = final_df[final_df[x_var] > 0.1].copy()

                    if len(current_df) < 2:
                        regression_results[(y_var, x_var)] = {'r2': np.nan, 'p_value': np.nan}
                        continue
                else:
                    current_df = final_df.copy()

                X = sm.add_constant(current_df[x_var])
                y = current_df[y_var]
                model = sm.OLS(y, X).fit()

                regression_results[(y_var, x_var)] = {'r2': model.rsquared, 'p_value': model.pvalues[x_var]}

        return regression_results

    # 辅助函数：进行多元回归分析
    def perform_multiple_regression_analysis(independent_vars, dependent_vars, stage_name):
        """进行多元回归分析并返回模型结果"""
        print(f"正在进行 {stage_name} 多元回归分析...")
        model_results = {}

        for y_var in dependent_vars:
            print(f"  分析因变量: {y_var}")

            # 准备数据
            X_data = final_df[independent_vars].dropna()
            y_data = final_df[y_var].loc[X_data.index]

            if len(X_data) < len(independent_vars) + 1:  # 确保有足够的观测值
                print(f"    警告: {y_var} 的数据不足，跳过")
                continue

            # 数据标准化处理 (Standardization)

            # 标准化自变量
            scaler_X = StandardScaler()
            X_standardized = pd.DataFrame(
                scaler_X.fit_transform(X_data),
                columns=X_data.columns,
                index=X_data.index
            )

            # 标准化因变量
            scaler_y = StandardScaler()
            y_standardized = pd.Series(
                scaler_y.fit_transform(y_data.values.reshape(-1, 1)).flatten(),
                index=y_data.index
            )

            # 添加常数项
            X_with_const = sm.add_constant(X_standardized)

            # 拟合多元回归模型（使用标准化数据）
            model = sm.OLS(y_standardized, X_with_const).fit()

            # 计算异方差稳健的标准误 (Heteroscedasticity-robust standard errors)
            # 使用HC1标准误（White标准误的小样本修正版本）
            model_robust = sm.OLS(y_standardized, X_with_const).fit(cov_type='HC1')

            # 保存标准化信息到模型对象中（供后续使用）
            model.scaler_X = scaler_X
            model.scaler_y = scaler_y
            model.X_original = X_data
            model.y_original = y_data

            # 保存稳健标准误模型
            model.robust_model = model_robust

            model_results[y_var] = model

            # 输出详细的回归诊断信息
            print(f"\n{'='*60}")
            print(f"{stage_name} - {y_var} 回归诊断结果")
            print(f"{'='*60}")

            # 基本模型信息
            print(f"观测数量: {model.nobs}")
            print(f"自由度: {model.df_model}")
            print(f"残差自由度: {model.df_resid}")

            # 拟合优度指标
            print(f"\n--- 拟合优度指标 (Goodness of Fit) ---")
            print(f"R-squared: {model.rsquared:.4f}")
            print(f"Adj. R-squared: {model.rsquared_adj:.4f}")
            print(f"AIC: {model.aic:.2f}")
            print(f"BIC: {model.bic:.2f}")
            print(f"Log-Likelihood: {model.llf:.2f}")

            # F统计量和显著性
            print(f"\n--- 整体模型显著性检验 (Overall Model Significance) ---")
            print(f"F-statistic: {model.fvalue:.4f}")
            print(f"F-test p-value: {model.f_pvalue:.6f}")
            significance = "***" if model.f_pvalue < 0.001 else "**" if model.f_pvalue < 0.01 else "*" if model.f_pvalue < 0.05 else ""
            print(f"整体模型显著性: {significance}")

            # 回归系数及其统计检验（普通标准误）
            print(f"\n--- 回归系数详细结果 (Regression Coefficients - OLS Standard Errors) ---")
            print(f"{'变量':<25} {'系数':<12} {'标准误':<12} {'t值':<10} {'p值':<12} {'置信区间':<20} {'显著性':<8}")
            print("-" * 100)

            for var in model.params.index:
                if var == 'const':
                    var_name = '截距项'
                else:
                    var_name = var

                coef = model.params[var]
                se = model.bse[var]
                t_val = model.tvalues[var]
                p_val = model.pvalues[var]
                conf_int = model.conf_int().loc[var]
                sig_stars = get_significance_stars(p_val)

                print(f"{var_name:<25} {coef:<12.4f} {se:<12.4f} {t_val:<10.4f} {p_val:<12.6f} [{conf_int[0]:.4f}, {conf_int[1]:.4f}] {sig_stars:<8}")

            # 回归系数及其统计检验（稳健标准误）
            print(f"\n--- 回归系数详细结果 (Regression Coefficients - Robust Standard Errors HC1) ---")
            print(f"{'变量':<25} {'系数':<12} {'稳健标准误':<12} {'稳健t值':<10} {'稳健p值':<12} {'稳健置信区间':<20} {'稳健显著性':<8}")
            print("-" * 105)

            for var in model_robust.params.index:
                if var == 'const':
                    var_name = '截距项'
                else:
                    var_name = var

                coef = model_robust.params[var]
                se_robust = model_robust.bse[var]
                t_val_robust = model_robust.tvalues[var]
                p_val_robust = model_robust.pvalues[var]
                conf_int_robust = model_robust.conf_int().loc[var]
                sig_stars_robust = get_significance_stars(p_val_robust)

                print(f"{var_name:<25} {coef:<12.4f} {se_robust:<12.4f} {t_val_robust:<10.4f} {p_val_robust:<12.6f} [{conf_int_robust[0]:.4f}, {conf_int_robust[1]:.4f}] {sig_stars_robust:<8}")

            # 比较标准误的变化
            print(f"\n--- 标准误比较 (Standard Error Comparison) ---")
            print(f"{'变量':<25} {'OLS标准误':<12} {'稳健标准误':<12} {'比率':<10} {'变化':<10}")
            print("-" * 75)

            for var in model.params.index:
                if var == 'const':
                    var_name = '截距项'
                else:
                    var_name = var

                se_ols = model.bse[var]
                se_robust = model_robust.bse[var]
                ratio = se_robust / se_ols if se_ols > 0 else 0
                change = "增大" if ratio > 1.05 else "减小" if ratio < 0.95 else "相近"

                print(f"{var_name:<25} {se_ols:<12.4f} {se_robust:<12.4f} {ratio:<10.4f} {change:<10}")

            # 标准化系数（现在模型直接用标准化数据拟合，系数就是标准化系数）
            if len(independent_vars) > 0:
                print(f"\n--- 标准化系数 (Standardized Coefficients) ---")
                beta_coeffs = model.params[1:]  # 排除常数项，系数已经是标准化的

                print(f"{'变量':<25} {'标准化系数':<15} {'相对重要性':<15}")
                print("-" * 55)
                for var, beta in beta_coeffs.sort_values(key=abs, ascending=False).items():
                    importance = abs(beta) / abs(beta_coeffs).sum() * 100 if abs(beta_coeffs).sum() > 0 else 0
                    print(f"{var:<25} {beta:<15.4f} {importance:<15.1f}%")

                # 输出原始量纲下的系数
                print(f"\n--- 原始系数 (Original Scale Coefficients) ---")
                print(f"{'变量':<25} {'原始系数':<15} {'标准误':<15}")
                print("-" * 55)

                # 反标准化系数
                x_scales = model.scaler_X.scale_  # 自变量的标准差
                y_scale = model.scaler_y.scale_[0]  # 因变量的标准差

                for i, var in enumerate(independent_vars):
                    original_coef = beta_coeffs[var] * y_scale / x_scales[i]
                    original_se = model.bse[var] * y_scale / x_scales[i]  # 近似标准误
                    print(f"{var:<25} {original_coef:<15.4f} {original_se:<15.4f}")

            # 残差诊断
            print(f"\n--- 残差诊断 (Residual Diagnostics) ---")
            residuals = model.resid
            print(f"残差均值: {np.mean(residuals):.6f}")
            print(f"残差标准差: {np.std(residuals):.6f}")
            print(f"残差最小值: {np.min(residuals):.4f}")
            print(f"残差最大值: {np.max(residuals):.4f}")

            # Durbin-Watson统计量（检验自相关）
            from statsmodels.stats.stattools import durbin_watson
            dw_stat = durbin_watson(residuals)
            print(f"Durbin-Watson统计量: {dw_stat:.4f}")
            if dw_stat < 1.5:
                print("  -> 可能存在正自相关")
            elif dw_stat > 2.5:
                print("  -> 可能存在负自相关")
            else:
                print("  -> 无明显自相关")

            # Jarque-Bera正态性检验
            from statsmodels.stats.stattools import jarque_bera
            jb_stat, jb_pvalue, skew, kurtosis = jarque_bera(residuals)
            print(f"\n--- 残差正态性检验 (Normality Test) ---")
            print(f"Jarque-Bera统计量: {jb_stat:.4f}")
            print(f"p值: {jb_pvalue:.6f}")
            print(f"偏度: {skew:.4f}")
            print(f"峰度: {kurtosis:.4f}")
            if jb_pvalue < 0.05:
                print("  -> 拒绝正态性假设（残差非正态分布）")
            else:
                print("  -> 接受正态性假设（残差近似正态分布）")

            # Breusch-Pagan异方差检验
            from statsmodels.stats.diagnostic import het_breuschpagan
            bp_stat, bp_pvalue, bp_f_stat, bp_f_pvalue = het_breuschpagan(residuals, X_with_const)
            print(f"\n--- 异方差检验 (Heteroscedasticity Test) ---")
            print(f"Breusch-Pagan统计量: {bp_stat:.4f}")
            print(f"p值: {bp_pvalue:.6f}")
            if bp_pvalue < 0.05:
                print("  -> 拒绝同方差假设（存在异方差）")
            else:
                print("  -> 接受同方差假设（方差齐性）")

            print(f"{'='*60}\n")

        return model_results

    # 辅助函数：生成多元回归标准化系数图
    def generate_coefficient_plots(model_results, independent_vars, stage_name, filename, cost_mapping):
        """生成多元回归标准化系数图"""
        print(f"正在生成 {stage_name} 多元回归标准化系数图...")

        n_models = len(model_results)
        if n_models == 0:
            print(f"警告: {stage_name} 没有有效的模型结果")
            return

        # 设置3x2布局 - 调整图像尺寸，减小宽度增大高度
        fig, axes = plt.subplots(3, 2, figsize=(18, 24))
        axes = axes.flatten()

        # 定义变量显示顺序（从上到下，Heating Demand在最上面）
        var_order = [
            'Heating Demand', 'Heating Demand Variation',
            'Cooling Demand', 'Cooling Demand Variation',
            'Wind Seasonal Variation', 'Wind Daily Fluctuation',
            'PV Seasonal Variation', 'PV Daily Fluctuation',
            'Wave Seasonal Variation'
        ]
        var_order.reverse()
        # 定义变量名简化函数
        def simplify_var_name(var_name):
            """简化变量名，去掉Variation和Fluctuation"""
            name_mapping = {
                'Heating Demand': 'HD',
                'Heating Demand Variation': 'HDV', 
                'Cooling Demand': 'CD',
                'Cooling Demand Variation': 'CDV',  
                'Wind Seasonal Variation': 'WTS',
                'Wind Daily Fluctuation': 'WTD',
                'PV Seasonal Variation': 'PVS',
                'PV Daily Fluctuation': 'PVD',
                'Wave Seasonal Variation': 'WECS',
                'Wave Daily Fluctuation': 'WECD'
            }
            return name_mapping.get(var_name, var_name)

        for idx, (y_var, model) in enumerate(model_results.items()):
            if idx >= 6:  # 显示前6个模型
                break
            ax = axes[idx]

            # 获取标准化系数（使用稳健标准误）
            beta_coeffs = model.robust_model.params[1:]  # 排除常数项
            conf_int_std = model.robust_model.conf_int().iloc[1:, :]  # 排除常数项，使用稳健置信区间
            p_values = model.robust_model.pvalues[1:]  # 排除常数项，使用稳健p值

            # 按自定义顺序排列变量
            ordered_vars = [var for var in var_order if var in beta_coeffs.index]
            # 添加任何未在预定义顺序中的变量
            remaining_vars = [var for var in beta_coeffs.index if var not in ordered_vars]
            final_order = ordered_vars + remaining_vars

            beta_sorted = beta_coeffs.reindex(final_order)
            conf_int_sorted = conf_int_std.reindex(final_order)
            p_values_sorted = p_values.reindex(final_order)

            # 计算误差条
            lower_errors = beta_sorted - conf_int_sorted.iloc[:, 0]
            upper_errors = conf_int_sorted.iloc[:, 1] - beta_sorted

            # 定义变量类型分类
            demand_vars = ['Heating Demand', 'Heating Demand Variation', 'Cooling Demand', 'Cooling Demand Variation']

            # 根据显著性设置颜色
            colors = ["#982B2D" if p < 0.05 else '#0B75B3' for p in p_values_sorted]

            # 根据变量类型设置纹理模式
            hatches = []
            for var in beta_sorted.index:
                if var in demand_vars:  # 需求类变量 - 实心填充
                    hatches.append('')
                else:  # 可再生能源类变量 - 斜线纹理
                    hatches.append('///')

            # 创建水平条形图 - 逐个绘制以支持不同纹理
            bars = []
            for i, (y_pos, value, lower_err, upper_err, color, hatch_pattern) in enumerate(
                zip(range(len(beta_sorted)), beta_sorted, lower_errors, upper_errors, colors, hatches)):
                bar = ax.barh(y_pos, value, xerr=[[lower_err], [upper_err]],
                             color=color, alpha=1, capsize=5, hatch=hatch_pattern)
                bars.extend(bar)

            # 设置y轴标签 - 增大字号并旋转45度，使用简化的变量名
            ax.set_yticks(range(len(beta_sorted)))
            simplified_labels = [simplify_var_name(var) for var in beta_sorted.index]
            ax.set_yticklabels(simplified_labels, fontsize=34, fontfamily='Arial', rotation=0, ha='right')

            # 添加零参考线
            ax.axvline(x=0, color='black', linestyle='-', linewidth=0.8)

            # 使用显示名称作为标题
            display_name = cost_mapping.get(y_var, {}).get('display_name', y_var)

            # 设置标题 - 增大字号
            ax.set_title(f'{display_name}\n(R² = {model.rsquared:.3f})', fontsize=36, fontfamily='Arial')

            # x轴标签只在最下面一排显示（3x2布局，最下面一排是索引4和5）
            if idx >= 4:  # 最下面一排的子图
                ax.set_xlabel('Standardized Coefficient (β)', fontsize=36, fontfamily='Arial')
            else:
                ax.set_xlabel('')  # 其他子图不显示x轴标签

            # 设置x轴刻度标签字号
            ax.tick_params(axis='x', labelsize=30)

            # 设置网格
            ax.grid(False)

            # 移除顶部和右侧边框
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_linewidth(2)
            ax.spines['bottom'].set_linewidth(2)
        # 隐藏多余的子图
        for idx in range(n_models, 6):
            axes[idx].set_visible(False)

        # 手动设置子图间距 - 适应减宽增高的布局
        plt.subplots_adjust(
            left=0.12,   # 左边距，增加以适应更窄的布局
            bottom=0.08, # 下边距，减小以利用更高的空间
            right=0.98,  # 右边距
            top=0.95,    # 上边距，增加以利用更高的空间
            wspace=0.4,  # 列间距（水平间距），增加以适应更窄的子图
            hspace=0.4   # 行间距（垂直间距），减小以适应更高的空间
        )
        _b = os.path.splitext(filename)[0]
        plt.savefig(f'png/{_b}.png', dpi=600, bbox_inches='tight')
        plt.savefig(f'pdf/{_b}.pdf', bbox_inches='tight')
        plt.savefig(f'svg/{_b}.svg', bbox_inches='tight')
        plt.close()
        print(f"{stage_name} 多元回归标准化系数图已保存为 {filename}")

        # 生成单独的图例
        generate_coefficient_legend(stage_name)

    # 辅助函数：生成系数图图例
    def generate_coefficient_legend(stage_name):
        """生成系数图的单独图例"""
        print(f"正在生成 {stage_name} 系数图图例...")

        fig, ax = plt.subplots(figsize=(6, 2))
        ax.axis('off')  # 隐藏坐标轴

        # 创建图例元素
        from matplotlib.patches import Rectangle

        # 显著性图例（基于稳健标准误）
        significant_patch = Rectangle((0, 0), 1, 1, facecolor="#982B2D", alpha=1, label='Significant (p < 0.05, Robust SE)')
        non_significant_patch = Rectangle((0, 0), 1, 1, facecolor='#0B75B3', alpha=1, label='Non-significant (p ≥ 0.05, Robust SE)')

        # 变量类型图例
        demand_patch = Rectangle((0, 0), 1, 1, facecolor="gray", alpha=1, hatch='', label='Demand Variables (Solid)')
        renewable_patch = Rectangle((0, 0), 1, 1, facecolor="gray", alpha=1, hatch='///', label='Renewable Variables (Hatched)')

        # 添加图例
        legend = ax.legend(
            handles=[significant_patch, non_significant_patch, demand_patch, renewable_patch],
            loc='center',
            frameon=False,
            fontsize=12,
            ncol=2
        )

        # 设置图例文字颜色
        for text in legend.get_texts():
            text.set_color('black')

        plt.tight_layout()
        legend_filename = f'coefficient_legend_{stage_name.lower().replace(" ", "_")}.png'
        _b = os.path.splitext(legend_filename)[0]
        plt.savefig(f'png/{_b}.png', dpi=600, bbox_inches='tight')
        plt.savefig(f'pdf/{_b}.pdf', bbox_inches='tight')
        plt.savefig(f'svg/{_b}.svg', bbox_inches='tight')
        plt.close()
        print(f"{stage_name} 系数图图例已保存为 {legend_filename}")

    # 辅助函数：生成偏回归图
    def generate_partial_regression_plots(model_results, independent_vars, stage_name, filename, cost_mapping):
        """生成偏回归图"""
        print(f"正在生成 {stage_name} 偏回归图...")

        if not model_results:
            print(f"警告: {stage_name} 没有有效的模型结果")
            return

        # 选择第一个有效模型进行偏回归图展示（通常选择Log Total Cost）
        target_model = None
        for y_var in ['Log Total Cost', 'Log LNG Cost', 'Log Storage Cost']:
            if y_var in model_results:
                target_model = model_results[y_var]
                target_y_var = y_var
                break

        if target_model is None:
            target_y_var = list(model_results.keys())[0]
            target_model = model_results[target_y_var]

        # 计算偏回归图的行列数
        n_vars = len(independent_vars)
        n_cols = min(4, n_vars)
        n_rows = (n_vars + n_cols - 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(5*n_cols, 4*n_rows))
        if n_rows == 1 and n_cols == 1:
            axes = [[axes]]
        elif n_rows == 1:
            axes = [axes]
        elif n_cols == 1:
            axes = [[ax] for ax in axes]

        # 准备数据（使用原始数据进行偏回归图）
        X_data = target_model.X_original  # 使用保存的原始数据
        y_data = target_model.y_original
        X_with_const = sm.add_constant(X_data)

        for idx, x_var in enumerate(independent_vars):
            row = idx // n_cols
            col = idx % n_cols
            ax = axes[row][col]

            # 计算偏残差
            other_vars = [v for v in independent_vars if v != x_var]
            if other_vars:
                # 回归y对其他变量
                X_others = sm.add_constant(X_data[other_vars])
                model_y_others = sm.OLS(y_data, X_others).fit()
                y_residuals = model_y_others.resid

                # 回归x对其他变量
                model_x_others = sm.OLS(X_data[x_var], X_others).fit()
                x_residuals = model_x_others.resid
            else:
                y_residuals = y_data - y_data.mean()
                x_residuals = X_data[x_var] - X_data[x_var].mean()

            # 绘制偏回归图
            ax.scatter(x_residuals, y_residuals, alpha=0.6, s=30, color='#4596CD')

            # 添加回归线
            from scipy.stats import linregress
            slope, intercept, r_value, p_value, std_err = linregress(x_residuals, y_residuals)
            line_x = np.array([x_residuals.min(), x_residuals.max()])
            line_y = slope * line_x + intercept
            ax.plot(line_x, line_y, color='#C84747', linewidth=2)

            # 设置标题和标签
            ax.set_xlabel(f'{x_var} (partial)', fontsize=12, fontfamily='Arial')
            ax.set_ylabel(f'{target_y_var} (partial)', fontsize=12, fontfamily='Arial')
            ax.set_title(f'r = {r_value:.3f}', fontsize=12, fontfamily='Arial')

            # 网格和边框
            ax.grid(True, alpha=0.3)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

        # 隐藏多余的子图
        for idx in range(n_vars, n_rows * n_cols):
            row = idx // n_cols
            col = idx % n_cols
            axes[row][col].set_visible(False)

        # 使用显示名称作为总标题
        display_name = cost_mapping.get(target_y_var, {}).get('display_name', target_y_var)
        plt.suptitle(f'{stage_name}: Partial Regression Plots for {display_name}',
                     fontsize=16, fontfamily='Arial', y=0.98)
        plt.tight_layout()
        _b = os.path.splitext(filename)[0]
        plt.savefig(f'png/{_b}.png', dpi=600, bbox_inches='tight')
        plt.savefig(f'pdf/{_b}.pdf', bbox_inches='tight')
        plt.savefig(f'svg/{_b}.svg', bbox_inches='tight')
        plt.close()
        print(f"{stage_name} 偏回归图已保存为 {filename}")

    # --- Stage 2 分析：多元回归系数图和偏回归图 (Stage 2 Analysis: Multiple Regression) ---
    stage2_models = perform_multiple_regression_analysis(stage2_vars, stage2_dependent_vars, "Stage 2")
    generate_coefficient_plots(stage2_models, stage2_vars, "Stage 2", "coefficient_plots_stage2.png", cost_mapping)
    generate_partial_regression_plots(stage2_models, stage2_vars, "Stage 2", "partial_regression_plots_stage2.png", cost_mapping)
    
    # 辅助函数：生成多重共线性检验图
    def generate_multicollinearity_analysis(independent_vars, stage_name, filename):
        """生成多重共线性检验图"""
        print(f"正在生成 {stage_name} 多重共线性检验图...")

        X_multi = final_df[independent_vars].dropna()

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(22, 10))
        fig.suptitle(f'{stage_name}: Multicollinearity Diagnostics for Independent Variables', fontsize=20)

        # Subplot 1: Correlation Matrix
        corr_matrix = X_multi.corr()
        sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', fmt=".2f", ax=ax1,
                    annot_kws={"size": 9})
        ax1.set_title('Correlation Matrix', fontsize=16)

        ax1.tick_params(axis='y', rotation=0)
        plt.setp(ax1.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor", size=11)

        # Subplot 2: Variance Inflation Factor (VIF)
        X_vif = sm.add_constant(X_multi)
        vif_data = pd.DataFrame()
        vif_data["feature"] = X_vif.columns
        vif_data["VIF"] = [variance_inflation_factor(X_vif.values, i) for i in range(X_vif.shape[1])]
        vif_data = vif_data[vif_data["feature"] != "const"].sort_values('VIF', ascending=False)

        sns.barplot(x='VIF', y='feature', data=vif_data, ax=ax2, palette='mako', hue='feature', legend=False)
        ax2.set_title('Variance Inflation Factor (VIF)', fontsize=16)
        ax2.axvline(x=5, color='orange', linestyle='--', label='Moderate Concern (VIF=5)')
        ax2.axvline(x=10, color='red', linestyle='--', label='High Concern (VIF=10)')
        ax2.legend()

        plt.tight_layout(rect=[0, 0.03, 1, 0.97])
        _b = os.path.splitext(filename)[0]
        plt.savefig(f'png/{_b}.png', dpi=600, bbox_inches='tight')
        plt.savefig(f'pdf/{_b}.pdf', bbox_inches='tight')
        plt.savefig(f'svg/{_b}.svg', bbox_inches='tight')
        plt.close()
        print(f"{stage_name} 多重共线性检验图已保存为 {filename}")

    # --- Stage 1 多重共线性检验 (Stage 1 Multicollinearity Test) ---
    # generate_multicollinearity_analysis(stage1_vars, "Stage 1", "multicollinearity_analysis_stage1.png")

    # --- Stage 2 多重共线性检验 (Stage 2 Multicollinearity Test) ---
    generate_multicollinearity_analysis(stage2_vars, "Stage 2", "multicollinearity_analysis_stage2.png")

    print("\n所有分析和绘图已完成 (All analysis and plotting complete)!")

# 运行主函数
if __name__ == '__main__':
    run_island_energy_cost_analysis()
    
