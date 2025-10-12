import pandas as pd
import numpy as np
import os
import geopandas as gpd
from shapely.geometry import Point

def generate_island_cost_summary(scenario, investment_cost, fixed_om_cost, base_dir='.'):
    """
    综合函数：生成指定情景下的岛屿成本汇总

    参数:
    scenario (str): '0', '2020', '2050', 'future_2030', etc.
    investment_cost (dict): 包含设备投资成本的字典
    fixed_om_cost (dict): 包含设备固定运维成本的字典
    base_dir (str): 结果目录的基路径

    返回:
    包含详细成本信息和IPCC区域信息的DataFrame
    """

    # 系统参数
    r = 0.05  # 系统的年化率
    n = 20    # 设备的使用年限

    # 年化因子计算
    annualization_factor = (r * (1 + r)**n) / ((1 + r)**n - 1)

    # 设置文件路径
    # The scenario name might be 'future_2030', but the directory is 'output_future_2030'
    output_dir_scenario = scenario
    island_capacity_file = f'{base_dir}/island_capacity_{output_dir_scenario}.csv'
    output_dir = f'{base_dir}/output_{output_dir_scenario}'
    population_file = '../visualization/filtered_island_1898.csv'  # 相对于base_dir的路径

    print(f"处理情景: {scenario}")
    print(f"容量文件: {island_capacity_file}")
    print(f"输出目录: {output_dir}")
    print(f"人口文件: {population_file}")

    # 检查文件是否存在
    if not os.path.exists(island_capacity_file):
        raise FileNotFoundError(f"容量文件不存在: {island_capacity_file}")
    if not os.path.exists(output_dir):
        raise FileNotFoundError(f"输出目录不存在: {output_dir}")
    if not os.path.exists(population_file):
        raise FileNotFoundError(f"人口文件不存在: {population_file}")

    # 读取容量配置数据
    capacity_df = pd.read_csv(island_capacity_file)
    print(f"读取到 {len(capacity_df)} 个岛屿的容量配置")

    # 读取人口数据
    pop_df = pd.read_csv(population_file)
    print(f"读取到 {len(pop_df)} 行人口数据")

    # 初始化结果列表
    results = []

    for idx, row in capacity_df.iterrows():
        lat, lon = row['lat'], row['lon']

        # 构建对应的best_cost文件路径
        cost_file = os.path.join(output_dir, f"{lat}_{lon}_best_cost.csv")

        if not os.path.exists(cost_file):
            print(f"警告: 文件不存在 {cost_file}")
            continue

        # 查找对应的人口数据（允许小的误差）
        pop_match = pop_df[(abs(pop_df['Lat'] - lat) < 0.01) & (abs(pop_df['Long'] - lon) < 0.01)]

        if len(pop_match) == 0:
            print(f"警告: 未找到岛屿 ({lat}, {lon}) 的人口数据")
            continue
        elif len(pop_match) > 1:
            print(f"警告: 岛屿 ({lat}, {lon}) 找到多个人口数据，使用第一个")

        # 获取人口数据，限制最大值为500
        population = min(pop_match.iloc[0]['pop'], 500)

        # 读取成本数据
        cost_df = pd.read_csv(cost_file)
        cost_dict = dict(zip(cost_df['Cost_Item'], cost_df['Cost_Value']))

        # 计算各类设备的成本

        # 1. 可再生能源设施
        renewable_devices = ['PV', 'WT', 'WEC']
        renewable_annualized_investment = sum(
            row[device] * investment_cost[device] * annualization_factor
            for device in renewable_devices if device in row.index and not pd.isna(row[device])
        )
        renewable_fixed_om = sum(
            row[device] * fixed_om_cost[device]
            for device in renewable_devices if device in row.index and not pd.isna(row[device])
        )
        renewable_cost = renewable_annualized_investment + renewable_fixed_om

        # 2. 储能设施 - 分为电储能(ESS+H2S+PEM+FC)和储热/储冷(TES+CES)
        # 2.1 电储能设施 (ESS + H2S + PEM + FC)
        electrical_storage_devices = ['ESS', 'H2S', 'PEM', 'FC']
        electrical_storage_annualized_investment = sum(
            row[device] * investment_cost[device] * annualization_factor
            for device in electrical_storage_devices if device in row.index and not pd.isna(row[device])
        )
        electrical_storage_fixed_om = sum(
            row[device] * fixed_om_cost[device]
            for device in electrical_storage_devices if device in row.index and not pd.isna(row[device])
        )
        electrical_storage_cost = electrical_storage_annualized_investment + electrical_storage_fixed_om

        # 2.2 储热/储冷设施 (TES + CES)
        thermal_storage_devices = ['TES', 'CES']
        thermal_storage_annualized_investment = sum(
            row[device] * investment_cost[device] * annualization_factor
            for device in thermal_storage_devices if device in row.index and not pd.isna(row[device])
        )
        thermal_storage_fixed_om = sum(
            row[device] * fixed_om_cost[device]
            for device in thermal_storage_devices if device in row.index and not pd.isna(row[device])
        )
        thermal_storage_cost = thermal_storage_annualized_investment + thermal_storage_fixed_om

        # 总储能成本 (保持向后兼容)
        storage_cost = electrical_storage_cost + thermal_storage_cost

        # 3. 其他能源转换设施 (移除PEM和FC，因为它们现在属于电储能)
        other_devices = ['CHP', 'EB', 'AC', 'LNGV']
        other_annualized_investment = sum(
            row[device] * investment_cost[device] * annualization_factor
            for device in other_devices if device in row.index and not pd.isna(row[device])
        )
        other_fixed_om = sum(
            row[device] * fixed_om_cost[device]
            for device in other_devices if device in row.index and not pd.isna(row[device])
        )
        other_equipment_cost = other_annualized_investment + other_fixed_om

        # 4. LNG总成本
        lng_capacity = row['LNG'] if 'LNG' in row.index and not pd.isna(row['LNG']) else 0
        lng_annualized_investment = lng_capacity * investment_cost['LNG'] * annualization_factor
        lng_fixed_om = lng_capacity * fixed_om_cost['LNG']
        lng_purchase_cost = cost_dict.get('LNG Purchase Cost', 0)
        lng_cost = lng_annualized_investment + lng_fixed_om + lng_purchase_cost

        # 5. 能源丢弃成本
        discard_cost = (cost_dict.get('Energy Discard Cost (Heat/Cold)', 0) +
                        cost_dict.get('Renewable Curtailment Cost', 0))

        # 6. 负荷削减成本
        load_shedding_cost = cost_dict.get('Load Shedding Cost', 0)

        # 计算人均成本
        renewable_cost_per_capita = renewable_cost / population if population > 0 else 0
        storage_cost_per_capita = storage_cost / population if population > 0 else 0
        electrical_storage_cost_per_capita = electrical_storage_cost / population if population > 0 else 0
        thermal_storage_cost_per_capita = thermal_storage_cost / population if population > 0 else 0
        lng_cost_per_capita = lng_cost / population if population > 0 else 0
        other_equipment_cost_per_capita = other_equipment_cost / population if population > 0 else 0
        discard_cost_per_capita = discard_cost / population if population > 0 else 0
        load_shedding_cost_per_capita = load_shedding_cost / population if population > 0 else 0

        # 保存结果
        results.append({
            'lat': lat,
            'lon': lon,
            'population': population,
            'original_population': pop_match.iloc[0]['pop'],
            # 总成本
            'renewable_cost': renewable_cost,
            'storage_cost': storage_cost,
            'electrical_storage_cost': electrical_storage_cost,
            'thermal_storage_cost': thermal_storage_cost,
            'lng_cost': lng_cost,
            'other_equipment_cost': other_equipment_cost,
            'discard_cost': discard_cost,
            'load_shedding_cost': load_shedding_cost,
            # 人均成本
            'renewable_cost_per_capita': renewable_cost_per_capita,
            'storage_cost_per_capita': storage_cost_per_capita,
            'electrical_storage_cost_per_capita': electrical_storage_cost_per_capita,
            'thermal_storage_cost_per_capita': thermal_storage_cost_per_capita,
            'lng_cost_per_capita': lng_cost_per_capita,
            'other_equipment_cost_per_capita': other_equipment_cost_per_capita,
            'discard_cost_per_capita': discard_cost_per_capita,
            'load_shedding_cost_per_capita': load_shedding_cost_per_capita,
            # 详细成本分解
            'renewable_investment': renewable_annualized_investment,
            'renewable_om': renewable_fixed_om,
            'storage_investment': electrical_storage_annualized_investment + thermal_storage_annualized_investment,
            'storage_om': electrical_storage_fixed_om + thermal_storage_fixed_om,
            'electrical_storage_investment': electrical_storage_annualized_investment,
            'electrical_storage_om': electrical_storage_fixed_om,
            'thermal_storage_investment': thermal_storage_annualized_investment,
            'thermal_storage_om': thermal_storage_fixed_om,
            'other_investment': other_annualized_investment,
            'other_om': other_fixed_om,
            'lng_investment': lng_annualized_investment,
            'lng_om': lng_fixed_om,
            'lng_purchase': lng_purchase_cost
        })

    cost_summary_df = pd.DataFrame(results)
    print(f"成功处理 {len(cost_summary_df)} 个岛屿的成本数据")

    # 添加IPCC区域信息
    def add_ipcc_regions(df):
        try:
            # 尝试读取IPCC区域数据
            ipcc_file = '../visualization/IPCC-WGI-reference-regions-v4.geojson'
            if not os.path.exists(ipcc_file):
                print(f"警告: IPCC区域文件不存在: {ipcc_file}")
                return df

            ipcc_regions = gpd.read_file(ipcc_file)
            print(f"成功读取IPCC区域数据，共{len(ipcc_regions)}个区域")

            # 为每个岛屿创建Point几何
            geometry = [Point(lon, lat) for lon, lat in zip(df['lon'], df['lat'])]
            islands_gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')

            # 空间连接
            islands_with_regions = gpd.sjoin(islands_gdf,
                                             ipcc_regions[['Name', 'Acronym', 'Continent', 'geometry']],
                                             how='left', predicate='within')

            # 清理结果
            result_df = islands_with_regions.drop(['geometry', 'index_right'], axis=1, errors='ignore')

            # 重命名列
            if 'Name' in result_df.columns:
                result_df = result_df.rename(columns={'Name': 'IPCC_Region_Name', 'Acronym': 'IPCC_Region_Code'})

            # 统计未匹配的岛屿
            unmatched = result_df[result_df['IPCC_Region_Name'].isna()]
            if len(unmatched) > 0:
                print(f"警告: {len(unmatched)}个岛屿未能匹配到IPCC区域")

            print(f"成功匹配 {len(result_df) - len(unmatched)} 个岛屿到IPCC区域")
            return result_df

        except Exception as e:
            print(f"添加IPCC区域信息时出错: {e}")
            return df

    # 添加区域信息
    cost_summary_with_regions = add_ipcc_regions(cost_summary_df.copy())

    # 保存结果
    output_file = f'island_cost_summary_{scenario}.csv'
    cost_summary_with_regions.to_csv(output_file, index=False)
    print(f"\n成本汇总数据已保存到: {output_file}")

    # 显示统计信息
    print(f"\n=== {scenario} 成本统计信息 ===")
    print(f"岛屿总数: {len(cost_summary_with_regions)}")
    print(f"平均人口: {cost_summary_with_regions['population'].mean():.1f}")
    print(f"总人口: {cost_summary_with_regions['population'].sum()}")

    # 显示人均成本统计
    per_capita_cols = [col for col in cost_summary_with_regions.columns if col.endswith('_per_capita')]
    print(f"\n平均人均成本:")
    for col in per_capita_cols:
        cost_name = col.replace('_per_capita', '').replace('_', ' ').title()
        print(f"  {cost_name}: {cost_summary_with_regions[col].mean():.2f}")

    return cost_summary_with_regions


if __name__ == "__main__":
    # 2020年基准成本参数
    investment_cost_2020 = {
        'WT': 1392, 'PV': 1377, 'WEC': 6000, 'AC': 150, 'EB': 250, 'CHP': 1300,
        'PEM': 1371, 'FC': 3000, 'LNG': 700, 'LNGV': 500, 'ESS': 1365,
        'TES': 250, 'CES': 250, 'H2S': 50
    }
    fixed_om_cost_2020 = {
        'WT': 43, 'PV': 23, 'LNG': 14, 'WEC': 300, 'CHP': 26, 'EB': 5, 'AC': 3,
        'PEM': 41, 'FC': 90, 'LNGV': 25, 'ESS': 34, 'TES': 6, 'CES': 6, 'H2S': 1.2
    }

    # 2030年成本参数
    investment_cost_2030 = {
        'WT': 1392, 'PV': 1377, 'WEC': 6000, 'AC': 150, 'EB': 250, 'CHP': 1300,
        'PEM': 1120, 'FC': 2000, 'LNG': 700, 'LNGV': 500, 'ESS': 784,
        'TES': 250, 'CES': 250, 'H2S': 50
    }
    fixed_om_cost_2030 = {
        'WT': 43, 'PV': 23, 'LNG': 14, 'WEC': 300, 'CHP': 26, 'EB': 5, 'AC': 3,
        'PEM': 41, 'FC': 90, 'LNGV': 25, 'ESS': 34, 'TES': 6, 'CES': 6, 'H2S': 1.2
    }

    # 2040年成本参数
    investment_cost_2040 = {
        'WT': 1392, 'PV': 1377, 'WEC': 6000, 'AC': 150, 'EB': 250, 'CHP': 1300,
        'PEM': 915, 'FC': 1800, 'LNG': 700, 'LNGV': 500, 'ESS': 686,
        'TES': 250, 'CES': 250, 'H2S': 50
    }
    fixed_om_cost_2040 = {
        'WT': 43, 'PV': 23, 'LNG': 14, 'WEC': 300, 'CHP': 26, 'EB': 5, 'AC': 3,
        'PEM': 41, 'FC': 90, 'LNGV': 25, 'ESS': 34, 'TES': 6, 'CES': 6, 'H2S': 1.2
    }

    # 2050年成本参数
    investment_cost_2050 = {
        'WT': 1392, 'PV': 1377, 'WEC': 6000, 'AC': 150, 'EB': 250, 'CHP': 1300,
        'PEM': 748, 'FC': 1600, 'LNG': 700, 'LNGV': 500, 'ESS': 588,
        'TES': 250, 'CES': 250, 'H2S': 50
    }
    fixed_om_cost_2050 = {
        'WT': 43, 'PV': 23, 'LNG': 14, 'WEC': 300, 'CHP': 26, 'EB': 5, 'AC': 3,
        'PEM': 41, 'FC': 90, 'LNGV': 25, 'ESS': 34, 'TES': 6, 'CES': 6, 'H2S': 1.2
    }

    # 运行所有情景
    summary_0 = generate_island_cost_summary('0', investment_cost_2020, fixed_om_cost_2020)
    summary_2020 = generate_island_cost_summary('2020', investment_cost_2020, fixed_om_cost_2020)
    summary_2050 = generate_island_cost_summary('2050', investment_cost_2050, fixed_om_cost_2050)
    summary_future_2030 = generate_island_cost_summary('future_2030', investment_cost_2030, fixed_om_cost_2030)
    summary_future_2040 = generate_island_cost_summary('future_2040', investment_cost_2040, fixed_om_cost_2040)
    summary_future_2050 = generate_island_cost_summary('future_2050', investment_cost_2050, fixed_om_cost_2050)