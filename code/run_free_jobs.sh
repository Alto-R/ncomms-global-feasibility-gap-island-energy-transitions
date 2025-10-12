#!/bin/bash

# --- 全局配置 ---
# 并行运行disaster_free.py计算任务 - 多岛屿同时计算
CSV_FILE="filtered_island_1898.csv"
MAIN_LOG="logs/main_log.log"
MAX_CONCURRENT_ISLANDS=20  # 最大并发岛屿数量，可根据系统资源调整

# --- 初始化日志文件 ---
> "$MAIN_LOG"  # 清空主日志文件

# --- 定义一个函数来检查日志文件中的MIPGap ---
# 参数: 1:log_file, 2:task_name, 3:island_id
check_mip_gap() {
    local log_file=$1
    local task_name=$2
    local island_id=$3
    local target_gap_percent=1.00

    # 使用grep查找包含关键字的行
    local gap_line=$(grep "Time limit reached. Using best solution found with gap" "$log_file")

    if [ -n "$gap_line" ]; then
        local final_gap=$(echo "$gap_line" | awk '{print $NF}' | tr -d '%')
        
        # 使用bc进行浮点数比较
        if (( $(echo "$final_gap > $target_gap_percent" | bc -l) )); then
            # 只将GAP检查失败的信息记录到主日志
            echo "GAP CHECK FAILED: Island $island_id, Task $task_name. Final Gap: ${final_gap}% > ${target_gap_percent}%" >> "$MAIN_LOG"
        fi
    fi
}

# --- 定义一个函数来运行单个岛屿的disaster_free计算，包含重试逻辑 ---
# 这个函数将被作为后台进程来执行
# 参数: 1:ID, 2:Lat, 3:Long, 4:Pop
run_island_disaster_free() {
    local ID=$1
    local Lat=$2
    local Long=$3
    local Pop=$4
    local LOG_FILE="logs/log_${ID}_disaster_free.log"
    local SCRIPT_NAME="disaster_free.py"

    echo "Island $ID: disaster_free started at $(date +'%Y-%m-%d %H:%M:%S')" >> "$MAIN_LOG"
    
    # 运行并重试逻辑，如果两次都失败，函数将以退出码 1 结束
    if ! python3 "$SCRIPT_NAME" --island_lat "$Lat" --island_lon "$Long" --pop "$Pop" >> "$LOG_FILE" 2>&1; then
        sleep 10
        if ! python3 "$SCRIPT_NAME" --island_lat "$Lat" --island_lon "$Long" --pop "$Pop" >> "$LOG_FILE" 2>&1; then
            echo "Island $ID: disaster_free FAILED at $(date +'%Y-%m-%d %H:%M:%S')" >> "$MAIN_LOG"
            exit 1 # 关键：后台任务通过退出码报告失败
        fi
    fi

    # 检查MIP Gap
    check_mip_gap "$LOG_FILE" "disaster_free" "$ID"
    
    echo "Island $ID: disaster_free completed at $(date +'%Y-%m-%d %H:%M:%S')" >> "$MAIN_LOG"
    exit 0 # 关键：后台任务通过退出码报告成功
}


# --- 主循环：批量并行处理岛屿 ---
# 首先读取所有岛屿信息到数组中
declare -a ISLANDS
while IFS=',' read -r ID Long Lat Country Island Pop Geometry Region; do
    # 跳过表头
    if [[ "$ID" != "ID" ]]; then
        ISLANDS+=("$ID,$Long,$Lat,$Pop")
    fi
done < "$CSV_FILE"

TOTAL_ISLANDS=${#ISLANDS[@]}
echo "Total islands to process: $TOTAL_ISLANDS" >> "$MAIN_LOG"
echo "Maximum concurrent islands: $MAX_CONCURRENT_ISLANDS" >> "$MAIN_LOG"
echo "============================================================" >> "$MAIN_LOG"

# 批量处理岛屿
BATCH_START=0
BATCH_NUM=1

while [ $BATCH_START -lt $TOTAL_ISLANDS ]; do
    BATCH_END=$((BATCH_START + MAX_CONCURRENT_ISLANDS - 1))
    if [ $BATCH_END -ge $TOTAL_ISLANDS ]; then
        BATCH_END=$((TOTAL_ISLANDS - 1))
    fi
    
    BATCH_SIZE=$((BATCH_END - BATCH_START + 1))
    BATCH_START_TIME=$(date +'%Y-%m-%d %H:%M:%S')
    
    echo "------------------------------------------------------------" >> "$MAIN_LOG"
    echo "BATCH $BATCH_NUM: Processing islands $((BATCH_START + 1))-$((BATCH_END + 1)) (${BATCH_SIZE} islands) started at $BATCH_START_TIME" >> "$MAIN_LOG"
    
    # 用于存储当前批次的后台任务PID和岛屿信息
    declare -A BATCH_PIDS
    declare -A BATCH_RESULTS
    
    # --- 启动当前批次的所有岛屿任务 ---
    for i in $(seq $BATCH_START $BATCH_END); do
        ISLAND_INFO=${ISLANDS[$i]}
        IFS=',' read -r ID Long Lat Pop <<< "$ISLAND_INFO"
        
        # 在后台运行岛屿任务
        run_island_disaster_free "$ID" "$Lat" "$Long" "$Pop" &
        BATCH_PIDS[$ID]=$!
        
        echo "  Island $ID: started in background (PID: $!)" >> "$MAIN_LOG"
    done
    
    # --- 等待当前批次的所有任务完成 ---
    BATCH_SUCCESS_COUNT=0
    BATCH_FAIL_COUNT=0
    
    for ISLAND_ID in "${!BATCH_PIDS[@]}"; do
        PID=${BATCH_PIDS[$ISLAND_ID]}
        wait $PID
        EXIT_CODE=$?
        BATCH_RESULTS[$ISLAND_ID]=$EXIT_CODE
        
        if [ $EXIT_CODE -eq 0 ]; then
            BATCH_SUCCESS_COUNT=$((BATCH_SUCCESS_COUNT + 1))
        else
            BATCH_FAIL_COUNT=$((BATCH_FAIL_COUNT + 1))
        fi
    done
    
    # --- 批次执行完毕，生成报告 ---
    BATCH_END_TIME=$(date +'%Y-%m-%d %H:%M:%S')
    BATCH_START_TIMESTAMP=$(date -d "$BATCH_START_TIME" +%s)
    BATCH_END_TIMESTAMP=$(date -d "$BATCH_END_TIME" +%s)
    BATCH_DURATION=$((BATCH_END_TIMESTAMP - BATCH_START_TIMESTAMP))
    HOURS=$((BATCH_DURATION / 3600))
    MINUTES=$(((BATCH_DURATION % 3600) / 60))
    SECONDS=$((BATCH_DURATION % 60))
    DURATION_FORMAT=$(printf "%02d:%02d:%02d" $HOURS $MINUTES $SECONDS)
    
    echo "BATCH $BATCH_NUM COMPLETED at $BATCH_END_TIME (Duration: $DURATION_FORMAT)" >> "$MAIN_LOG"
    echo "  Success: $BATCH_SUCCESS_COUNT, Failed: $BATCH_FAIL_COUNT" >> "$MAIN_LOG"
    
    # 如果有失败的任务，列出详细信息
    if [ $BATCH_FAIL_COUNT -gt 0 ]; then
        echo "  Failed islands:" >> "$MAIN_LOG"
        for ISLAND_ID in "${!BATCH_RESULTS[@]}"; do
            if [ ${BATCH_RESULTS[$ISLAND_ID]} -ne 0 ]; then
                echo "    Island $ISLAND_ID (exit code: ${BATCH_RESULTS[$ISLAND_ID]})" >> "$MAIN_LOG"
            fi
        done
    fi
    
    echo "" >> "$MAIN_LOG"
    
    # 清理当前批次的变量，准备下一批次
    unset BATCH_PIDS
    unset BATCH_RESULTS
    
    BATCH_START=$((BATCH_END + 1))
    BATCH_NUM=$((BATCH_NUM + 1))
done

echo "============================================================" >> "$MAIN_LOG"
echo "All batches completed. All islands processed." >> "$MAIN_LOG"