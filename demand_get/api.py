import requests
import pandas as pd
import json
import time
import logging
from datetime import datetime, timedelta
import os
from io import StringIO 

# ==============================================================================
# 1. 自定义异常类
# ==============================================================================
class RateLimitError(Exception):
    """当API明确返回速率限制错误时引发的自定义异常。"""
    pass

# ==============================================================================
# 2. API 数据获取函数
# ==============================================================================

##
# PV (光伏)
##
def get_pv(lat, lon, pop, token):
    api_base = 'https://www.renewables.ninja/api/'
    s = requests.session()
    s.headers = {'Authorization': 'Token ' + token}
    
    url = api_base + 'data/pv'
    azim = 180 if lat > 0 else 0
    
    # 限制人口输入值
    capacity_pop = min(pop, 500)
        
    args = {
        'lat': lat,
        'lon': lon,
        'date_from': '2020-01-01',
        'date_to': '2020-12-31',
        'dataset': 'merra2',
        'capacity': 2 * capacity_pop,
        'system_loss': 0.1,
        'tracking': 2,
        'tilt': abs(lat),
        'azim': azim,
        'format': 'json'
    }
    try:
        r = s.get(url, params=args, timeout=60) # 增加超时时间
        r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        if 'Reached limit' in r.text and 'Expected available in' in r.text:
            raise RateLimitError(r.text)
        print(f"HTTP Error in get_pv: {err}")
        print(f"Response Text: {r.text}")
        raise
        
    parsed_response = json.loads(r.text)
    json_string = json.dumps(parsed_response['data'])
    data_pv = pd.read_json(StringIO(json_string), orient='index')
    return data_pv

##
# Wind (风能)
##
def get_wind(lat, lon, pop, token):
    api_base = 'https://www.renewables.ninja/api/'
    s = requests.session()
    s.headers = {'Authorization': 'Token ' + token}
    
    url = api_base + 'data/wind'
    
    capacity_pop = min(pop, 500)
        
    args = {
        'lat': lat,
        'lon': lon,
        'date_from': '2020-01-01',
        'date_to': '2020-12-31',
        'capacity': 2 * capacity_pop,
        'height': 80,
        'turbine': 'Vestas V80 2000',
        'format': 'json'
    }

    try:
        r = s.get(url, params=args, timeout=60)
        r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        if 'Reached limit' in r.text and 'Expected available in' in r.text:
            raise RateLimitError(r.text)
        print(f"HTTP Error in get_wind: {err}")
        print(f"Response Text: {r.text}")
        raise
        
    parsed_response = json.loads(r.text)
    json_string = json.dumps(parsed_response['data'])
    data_wind = pd.read_json(StringIO(json_string), orient='index')
    return data_wind

##
# Demand (需求)
##
def get_demand(lat, lon, pop, region, token):
    capacity_pop = min(pop, 500)
        
    region_params = {
        'APAC': {
            'heating_threshold': 11.9, 'cooling_threshold': 20.4, 'heating_power': 0.0566 * capacity_pop,
            'cooling_power': 0.052 * capacity_pop, 'smoothing': 0.73, 'solar_gains': 0.014,
            'wind_chill': -0.12, 'humidity_discomfort': 0.036
        },
        'Europe': {
            'heating_threshold': 12.7, 'cooling_threshold': 20.4, 'heating_power': 0.0642 * capacity_pop,
            'cooling_power': 0.016 * capacity_pop, 'smoothing': 0.62, 'solar_gains': 0.019,
            'wind_chill': -0.13, 'humidity_discomfort': 0.032
        },
        'US': {
            'heating_threshold': 9.7, 'cooling_threshold': 18.8, 'heating_power': 0.1023 * capacity_pop,
            'cooling_power': 0.059 * capacity_pop, 'smoothing': 0.73, 'solar_gains': 0.011,
            'wind_chill': -0.10, 'humidity_discomfort': 0.022
        },
        'Unknown': { # Fallback for unknown regions
            'heating_threshold': 11.9, 'cooling_threshold': 20.4, 'heating_power': 0.0566 * capacity_pop,
            'cooling_power': 0.052 * capacity_pop, 'smoothing': 0.73, 'solar_gains': 0.014,
            'wind_chill': -0.12, 'humidity_discomfort': 0.036
        }
    }
    params = region_params.get(region, region_params['Unknown'])
    
    api_base = 'https://www.renewables.ninja/api/'
    s = requests.session()
    s.headers = {'Authorization': 'Token ' + token}
    
    url = api_base + 'data/demand'

    args = {
        'lat': lat, 'lon': lon, 'date_from': '2020-01-01', 'date_to': '2020-12-31',    
        'dataset': 'merra2', 'heating_threshold': params['heating_threshold'],  
        'cooling_threshold': params['cooling_threshold'], 'base_power': 0,
        'heating_power': params['heating_power'], 'cooling_power': params['cooling_power'],
        'smoothing': params['smoothing'], 'solar_gains': params['solar_gains'],
        'wind_chill': params['wind_chill'], 'humidity_discomfort': params['humidity_discomfort'],
        'use_diurnal_profile': 'true', 'format': 'json'            
    }

    try:
        r = s.get(url, params=args, timeout=60)
        r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        if 'Reached limit' in r.text and 'Expected available in' in r.text:
            raise RateLimitError(r.text)
        print(f"HTTP Error in get_demand: {err}")
        print(f"Response Text: {r.text}")
        raise
        
    parsed_response = json.loads(r.text)
    json_string = json.dumps(parsed_response['data'])
    data_demand = pd.read_json(StringIO(json_string), orient='index')
    return data_demand

# ==============================================================================
# 3. 智能 Token 管理器
# ==============================================================================
class TokenManager:
    def __init__(self, tokens, max_calls_per_hour=50, call_buffer=2):
        self.tokens = tokens
        self.api_limit = max_calls_per_hour
        self.effective_max_calls = max_calls_per_hour - call_buffer
        self.current_token_index = 0
        self.call_history = []
        self.token_cooldowns = {}
        self.setup_logging()
        self.logger.info(
            f"TokenManager已初始化。API限制: {self.api_limit}/小时, "
            f"有效限制 (带缓冲): {self.effective_max_calls}/小时。"
        )

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                # logging.FileHandler('api_batch_log.txt'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def clean_old_calls(self):
        one_hour_ago = datetime.now() - timedelta(hours=1)
        self.call_history = [(ts, idx) for ts, idx in self.call_history if ts > one_hour_ago]

    def mark_token_as_exhausted(self, token_index, duration_seconds=3600):
        expiry_time = datetime.now() + timedelta(seconds=duration_seconds)
        self.token_cooldowns[token_index] = expiry_time
        self.logger.warning(
            f"Token {token_index + 1} 已被服务器标记为耗尽，将冷却至 {expiry_time.strftime('%H:%M:%S')}。"
        )

    def get_available_token(self):
        while True: # --- 核心修改：使用无限循环来确保最终能返回一个Token ---
            self.clean_old_calls()
            
            # 遍历所有Token，寻找一个可用的
            start_index = self.current_token_index
            for i in range(len(self.tokens)):
                check_index = (start_index + i) % len(self.tokens)

                # 检查1：是否在冷却中
                if check_index in self.token_cooldowns:
                    if datetime.now() < self.token_cooldowns[check_index]:
                        continue 
                    else:
                        self.logger.info(f"Token {check_index + 1} 已结束冷却，恢复使用。")
                        del self.token_cooldowns[check_index]
                
                # 检查2：调用次数是否已满
                one_hour_ago = datetime.now() - timedelta(hours=1)
                token_calls = len([1 for ts, idx in self.call_history if idx == check_index and ts > one_hour_ago])
                
                if token_calls < self.effective_max_calls:
                    if self.current_token_index != check_index:
                        self.logger.info(f"主动切换到Token {check_index + 1} (最近一小时调用次数: {token_calls})")
                    self.current_token_index = check_index
                    return self.tokens[self.current_token_index] # 找到可用Token，跳出无限循环

            # --- 如果循环结束还没找到可用的Token，说明所有Token都不可用，执行等待逻辑 ---
            self.logger.warning("所有Token均不可用。计算最短等待时间...")
            
            wait_seconds_list = []
            
            # 计算因“冷却”而需要等待的时间
            for token_idx, expiry_time in self.token_cooldowns.items():
                 wait_seconds_list.append((expiry_time - datetime.now()).total_seconds())
            
            # --- 核心修改：实时计算每个Token的恢复倒计时 ---
            # 即使Token不在冷却列表中，如果它的调用次数已满，我们也需要计算它的恢复时间
            for i in range(len(self.tokens)):
                if i not in self.token_cooldowns: # 只检查不在冷却中的Token
                    token_specific_history = [ts for ts, idx in self.call_history if idx == i]
                    if len(token_specific_history) >= self.effective_max_calls:
                        # 如果调用次数已满，它的恢复时间取决于它最早的那个调用何时过期
                        oldest_call_for_this_token = min(token_specific_history)
                        recovery_time = (oldest_call_for_this_token + timedelta(hours=1) - datetime.now()).total_seconds()
                        wait_seconds_list.append(recovery_time)
            
            positive_wait_times = [s for s in wait_seconds_list if s > 0]
            
            if not positive_wait_times:
                # 这是一个理论上的边缘情况，如果发生，意味着逻辑有误或状态瞬间变化
                # 短暂等待后，让无限循环重新评估所有状态
                self.logger.warning("无法计算出正数的等待时间，将短暂停顿10秒后重试。")
                time.sleep(10)
                continue # 继续while循环的下一次迭代

            # 精确等待到最早恢复的那个Token
            wait_time = min(positive_wait_times)
            
            self.logger.info(f"等待 {wait_time:.0f} 秒以等待最近的Token恢复...")
            time.sleep(wait_time + 5) # 增加5秒缓冲
            
            # 等待结束后，while循环将自然地重新开始，再次评估所有Token的状态

    def record_api_call(self):
        self.call_history.append((datetime.now(), self.current_token_index))
        
    def get_status(self):
        self.clean_old_calls()
        status = {}
        now = datetime.now()
        one_hour_delta = timedelta(hours=1)
        
        for i in range(len(self.tokens)):
            # --- 核心修改：在状态报告中加入恢复倒计时 ---
            cooldown_status = ""
            # 1. 检查是否在冷却中
            if i in self.token_cooldowns and now < self.token_cooldowns[i]:
                remaining_seconds = (self.token_cooldowns[i] - now).total_seconds()
                cooldown_status = f" (冷却中, 剩 {int(remaining_seconds)}s)"
            else:
                # 2. 如果不在冷却中，检查调用次数是否已满
                token_specific_history = [ts for ts, idx in self.call_history if idx == i]
                calls = len(token_specific_history)
                if calls >= self.effective_max_calls:
                    # 如果满了，计算恢复时间
                    oldest_call_for_this_token = min(token_specific_history)
                    remaining_seconds = (oldest_call_for_this_token + one_hour_delta - now).total_seconds()
                    if remaining_seconds > 0:
                        cooldown_status = f" (等待恢复, 剩 {int(remaining_seconds)}s)"
            
            calls = len([1 for ts, idx in self.call_history if idx == i]) # 重新获取调用次数
            status[f'Token_{i+1}'] = f"{calls}/{self.effective_max_calls}{cooldown_status}"
            
        return status

# ==============================================================================
# 4. 批处理主函数
# ==============================================================================

def save_progress(completed_islands, progress_file='progress.txt'):
    with open(progress_file, 'w') as f:
        for island_id in completed_islands:
            f.write(f"{island_id}\n")

def load_progress(progress_file='progress.txt'):
    if not os.path.exists(progress_file):
        return set()
    with open(progress_file, 'r') as f:
        return set(line.strip() for line in f)

def batch_get_data(island_csv, tokens, output_dir='data', progress_file='progress.txt'):
    os.makedirs(output_dir, exist_ok=True)
    try:
        island_data = pd.read_csv(island_csv)
    except FileNotFoundError:
        print(f"错误: 输入文件 '{island_csv}' 未找到。请检查文件名和路径。")
        return 0, []

    token_manager = TokenManager(tokens, max_calls_per_hour=50, call_buffer=2)
    completed_islands = load_progress(progress_file)
    
    token_manager.logger.info(f"开始处理 {len(island_data)} 个岛屿的批处理任务")
    token_manager.logger.info(f"已完成: {len(completed_islands)} 个岛屿")
    
    successful_count = 0
    failed_islands = []
    
    for idx, row in island_data.iterrows():
        island_id = str(row['ID'])
        
        if island_id in completed_islands:
            continue
        
        island_lat, island_lon = row['Lat'], row['Long']
        pop, region = row['pop'], row['Region']
        
        max_retries = len(tokens)
        for attempt in range(max_retries):
            try:
                if attempt == 0:
                    token_manager.logger.info(f"正在处理岛屿 {island_id}: ({island_lat}, {island_lon})")
                
                # 获取Token
                current_token = token_manager.get_available_token()
                token_manager.logger.info(f"岛屿 {island_id} (尝试 {attempt + 1}/{max_retries}) - "
                                          f"使用Token {token_manager.current_token_index + 1}, "
                                          f"状态: {token_manager.get_status()}")
                
                # API调用
                time.sleep(1)
                pv_data = get_pv(island_lat, island_lon, pop, current_token)
                token_manager.record_api_call()
                
                current_token = token_manager.get_available_token()
                time.sleep(1)
                wt_data = get_wind(island_lat, island_lon, pop, current_token)
                token_manager.record_api_call()
                
                current_token = token_manager.get_available_token()
                time.sleep(1)
                demand_data = get_demand(island_lat, island_lon, pop, region, current_token)
                token_manager.record_api_call()
                
                # 保存数据
                pv_data.to_csv(f'{output_dir}/pv_{island_lat}_{island_lon}.csv', index_label='time')
                wt_data.to_csv(f'{output_dir}/wt_{island_lat}_{island_lon}.csv', index_label='time')
                demand_data.to_csv(f'{output_dir}/demand_{island_lat}_{island_lon}.csv', index_label='time')
                
                completed_islands.add(island_id)
                save_progress(completed_islands, progress_file)
                successful_count += 1
                token_manager.logger.info(f'成功处理岛屿 {island_id} ({len(completed_islands)}/{len(island_data)})')
                break 

            except RateLimitError as e:
                token_manager.logger.error(f"API速率限制！Token {token_manager.current_token_index + 1} 已被服务器拒绝。")
                wait_seconds = 3600
                try:
                    wait_seconds = int(str(e).split('Expected available in ')[1].split(' seconds')[0])
                except (IndexError, ValueError):
                    pass
                token_manager.mark_token_as_exhausted(token_manager.current_token_index, wait_seconds)
                token_manager.logger.info(f"立即尝试使用下一个可用Token重试岛屿 {island_id}...")
                continue

            except Exception as e:
                token_manager.logger.error(f"处理岛屿 {island_id} 时发生不可恢复的错误: {e}")
                failed_islands.append((island_id, str(e)))
                break
        else:
            token_manager.logger.error(f"为岛屿 {island_id} 的所有重试尝试均失败，将跳过此岛屿。")
            failed_islands.append((island_id, "All tokens exhausted or failed"))

    # ==============================================================================
    # 5. 任务总结
    # ==============================================================================
    token_manager.logger.info(f"\n{'='*15} 批处理任务完成 {'='*15}")
    token_manager.logger.info(f"总计岛屿数: {len(island_data)}")
    token_manager.logger.info(f"本次运行成功处理: {successful_count}")
    token_manager.logger.info(f"累计已完成: {len(completed_islands)}")
    token_manager.logger.info(f"处理失败: {len(failed_islands)}")
    token_manager.logger.info(f"最终Token状态: {token_manager.get_status()}")
    
    if failed_islands:
        token_manager.logger.error("\n失败的岛屿列表:")
        for island_id, reason in failed_islands:
            token_manager.logger.error(f"  - 岛屿ID: {island_id}, 原因: {reason}")
    
    return successful_count, failed_islands

