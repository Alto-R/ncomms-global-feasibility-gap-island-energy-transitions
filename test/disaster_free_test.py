import pandas as pd
import numpy as np
import xarray as xr
import gurobipy as gp
from gurobipy import GRB
from geopy.distance import geodesic
import os
import pvlib
import argparse
from timezonefinder import TimezoneFinder

### 获取参数和数据 ###
# 获取岛屿经纬度参数
parser = argparse.ArgumentParser(description="Process island coordinates and population.")
parser.add_argument("--island_lat", type=float, required=True, help="Latitude of the island")
parser.add_argument("--island_lon", type=float, required=True, help="Longitude of the island")
parser.add_argument("--pop", type=int, required=True, help="Population of the island")
args = parser.parse_args()
island_lat = args.island_lat
island_lon = args.island_lon
pop = args.pop
if pop < 500:
    pop = pop
else:
    pop = 500
island_coords = (island_lat, island_lon)

# 读取原始1小时精度数据
demand_data = pd.read_csv(f'sampledata/demand_{island_lat}_{island_lon}.csv', index_col=0, parse_dates=True)
pv_data = pd.read_csv(f'sampledata/pv_{island_lat}_{island_lon}.csv', index_col=0, parse_dates=True)
wt_data = pd.read_csv(f'sampledata/wt_{island_lat}_{island_lon}.csv', index_col=0, parse_dates=True)

# 重采样为3小时精度：需求使用最大值，供给使用平均值
demand_data_3h = demand_data.resample('3h').max()
pv_data_3h = pv_data.resample('3h').mean()
wt_data_3h = wt_data.resample('3h').mean()

# 提取功率数组
pv_power = pv_data_3h['electricity'].values
wind_power = wt_data_3h['electricity'].values

# 获取基础电负荷数据
def calculate_elec_with_pvlib(latitude, longitude, year):
    """
    使用 pvlib 高效计算全年基础电负荷。
    Args:
        latitude (float): 地点的纬度。
        longitude (float): 地点的经度。
        year (int): 需要计算的年份。
    Returns:
        pd.DataFrame: 一个包含全年每小时负荷的 DataFrame。
    """
    # --- 1. 设置地点和时区 ---
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lng=longitude, lat=latitude)
    if not tz_name:
        print(f"警告：无法为经纬度 ({latitude}, {longitude}) 找到时区，将使用 UTC。")
        tz_name = "UTC"
    
    # --- 2. 创建全年的时间序列 ---
    # 这是矢量化操作的基础。我们创建两个时间序列：
    # daily_times 用于计算每日的日出日落
    # hourly_times 用于构建最终的每小时负荷数据
    daily_times = pd.date_range(
        start=f'{year}-01-01', 
        end=f'{year}-12-31', 
        freq='D', 
        tz=tz_name,
        nonexistent='shift_forward',
        ambiguous=True
    )
    hourly_times = pd.date_range(
        start=f'{year}-01-01', 
        end=f'{year+1}-01-01', # 到下一年初，确保包含最后一天的所有小时
        freq='h', 
        inclusive='left', # 【已修正】使用 'inclusive' 替代 'closed' (for pandas >= 2.0)
        tz=tz_name,
        nonexistent='shift_forward', # 处理不存在的时间（夏令时开始）
        ambiguous=True 
    )
    # --- 3. 一次性计算全年的日出日落时间 ---
    # 这是 pvlib 的核心优势：用一个函数调用取代整个 while 循环。
    # 结果是一个 DataFrame，索引是日期，列是 'sunrise', 'sunset', 'transit'。
    sun_times = pvlib.solarposition.sun_rise_set_transit_spa( # 【已修正】使用新的函数名 (for pvlib >= 0.8)
        daily_times, latitude, longitude
    )
    # --- 4. 构建基础负荷（完全矢量化，无循环） ---
    df_load = pd.DataFrame(index=hourly_times)
    df_load['Hour'] = df_load.index.hour
    df_load['Date'] = df_load.index.date.astype('O') # 使用 object 类型以便于映射
    # 将每日的日出日落小时映射到每小时的数据中
    # .dt.hour 会自动处理时区并提取本地时间的小时
    sunrise_map = sun_times['sunrise'].dt.hour
    sunset_map = sun_times['sunset'].dt.hour
    df_load['sunrise_hour'] = df_load['Date'].map(sunrise_map)
    df_load['sunset_hour'] = df_load['Date'].map(sunset_map)
    # --- 5. 优雅地处理极昼和极夜 ---
    # pvlib 在极昼/极夜时返回 NaT (Not a Time)，这在 pandas 中会变成 NaN。
    # 我们需要填充这些NaN值。
    # 极夜: 日出日落都为NaN。我们将日出设为24，日落设为0，这样任何小时都不在[日出, 日落)区间内。
    # 极昼: 日出日落也为NaN。我们将日出设为0，日落设为24，这样任何小时都在区间内。
    # 为了区分两者，我们检查太阳在正午时是否在地平线以上。
    
    # 找到有NaN的日期
    nan_dates = sun_times[sun_times['sunrise'].isnull()].index
    if not nan_dates.empty:
        # 计算这些特殊日期的正午太阳位置
        solar_pos_noon = pvlib.solarposition.get_solarposition(
            nan_dates + pd.Timedelta(hours=12), latitude, longitude
        )
        # 如果正午时太阳高度角 > 0，则为极昼；否则为极夜。
        is_polar_day = solar_pos_noon['apparent_elevation'] > 0
        
        # 根据判断结果填充 sunrise 和 sunset 小时
        # 极昼: (0, 24)
        df_load.loc[df_load['Date'].isin(is_polar_day[is_polar_day].index), 'sunrise_hour'] = 0
        df_load.loc[df_load['Date'].isin(is_polar_day[is_polar_day].index), 'sunset_hour'] = 24
        # 极夜: (24, 0) - 或者其他确保白天条件为假的组合
        df_load.loc[df_load['Date'].isin(is_polar_day[~is_polar_day].index), 'sunrise_hour'] = 24
        df_load.loc[df_load['Date'].isin(is_polar_day[~is_polar_day].index), 'sunset_hour'] = 0
        
    # --- 6. 使用矢量化操作计算照明负荷 ---
    day_hours_power = 0.1
    night_hours_power = 0.2
    
    # 条件1：是白天吗？ (当前小时 >= 日出小时 AND 当前小时 < 日落小时)
    is_day = (df_load['Hour'] >= df_load['sunrise_hour']) & (df_load['Hour'] < df_load['sunset_hour'])
    
    # 使用 np.where 高效地根据条件分配功率
    df_load['Power (kW)'] = np.where(is_day, day_hours_power, night_hours_power)
    # 条件2：是无照明时间吗？ (23:00 - 06:59)
    no_lighting_hours = (df_load['Hour'] >= 23) | (df_load['Hour'] < 7)
    
    # 在无照明时间将功率设为 0，覆盖之前的计算结果
    df_load.loc[no_lighting_hours, 'Power (kW)'] = 0
    
    # --- 7. 添加其他基础负荷（矢量化） ---
    daily_profile_data = {
        "hour": list(range(24)),
        "refrigerator": [0.01]*24,
        "cooking": [0.01]*7 + [0.08]*3 + [0.025]*7 + [0.15]*4 + [0.01]*3,
        "hot water": [0.01]*7 + [0.06]*3 + [0.05]*7 + [0.12]*4 + [0.01]*3,
        "others": [0.01]*7 + [0.02]*3 + [0.02]*7 + [0.03]*4 + [0.02]*3,
    }
    daily_df = pd.DataFrame(daily_profile_data).set_index('hour')
    # 计算每小时的基础总负荷
    daily_df['base_power'] = daily_df.sum(axis=1)
    
    # 创建一个从小时到功率的映射字典
    hour_to_base_power_map = daily_df['base_power'].to_dict()
    
    # 使用 .map() 将小时映射到对应的基础负荷值，并加到总负荷上
    df_load['Power (kW)'] += df_load['Hour'].map(hour_to_base_power_map)
    
    # --- 8. 重采样为3小时精度并返回最终结果 ---
    final_df = df_load.reset_index().rename(columns={'index': 'Timestamp', 'Date': 'Day'})
    
    # 重采样为3小时精度，使用最大值以保证可靠性
    final_df_3h = final_df.set_index('Timestamp')
    final_df_3h = final_df_3h.resample('3h').max()
    final_df_3h = final_df_3h.reset_index()
    final_df_3h['Day'] = final_df_3h['Timestamp'].dt.date
    final_df_3h['Hour'] = final_df_3h['Timestamp'].dt.hour
    
    return final_df_3h[['Day', 'Hour', 'Power (kW)']]

E_demand = calculate_elec_with_pvlib(island_lat, island_lon, year=2020)
E_demand['Power (kW)'] = E_demand['Power (kW)'] * pop

# 获取波浪能数据
def get_wave(data,lat,lon):
    if lon < 0 :
        lon = lon + 360
    else :
        lon = lon
    location_wave = data['WPD'].sel(lat=lat, lon=lon, method='nearest')
    
    wave_power_df = location_wave.to_dataframe().reset_index()
    wave_power_df = wave_power_df[wave_power_df['npt']==1]
    
    last_time = pd.Timestamp("2021-01-01 00:00:00")
    last_row = wave_power_df.iloc[-1].copy()
    last_row['time'] = last_time
    new_row = pd.DataFrame([last_row])
    wave_df = pd.concat([wave_power_df, new_row])
    
    wave_df['time'] = pd.to_datetime(wave_df['time'])
    wave_df.set_index("time", inplace=True) 
    wave_df = wave_df.resample('3h').interpolate(method='linear')
    wave_df['t'] = range(0, len(wave_df))
    
    wave_df.fillna(0, inplace=True)
    wave_df[wave_df < 0] = 0
    
    return wave_df

wave = xr.open_dataset('sampledata/wave_2020.nc')
wave_df = get_wave(wave, island_lat, island_lon)
wave_power = wave_df['WPD'].values


# 找出最近的终端
LNG_terminals = pd.read_excel('sampledata/LNG_Terminals.xlsx')
LNG_terminals = LNG_terminals[LNG_terminals['Status'].isin(['Construction', 'Operating'])]
LNG_terminals = LNG_terminals.dropna(subset=['Latitude', 'Longitude'])
LNG_terminals['Distance_km'] = LNG_terminals.apply(
    lambda row: geodesic(island_coords, (row['Latitude'], row['Longitude'])).kilometers,
    axis=1
)
closest_terminal = LNG_terminals.loc[LNG_terminals['Distance_km'].idxmin()]
LNG_terminal_lat = closest_terminal['Latitude']
LNG_terminal_lon = closest_terminal['Longitude']
LNG_distance = closest_terminal['Distance_km']

# 使用3小时重采样后的需求数据
H_load_demand = demand_data_3h['heating_demand'].tolist()
C_load_demand = demand_data_3h['cooling_demand'].tolist()
E_load_demand = E_demand['Power (kW)'].tolist()
H_load_demand[0] = 0
C_load_demand[0] = 0
E_load_demand[0] = 0


### 系统能源设备的参数 ###
# WT风电 PV光伏 WEC波浪能 EB电锅炉 AC空调 CHP热电联产机组 PEM质子交换膜电解槽 FC燃料电池 ESS电化学储能 TES热能储存 CES冷能储存 LNG液化天然气 LNGV LNG气化器 H2S氢气储存      
devices = ['WT', 'PV', 'LNG','WEC','CHP','EB','AC', 'PEM','FC','LNGV','ESS', 'TES','CES', 'H2S']
investment_cost = {'WT': 1392,'PV': 1377, 'WEC': 6000,'AC':150, 'EB': 250,'CHP': 1300,'PEM': 1371, 'FC': 3000, 'LNG': 700,'LNGV': 500, 'ESS': 1365, 
    'TES': 250,'CES': 250 ,'H2S': 50
}
fixed_om_cost = {'WT': 43, 'PV': 23,'LNG': 14,'WEC': 300,'CHP': 26,'EB': 5,'AC':3, 'PEM': 41,'FC': 90,'LNGV': 25,'ESS': 34,'TES': 6,'CES': 6, 'H2S': 1.2 
}

efficiency = {
    'CHP': (0.4, 0.5), 'EB': 0.9, 'PEM': 0.8, 'LNGV': (500, 0.01, 0.99), 'FC': (0.6,0.5), 'AC': 3.5, 
    'ESS': (0.9, 0.9), 'TES': (0.9, 0.9),'CES': (0.85, 0.85),'H2S': (0.95, 0.95)   
}

wave_length = 1000 

LNG_value = 6300  # kWh/m3
LNG_cost = 300 # ＄/m3
LNG_trans_cost = 0.0002 # ＄/m3/km
LNG_fixed_cost = 100000 # ＄

gas_heat_value = 9.97 # kW·h/m3 
# 弃风弃光和削减负荷的惩罚系数
# 假设孤岛能源系统的买电价格为0.5美元/kWh
penalty_renew_dis = 1
penalty_hot_dis = 0.01
penalty_cold_dis = 0.15
penalty_load_shed = 50

delta_ESS = 0.0001  # 储电自耗率
mu_ESS_in, mu_ESS_out = efficiency['ESS']
delta_TES = 0.005  # 储热自耗率
mu_TES_in, mu_TES_out = efficiency['TES']
delta_CES = 0.005  # 储冷自耗率
mu_CES_in, mu_CES_out = efficiency['CES']
delta_H2S = 0.0001  # 储氢自耗率
mu_H2S_in, mu_H2S_out = efficiency['H2S']
delta_t = 3

capacity_config_1 = {
    'WT': {'min': 0, 'max': wind_power.max()},
    'PV': {'min': 0, 'max': pv_power.max()},
    'WEC': {'min': 0, 'max': wave_power.max() * wave_length},
    'LNG': {'min': 0, 'max': 2000},
    'CHP': {'min': 0, 'max': 10000},
    'EB': {'min': 0, 'max': 10000},
    'AC': {'min': 0, 'max': 10000},
    'PEM': {'min': 0, 'max': 10000},
    'FC': {'min': 0, 'max': 10000},
    'LNGV': {'min': 0, 'max': 10000},
    'ESS': {'min': 0, 'max': 30000},
    'TES': {'min': 0, 'max': 30000},
    'CES': {'min': 0, 'max': 30000},
    'H2S': {'min': 0, 'max': 30000}
}

 
def integrated_optimization_model():
    T = 2928  # 时间段数量 (3小时分辨率)
    
    # LNG周期性采购参数
    purchase_cycle_length = 112  # 14天 * 24小时 / 3小时 = 112个时间步
    n_purchase_cycles = (T + purchase_cycle_length - 1) // purchase_cycle_length  # 向上取整
    
    model = gp.Model("LowerLevel")
    model.setParam('OutputFlag', 1)  # Gurobi输出
    model.setParam('OptimalityTol', 1e-4)     
    model.setParam('MIPGap', 0.01)
    model.setParam('Threads', 128)
    model.setParam('ConcurrentMIP', 2)
    model.setParam('Method', 3)      # 使用内点法 Barrier 方法
    # model.setParam('Heuristics', 0.1)  # 增加启发式搜索的力度
    model.setParam('MIPFocus', 2)  # 让求解器专注于提升下界
    model.setParam('Presolve', 2)  # 使用更高级的预处理选项
    model.setParam('FeasibilityTol', 1e-5)  # 约束的可接受误差范围
    model.setParam('TimeLimit', 1200)      # 求解时间限制

    # 定义决策变量
    capacity_dict = model.addVars(devices, lb=0, ub=[capacity_config_1[d]['max'] for d in devices], vtype=GRB.CONTINUOUS, name="capacity")
    output = model.addVars(devices, range(T), vtype=GRB.CONTINUOUS, name="output")
    # 电
    E_ESS = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="E_ESS")
    P_ESS_net = model.addVars(range(T), vtype=GRB.CONTINUOUS, lb=-GRB.INFINITY, name="P_ESS_net")  # 净功率，正值为放电，负值为充电
    # 热
    E_TES = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="E_TES")
    P_TES_net = model.addVars(range(T), vtype=GRB.CONTINUOUS, lb=-GRB.INFINITY, name="P_TES_net")  # 净功率，正值为放热，负值为储热
    # 冷
    E_CES = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="E_CES")
    P_CES_net = model.addVars(range(T), vtype=GRB.CONTINUOUS, lb=-GRB.INFINITY, name="P_CES_net")  # 净功率，正值为制冷，负值为储冷
    # 氢
    E_H2S = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="E_H2S")
    P_H2S_net = model.addVars(range(T), vtype=GRB.CONTINUOUS, lb=-GRB.INFINITY, name="P_H2S_net")  # 净功率，正值为释放氢气，负值为储氢
    # 弃风弃光弃波浪能
    curtailed_WT = model.addVars(range(T), vtype=GRB.CONTINUOUS, name=f"curtailed_WT")
    curtailed_PV = model.addVars(range(T), vtype=GRB.CONTINUOUS, name=f"curtailed_PV")
    curtailed_WEC = model.addVars(range(T), vtype=GRB.CONTINUOUS, name=f"curtailed_WEC")
    # 定义可用最大发电量变量
    available_WT = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="available_WT")
    available_PV = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="available_PV")
    available_WEC = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="available_WEC")
    # 其他设备变量
    gas_consumption = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="gas_consumption")
    CHP_electric_output = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="CHP_electric_output")
    CHP_heat_output = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="CHP_heat_output")
    FC_electric_output = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="FC_electric_output")
    FC_heat_output = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="FC_heat_output")
    hydrogen_consumption_FC = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="hydrogen_consumption_FC")
    LNGV_cold_output = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="LNGV_cold_output")
    LNGV_gas_output = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="LNGV_gas_output")
    power_consumption_EB = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="power_consumption_EB")
    power_consumption_PEM = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="power_consumption_PEM")
    power_consumption_LNGV = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="power_consumption_LNGV")
    power_consumption_AC = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="power_consumption_AC")
    
    LNG_get = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="LNG_in") # 购买 LNG m3
    LNG_storage = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="LNG_storage")
    LNG_purchase = model.addVars(range(n_purchase_cycles), vtype=gp.GRB.BINARY, name="LNG_purchase") # 周期性购买LNG决策
    # 添加场景相关的LNG变量
    P_cold_dis = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="P_cold_dis")
    P_hot_dis = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="P_hot_dis")
    P_gas_dis = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="P_gas_dis")
    P_Dload_E = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="P_Dload_E")  # 削减负荷功率
    P_Dload_H = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="P_Dload_H") 
    P_Dload_C = model.addVars(range(T), vtype=GRB.CONTINUOUS, name="P_Dload_C") 
    
    # 目标函数：最小化运行成本
    # 各项成本的定义
    r = 0.05  # 系统的年化率
    n = 20    # 设备的使用年限
    annualized_investment_cost = gp.quicksum(
        capacity_dict[d] * investment_cost[d] * (r * (1 + r)**n) / ((1 + r)**n - 1) 
        for d in devices
    )
    
    LNG_cost_total = (gp.quicksum(LNG_get[t] * (LNG_cost + LNG_trans_cost * LNG_distance) for t in range(T))  # LNG 购买和运输成本
                        + LNG_fixed_cost * gp.quicksum(LNG_purchase[c] for c in range(n_purchase_cycles)) ) # 每个周期购买的固定成本
                        # + gp.quicksum(LNG_storage[t] * maintenance_rate for t in range(T)) ) # 运行维护成本                               
    fixed_om_cost_total = gp.quicksum(fixed_om_cost[device] * capacity_dict[device] for device in devices)  # 固定运维成本
    power_discard_cost = gp.quicksum((penalty_hot_dis * P_hot_dis[t] + penalty_cold_dis * P_cold_dis[t]) * 3 for t in range(T))  # 弃能成本
    renew_curtailment_cost = gp.quicksum(penalty_renew_dis * (curtailed_WT[t] + curtailed_PV[t] + curtailed_WEC[t]) * 3 for t in range(T)) # 弃风弃光弃波浪能成本 
    load_shedding_cost_total = gp.quicksum(penalty_load_shed * (P_Dload_E[t] + P_Dload_H[t] + P_Dload_C[t]) * 3 for t in range(T))  # 削减负荷成本
    total_operating_cost = LNG_cost_total + fixed_om_cost_total + power_discard_cost  + renew_curtailment_cost + load_shedding_cost_total

    model.setObjective(annualized_investment_cost + total_operating_cost, GRB.MINIMIZE)
    M_lng = capacity_config_1['LNG']['max']  
    epsilon = 1e-3
    # 添加约束条件
    # 设置输出上限为容量配置
    for device in devices:
        for t in range(T):
            model.addConstr(output[device, t] <= capacity_dict[device], name=f"{device}_capacity_limit_{t}")

    for t in range(T):
         # WT风电和PV光伏约束
        model.addConstr(output['WT', t] >= 0, name=f"WT_min_output_{t}")
        model.addConstr(output['WT', t] <= wind_power[t], name=f"WT_max_output1_{t}")
        model.addConstr(output['WT', t] <= capacity_dict['WT'], name=f"WT_max_output2_{t}")
        model.addConstr(output['PV', t] >= 0, name=f"PV_min_output_{t}")
        model.addConstr(output['PV', t] <= pv_power[t], name=f"PV_max_output1_{t}")
        model.addConstr(output['PV', t] <= capacity_dict['PV'], name=f"PV_max_output2_{t}")
        # WEC波浪能约束
        model.addConstr(output['WEC', t] >= 0, name=f"WEC_min_output_{t}")
        model.addConstr(output['WEC', t] <= capacity_dict['WEC'], name=f"WEC_max_output_{t}") 
        model.addConstr(output['WEC', t] <= wave_power[t] * wave_length, name=f"WEC_max_output1_{t}")
        # LNG液化天然气约束
        if t == 0:
            model.addConstr(LNG_storage[0] == 0, name="LNG_initial_storage")
        else:
            model.addConstr(LNG_storage[t] == LNG_storage[t - 1] + LNG_get[t-1] - output['LNG', t-1],name=f"LNG_balance_{t}")
        # model.addConstr(LNG_storage[T-1] == LNG_storage[0],name= f"LNG_cyclic_constraint")
        model.addConstr(LNG_storage[t] >= 0, name=f"LNG_min_storage_{t}")
        model.addConstr(LNG_storage[t] <= capacity_dict['LNG'], name=f"LNG_max_storage_{t}")
        model.addConstr(output['LNG', t] >= 0, name=f"LNG_min_output_{t}")
        model.addConstr(output['LNG', t] <= LNG_storage[t], name=f"LNG_max_output_{t}")  
        model.addConstr(LNG_get[t] <= capacity_dict['LNG'], name=f"LNG_get_{t}")
        # 确定当前时间步属于哪个采购周期
        cycle_index = t // purchase_cycle_length
        cycle_first_timestep = cycle_index * purchase_cycle_length
        
        if cycle_index < n_purchase_cycles and t == cycle_first_timestep:
            # 只在每个周期的第一个时间步允许购买LNG（瞬时事件）
            model.addConstr(LNG_get[t] <= M_lng * LNG_purchase[cycle_index], name=f"LNG_purchase_upper_{t}")
            model.addConstr(LNG_get[t] >= epsilon * LNG_purchase[cycle_index], name=f"LNG_purchase_minimum_{t}")
        else:
            # 在其他时间步不允许购买LNG
            model.addConstr(LNG_get[t] == 0, name=f"LNG_no_purchase_{t}")
        # 添加弃电量的计算约束
        # 对于风电
        model.addConstr(available_WT[t] <= wind_power[t], name=f"available_WT_wind_limit_{t}")
        model.addConstr(available_WT[t] <= capacity_dict['WT'], name=f"available_WT_capacity_limit_{t}")
        # 对于光伏
        model.addConstr(available_PV[t] <= pv_power[t], name=f"available_PV_solar_limit_{t}")
        model.addConstr(available_PV[t] <= capacity_dict['PV'], name=f"available_PV_capacity_limit_{t}")
        # 对于波浪能
        model.addConstr(available_WEC[t] <= wave_power[t] * wave_length, name=f"available_WEC_resource_limit_{t}")
        model.addConstr(available_WEC[t] <= capacity_dict['WEC'], name=f"available_WEC_capacity_limit_{t}")
        # 计算弃能量
        model.addConstr(curtailed_WT[t] == available_WT[t] - output['WT', t], name=f"curtailed_WT_calc_{t}")
        model.addConstr(curtailed_PV[t] == available_PV[t] - output['PV', t], name=f"curtailed_PV_calc_{t}")
        model.addConstr(curtailed_WEC[t] == available_WEC[t] - output['WEC', t], name=f"curtailed_WEC_calc_{t}")
        
        ## 组件
        # CHP燃气轮机约束
        eta_CHP_E, eta_CHP_H = efficiency['CHP']
        model.addConstr(output['CHP', t] == CHP_electric_output[t] + CHP_heat_output[t], name=f"CHP_output_balance_{t}")
        model.addConstr(gas_consumption[t] == CHP_electric_output[t] / (eta_CHP_E * gas_heat_value), name=f"CHP_gas_constraint_{t}")
        model.addConstr(CHP_heat_output[t] == CHP_electric_output[t] * eta_CHP_H, name=f"CHP_heat_constraint_{t}")
        model.addConstr(output['CHP', t] >= 0, name=f"CHP_min_output_{t}")
        model.addConstr(output['CHP', t] <= capacity_dict['CHP'], name=f"CHP_max_output_{t}")
        # EB电锅炉约束
        eta_EB = efficiency['EB']
        model.addConstr(power_consumption_EB[t] == output['EB', t] / eta_EB, name=f"EB_power_constraint_{t}")
        model.addConstr(output['EB', t] >= 0, name=f"EB_min_output_{t}")
        model.addConstr(output['EB', t] <= capacity_dict['EB'], name=f"EB_max_output_{t}")
        # AC空调约束
        eta_AC = efficiency['AC']
        model.addConstr(power_consumption_AC[t] == output['AC', t] / eta_AC, name=f"AC_power_constraint_{t}")
        model.addConstr(output['AC', t] >= 0, name=f"AC_min_output_{t}")
        model.addConstr(output['AC', t] <= capacity_dict['AC'], name=f"AC_max_output_{t}")
        # PEM电解水制氢约束
        eta_PEM = efficiency['PEM']
        model.addConstr(power_consumption_PEM[t] == output['PEM', t] / eta_PEM, name=f"PEM_constraint_{t}")
        model.addConstr(output['PEM', t] >= 0, name=f"PEM_min_output_{t}")
        model.addConstr(output['PEM', t] <= capacity_dict['PEM'], name=f"PEM_max_output_{t}")
        # FC氢燃料电池约束
        eta_FC_E, eta_FC_H = efficiency['FC']
        model.addConstr(hydrogen_consumption_FC[t] == FC_electric_output[t] / eta_FC_E, name=f"FC_hydrogen_constraint_{t}")
        model.addConstr(FC_heat_output[t] == FC_electric_output[t] * eta_FC_H, name=f"FC_heat_constraint_{t}")
        model.addConstr(FC_electric_output[t] >= 0, name=f"FC_min_output_{t}")
        model.addConstr(FC_electric_output[t] + FC_heat_output[t] <= capacity_dict['FC'], name=f"FC_max_output_{t}")
        model.addConstr(output['FC', t] == FC_electric_output[t] + FC_heat_output[t],name= f"FC_output_balance_{t}")
        # LNGV气化器约束 接入电网
        eta_LNGV, eta_LNGV_C, eta_LNGV_G = efficiency['LNGV'] 
        model.addConstr(power_consumption_LNGV[t] == LNGV_gas_output[t] / eta_LNGV,  name=f"LNGV_power_constraint_{t}")
        model.addConstr(output['LNG', t] * LNG_value == (LNGV_gas_output[t] / eta_LNGV_G) * 3, name=f"LNGV_LNG_constraint_{t}")
        model.addConstr(LNGV_cold_output[t] == eta_LNGV_C * (LNGV_gas_output[t] / eta_LNGV_G), name=f"LNGV_cold_constraint_{t}")
        model.addConstr(LNGV_gas_output[t] >= 0, name=f"LNGV_min_output_{t}")
        model.addConstr(LNGV_gas_output[t] + LNGV_cold_output[t] <= capacity_dict['LNGV'],name= f"LNGV_max_output_{t}")
        model.addConstr(output['LNGV', t] == LNGV_cold_output[t] + LNGV_gas_output[t], name=f"LNGV_output_balance_{t}")
        model.addConstr(LNGV_gas_output[t] >= gas_consumption[t] * gas_heat_value , name=f"LNGV_gas_output_vs_consumption_{t}")
        ## 储存
        # 电储能约束
        model.addConstr(E_ESS[t] >= 0, name=f"ESS_min_storage_{t}")
        model.addConstr(E_ESS[t] <= capacity_dict['ESS'], name=f"ESS_max_storage_{t}")
        model.addConstr(P_ESS_net[t] <= capacity_dict['ESS']/4, name=f"ESS_max_discharge_{t}")  # 最大放电功率
        model.addConstr(P_ESS_net[t] >= -capacity_dict['ESS']/4, name=f"ESS_max_charge_{t}")  # 最大充电功率（负值）
        if t == 0:
            model.addConstr(E_ESS[t] == 0, name=f"ESS_initial_{t}")
        else:
            model.addConstr(E_ESS[t] == E_ESS[t-1] * (1 - delta_ESS) - P_ESS_net[t-1] * 3, name=f"ESS_storage_balance_{t}")  # 正的P_ESS_net表示放电，所以用减号
        model.addConstr(E_ESS[T-1] == E_ESS[0], name=f"ESS_cyclic_constraint")
        # 热储能约束
        model.addConstr(E_TES[t] >= 0, name=f"TES_min_storage_{t}")
        model.addConstr(E_TES[t] <= capacity_dict['TES'], name=f"TES_max_storage_{t}")
        model.addConstr(P_TES_net[t] <= capacity_dict['TES']/4, name=f"TES_max_discharge_{t}")
        model.addConstr(P_TES_net[t] >= -capacity_dict['TES']/4, name=f"TES_max_charge_{t}")
        if t == 0:
            model.addConstr(E_TES[t] == 0, name=f"TES_initial_{t}")
        else:
            model.addConstr(E_TES[t] == E_TES[t-1] * (1 - delta_TES) - P_TES_net[t-1] * 3, name=f"TES_storage_balance_{t}")
        model.addConstr(E_TES[T-1] == E_TES[0], name=f"TES_cyclic_constraint")
        # 冷储能约束
        model.addConstr(E_CES[t] >= 0, name=f"CES_min_storage_{t}")
        model.addConstr(E_CES[t] <= capacity_dict['CES'], name=f"CES_max_storage_{t}")
        model.addConstr(P_CES_net[t] <= capacity_dict['CES']/4, name=f"CES_max_discharge_{t}")
        model.addConstr(P_CES_net[t] >= -capacity_dict['CES']/4, name=f"CES_max_charge_{t}")
        if t == 0:
            model.addConstr(E_CES[t] == 0, name=f"CES_initial_{t}")
        else:
            model.addConstr(E_CES[t] == E_CES[t-1] * (1 - delta_CES) - P_CES_net[t-1] * 3, name=f"CES_storage_balance_{t}")
        model.addConstr(E_CES[T-1] == E_CES[0], name=f"CES_cyclic_constraint")
        # 氢储能约束
        model.addConstr(E_H2S[t] >= 0, name=f"H2S_min_storage_{t}")
        model.addConstr(E_H2S[t] <= capacity_dict['H2S'], name=f"H2S_max_storage_{t}")
        model.addConstr(P_H2S_net[t] <= capacity_dict['H2S']/4, name=f"H2S_max_discharge_{t}")
        model.addConstr(P_H2S_net[t] >= -capacity_dict['H2S']/4, name=f"H2S_max_charge_{t}")
        if t == 0:
            model.addConstr(E_H2S[t] == 0, name=f"H2S_initial_{t}")
        else:
            model.addConstr(E_H2S[t] == E_H2S[t-1] * (1 - delta_H2S) - P_H2S_net[t-1] * 3, name=f"H2S_storage_balance_{t}")
        model.addConstr(E_H2S[T-1] == E_H2S[0], name=f"H2S_cyclic_constraint")
        
    ## 平衡约束
    for t in range(T):
        # 电
        model.addConstr(output['WT', t] + output['PV', t] + output['WEC', t] +
                        CHP_electric_output[t] + FC_electric_output[t] - power_consumption_PEM[t] - power_consumption_EB[t] - power_consumption_LNGV[t]- power_consumption_AC[t]+
                        P_ESS_net[t] - E_load_demand[t] + P_Dload_E[t] == 0, name=f"E_power_balance_{t}")
        # 热
        model.addConstr(output['EB', t] + CHP_heat_output[t] + FC_heat_output[t] +
                        P_TES_net[t] - H_load_demand[t] + P_Dload_H[t] == P_hot_dis[t], name=f"H_power_balance_{t}")
        # 冷
        model.addConstr(LNGV_cold_output[t] + output['AC', t] + P_CES_net[t] - C_load_demand[t] + P_Dload_C[t] == P_cold_dis[t], name=f"C_power_balance_{t}")
        # 气
        model.addConstr(LNGV_gas_output[t] - gas_consumption[t] * gas_heat_value == P_gas_dis[t], name=f"G_power_balance_{t}")
        # 氢
        model.addConstr(output['PEM', t] + P_H2S_net[t] - hydrogen_consumption_FC[t] == 0, name=f"HY_power_balance_{t}")
    
    # 定义并约束 Normalized EENS (不考虑灾害情景)
    reliability_level = 0.001  # 可靠性标准：允许总缺口能量不超过总需求的0.1%
    # 计算年度总需求 (Total Annual Demand)
    # 乘以3将3小时功率转换为年度总能量需求 (kWh)
    total_demand_E = sum(E_load_demand) * 3
    total_demand_H = sum(H_load_demand) * 3
    total_demand_C = sum(C_load_demand) * 3
    # 计算未服务能量 (EENS = Energy Not Served) - 简化为削减负荷
    # 乘以3将3小时功率转换为能量 (kWh)
    EENS_E = gp.quicksum(P_Dload_E[t] * 3 for t in range(T))
    EENS_H = gp.quicksum(P_Dload_H[t] * 3 for t in range(T))
    EENS_C = gp.quicksum(P_Dload_C[t] * 3 for t in range(T))
    # 添加 Normalized EENS 约束
    # 约束： EENS / Total_Demand <= reliability_level
    model.addConstr(EENS_E <= reliability_level * total_demand_E, name="Normalized_EENS_limit_E")
    model.addConstr(EENS_H <= reliability_level * total_demand_H, name="Normalized_EENS_limit_H")
    model.addConstr(EENS_C <= reliability_level * total_demand_C, name="Normalized_EENS_limit_C")
    # 优化模型
    # model.write("model.lp")
    model.optimize()
     
    # 检查优化状态
    if model.status == GRB.INFEASIBLE:
        print("Model is infeasible. Skipping this solution.")
        return None, None, float('inf'), None
    elif model.status == GRB.OPTIMAL or model.status == GRB.TIME_LIMIT:
        # 如果达到最优解或者时间限制但有可行解
        if model.status == GRB.TIME_LIMIT:
            print(f"Time limit reached. Using best solution found with gap {model.MIPGap:.2%}")
            # 确认有可行解
            if model.SolCount == 0:
                print("No feasible solution found within time limit.")
                return None, None, float('inf'), None
        
        all_cost = model.objVal
        print(f"All Cost: {all_cost}")
        
        optimal_capacities = {d: capacity_dict[d].X for d in devices}
        capacity_df = pd.DataFrame(list(optimal_capacities.items()), columns=['Device', 'Optimal_Capacity'])
        ################### 存储结果
        annualized_investment_cost = sum(optimal_capacities[d] * investment_cost[d] * (r * (1 + r)**n) / ((1 + r)**n - 1) for d in devices)
        LNG_cost_total = (gp.quicksum(LNG_get[t].X * (LNG_cost + LNG_trans_cost * LNG_distance) for t in range(T)).getValue()  # LNG 购买和运输成本
                + LNG_fixed_cost * gp.quicksum(LNG_purchase[c].X for c in range(n_purchase_cycles)).getValue())  # 每个周期购买的固定成本
        fixed_om_cost_total = gp.quicksum(fixed_om_cost[device] * capacity_dict[device] for device in devices).getValue()  # 固定运维成本
        power_discard_cost = gp.quicksum((penalty_hot_dis * P_hot_dis[t].X + penalty_cold_dis * P_cold_dis[t].X) * 3 for t in range(T)).getValue()  # 弃能成本
        renew_curtailment_cost = gp.quicksum(penalty_renew_dis * (curtailed_WT[t].X + curtailed_PV[t].X + curtailed_WEC[t].X) * 3 for t in range(T)).getValue()  # 弃风弃光弃波浪能成本 
        load_shedding_cost_total = gp.quicksum(penalty_load_shed * (P_Dload_E[t].X + P_Dload_H[t].X + P_Dload_C[t].X) * 3 for t in range(T)).getValue()  # 削减负荷成本
        total_operating_cost = LNG_cost_total + fixed_om_cost_total + power_discard_cost + renew_curtailment_cost + load_shedding_cost_total
        total_annual_cost = annualized_investment_cost + total_operating_cost
        cost_data = {
        "Cost_Item": [
            "Annualized Investment Cost", 
            "LNG Purchase Cost", 
            "Fixed Operation & Maintenance Cost",
            "Energy Discard Cost (Heat/Cold)", 
            "Renewable Curtailment Cost",
            "Load Shedding Cost", 
            "--- Total Operating Cost ---", 
            "--- TOTAL ANNUAL COST ---"
        ],
        "Cost_Value": [
            annualized_investment_cost, 
            LNG_cost_total, 
            fixed_om_cost_total,
            power_discard_cost, 
            renew_curtailment_cost, 
            load_shedding_cost_total,
            total_operating_cost,
            total_annual_cost
        ]
    }
        cost_df = pd.DataFrame(cost_data)

        # 保存优化结果
        results = pd.DataFrame(index=range(T), columns=devices + ['LNG_get','LNG_storage','E_ESS','E_TES','E_CES','E_H2S', 'P_cold_dis','P_hot_dis','P_gas_dis','P_Dload_E', 'P_Dload_H', 'P_Dload_C', 'E_supply', 'E_demand','H_supply', 'H_demand',  'C_supply', 'C_demand', 'CHP_gas_consumption', 'EB_power_consumption','AC_power_consumption', 'PEM_power_consumption', 'LNGV_power_consumption','FC_hydrogen_consumption',  'CHP_electric_output', 'CHP_heat_output', 'FC_electric_output', 'FC_heat_output', 'LNGV_cold_output', 'LNGV_gas_output'])
        
        for device in devices:
            if device in ['ESS', 'TES', 'CES', 'H2S']:
                # 对于储能设施，直接使用净功率
                results[device] = [P_ESS_net[t].X if device == 'ESS' else
                                P_TES_net[t].X if device == 'TES' else
                                P_CES_net[t].X if device == 'CES' else
                                P_H2S_net[t].X for t in range(T)]
            else:
                results[device] = [output[device, t].X for t in range(T)]

        results['LNG_get'] = [LNG_get[t].X for t in range(T)]     
        results['LNG_storage'] = [LNG_storage[t].X for t in range(T)]
        
        # 添加LNG购买周期信息到结果中，便于分析
        lng_purchase_info = []
        for t in range(T):
            cycle_index = t // purchase_cycle_length
            cycle_first_timestep = cycle_index * purchase_cycle_length
            if t == cycle_first_timestep and cycle_index < n_purchase_cycles:
                lng_purchase_info.append(LNG_purchase[cycle_index].X)  # 该周期是否购买LNG
            else:
                lng_purchase_info.append(0)  # 非购买时间步标记为0
        results['LNG_purchase_decision'] = lng_purchase_info      
        results['P_cold_dis'] = [P_cold_dis[t].X for t in range(T)]
        results['P_hot_dis'] = [P_hot_dis[t].X for t in range(T)]
        results['P_gas_dis'] = [P_gas_dis[t].X for t in range(T)]
        results['P_Dload_E'] = [P_Dload_E[t].X for t in range(T)]
        results['P_Dload_H'] = [P_Dload_H[t].X for t in range(T)]
        results['P_Dload_C'] = [P_Dload_C[t].X for t in range(T)]
        results['E_ESS'] = [E_ESS[t].X for t in range(T)]
        results['E_TES'] = [E_TES[t].X for t in range(T)]
        results['E_CES'] = [E_CES[t].X for t in range(T)]
        results['E_H2S'] = [E_H2S[t].X for t in range(T)]
        
        for t in range(T):
            # 记录能源消耗
            results.at[t, 'CHP_gas_consumption'] = gas_consumption[t].X * gas_heat_value
            results.at[t, 'EB_power_consumption'] = power_consumption_EB[t].X
            results.at[t, 'AC_power_consumption'] = power_consumption_AC[t].X
            results.at[t, 'PEM_power_consumption'] = power_consumption_PEM[t].X
            results.at[t, 'LNGV_power_consumption'] = power_consumption_LNGV[t].X
            results.at[t, 'FC_hydrogen_consumption'] = hydrogen_consumption_FC[t].X
            # 记录能源输出
            results.at[t, 'CHP_electric_output'] = CHP_electric_output[t].X
            results.at[t, 'CHP_heat_output'] = CHP_heat_output[t].X
            results.at[t, 'FC_electric_output'] = FC_electric_output[t].X
            results.at[t, 'FC_heat_output'] = FC_heat_output[t].X
            results.at[t, 'LNGV_cold_output'] = LNGV_cold_output[t].X
            results.at[t, 'LNGV_gas_output'] = LNGV_gas_output[t].X
            # 计算不同能源的供给
            results.at[t, 'E_supply'] = output['WT', t].X + output['PV', t].X + output['WEC', t].X + CHP_electric_output[t].X + FC_electric_output[t].X - power_consumption_AC[t].X - power_consumption_PEM[t].X - power_consumption_EB[t].X - power_consumption_LNGV[t].X + P_ESS_net[t].X
            results.at[t, 'H_supply'] = output['EB', t].X + CHP_heat_output[t].X + FC_heat_output[t].X + P_TES_net[t].X
            results.at[t, 'C_supply'] = LNGV_cold_output[t].X + output['AC', t].X + P_CES_net[t].X
            # 记录不同能源的负荷
            results.at[t, 'E_demand'] = E_load_demand[t]
            results.at[t, 'H_demand'] = H_load_demand[t] 
            results.at[t, 'C_demand'] = C_load_demand[t] 

        return capacity_df, results, all_cost, cost_df
    else:
        print(f"Unexpected model status: {model.status}. Skipping this solution.")
        return None, None, float('inf'), None

capacity_df, results, all_cost, cost_df = integrated_optimization_model()
cost_df.to_csv(f'output_sample/{island_lat}_{island_lon}_best_cost_free.csv', index=False)
capacity_df.to_csv(f'output_sample/{island_lat}_{island_lon}_capacity_free.csv', index=False)
results.to_csv(f'output_sample/{island_lat}_{island_lon}_results_free.csv', index=False)