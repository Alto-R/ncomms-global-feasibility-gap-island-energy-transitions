#!/bin/bash

# --- 全局配置 ---
CSV_FILE="islands_tobe_calculated.csv"
MAIN_LOG="logs/main_log.log"

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

# --- 定义一个函数来运行单个任务，包含重试逻辑 ---
# 这个函数将被作为后台进程来执行
# 参数: 1:TASK_NAME, 2:SCRIPT_NAME, 3:LOG_FILE, 4:Lat, 5:Long, 6:Pop, 7:ID
run_single_task_with_retry() {
    local TASK_NAME=$1
    local SCRIPT_NAME=$2
    local LOG_FILE=$3
    local Lat=$4
    local Long=$5
    local Pop=$6
    local ID=$7

    echo "$TASK_NAME started for ID: $ID at $(date +'%Y-%m-%d %H:%M:%S')" >> "$MAIN_LOG"
    
    # 运行并重试逻辑，如果两次都失败，函数将以退出码 1 结束
    if ! python3 "$SCRIPT_NAME" --island_lat "$Lat" --island_lon "$Long" --pop "$Pop" >> "$LOG_FILE" 2>&1; then
        sleep 10
        if ! python3 "$SCRIPT_NAME" --island_lat "$Lat" --island_lon "$Long" --pop "$Pop" >> "$LOG_FILE" 2>&1; then
            echo "$TASK_NAME FAILED for ID: $ID at $(date +'%Y-%m-%d %H:%M:%S')" >> "$MAIN_LOG"
            exit 1 # 关键：后台任务通过退出码报告失败
        fi
    fi

    echo "$TASK_NAME completed for ID: $ID at $(date +'%Y-%m-%d %H:%M:%S')" >> "$MAIN_LOG"
    exit 0 # 关键：后台任务通过退出码报告成功
}


# --- 主循环：从CSV读取岛屿信息并处理 ---
# tail跳过表头，while循环逐行读取
tail -n +2 "$CSV_FILE" | while IFS=',' read -r ID Long Lat Country Island Pop Geometry Region; do
    
    ISLAND_START_TIME=$(date +'%Y-%m-%d %H:%M:%S')
    echo "------------------------------------------------------------" >> "$MAIN_LOG"
    echo "Island $ID: PROCESSING STARTED at $ISLAND_START_TIME" >> "$MAIN_LOG"

    # --- 使用关联数组定义所有任务 ---
    declare -A TASKS
    TASKS["disaster_2020"]="disaster_2020.py"
    TASKS["disaster_2050"]="disaster_2050.py"
    TASKS["disaster_future_2030"]="disaster_future_2030.py"
    TASKS["disaster_future_2040"]="disaster_future_2040.py"
    TASKS["disaster_future_2050"]="disaster_future_2050.py"

    # 用于存储后台任务的进程ID (PID) 和退出码
    declare -A PIDS
    declare -A EXIT_CODES
    LOG_PREFIX="logs/log_${ID}"

    # --- 并行启动所有任务 ---
    for TASK_NAME in "${!TASKS[@]}"; do
        SCRIPT_NAME=${TASKS[$TASK_NAME]}
        LOG_FILE="${LOG_PREFIX}_${TASK_NAME}.log"
        
        # 在后台运行任务 (&)，并将函数调用所需的所有参数传递给它
        run_single_task_with_retry "$TASK_NAME" "$SCRIPT_NAME" "$LOG_FILE" "$Lat" "$Long" "$Pop" "$ID" &
        
        # 存储该后台任务的PID
        PIDS[$TASK_NAME]=$!
    done

    # --- 等待所有后台任务完成并收集结果 ---
    ALL_TASKS_SUCCESS=true
    for TASK_NAME in "${!PIDS[@]}"; do
        PID=${PIDS[$TASK_NAME]}
        # 等待指定的PID完成
        wait $PID
        # 获取该进程的退出码
        EXIT_CODE=$?
        EXIT_CODES[$TASK_NAME]=$EXIT_CODE

        if [ $EXIT_CODE -ne 0 ]; then
            ALL_TASKS_SUCCESS=false
        fi

        # 任务完成后，立即检查其日志文件
        LOG_FILE="${LOG_PREFIX}_${TASK_NAME}.log"
        check_mip_gap "$LOG_FILE" "$TASK_NAME" "$ID"
    done
    
    # --- 任务执行完毕，开始统计和报告 ---
    ISLAND_END_TIME=$(date +'%Y-%m-%d %H:%M:%S')
    ISLAND_START_TIMESTAMP=$(date -d "$ISLAND_START_TIME" +%s)
    ISLAND_END_TIMESTAMP=$(date -d "$ISLAND_END_TIME" +%s)
    ISLAND_DURATION=$((ISLAND_END_TIMESTAMP - ISLAND_START_TIMESTAMP))
    HOURS=$((ISLAND_DURATION / 3600))
    MINUTES=$(((ISLAND_DURATION % 3600) / 60))
    SECONDS=$((ISLAND_DURATION % 60))
    DURATION_FORMAT=$(printf "%02d:%02d:%02d" $HOURS $MINUTES $SECONDS)

    # --- 生成最终的报告信息 ---
    if [ "$ALL_TASKS_SUCCESS" = true ]; then
        echo "Island $ID: ALL TASKS COMPLETED SUCCESSFULLY at $ISLAND_END_TIME (Total Duration: $DURATION_FORMAT)" >> "$MAIN_LOG"
    else
        # 构建一个详细的失败报告
        FAIL_REPORT="Island $ID: ONE OR MORE TASKS FAILED at $ISLAND_END_TIME (Total Duration: $DURATION_FORMAT). Status: ("
        for TASK_NAME in "${!EXIT_CODES[@]}"; do
            FAIL_REPORT+=" $TASK_NAME:${EXIT_CODES[$TASK_NAME]} "
        done
        FAIL_REPORT+=")"
        echo "$FAIL_REPORT" >> "$MAIN_LOG"
    fi
    echo "" >> "$MAIN_LOG"

done

echo "------------------------------------------------------------" >> "$MAIN_LOG"
echo "All islands processed." >> "$MAIN_LOG"