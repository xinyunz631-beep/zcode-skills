#!/usr/bin/env bash
set -euo pipefail

echo "========== 硬件 =========="
CPU=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "未知")
PHYS=$(sysctl -n hw.physicalcpu 2>/dev/null || echo "?")
LOGI=$(sysctl -n hw.logicalcpu 2>/dev/null || echo "?")
MEM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
MEM_GB=$(awk -v b="$MEM_BYTES" 'BEGIN { printf "%.1f", b/1024/1024/1024 }')
echo "CPU: $CPU"
echo "核心: ${PHYS} 物理 / ${LOGI} 逻辑"
echo "内存: ${MEM_GB} GB"

echo
echo "========== 实时 CPU / 内存 =========="
top -l 1 -s 0 | head -12

echo
echo "========== 内存详情 =========="
if command -v vm_stat >/dev/null 2>&1; then
  vm_stat | perl -ne '
    /page size of (\d+)/ and $size=$1;
    /Pages free:\s+(\d+)/ and printf "空闲: %.2f GB\n", $1*$size/1024/1024/1024;
    /Pages active:\s+(\d+)/ and printf "活跃: %.2f GB\n", $1*$size/1024/1024/1024;
    /Pages inactive:\s+(\d+)/ and printf "非活跃: %.2f GB\n", $1*$size/1024/1024/1024;
    /Pages wired down:\s+(\d+)/ and printf "wired: %.2f GB\n", $1*$size/1024/1024/1024;
    /Pages occupied by compressor:\s+(\d+)/ and printf "压缩: %.2f GB\n", $1*$size/1024/1024/1024;
  '
fi

echo
echo "========== CPU TOP 10 =========="
ps -Arco pid,comm,%cpu,%mem,rss -m 2>/dev/null | head -11

echo
echo "========== 内存 TOP 10 =========="
ps -Amrco pid,comm,rss,%mem 2>/dev/null | awk 'NR==1{print; next} {printf "%s\t%s\t%.0f MB\t%s%%\n", $1, $2, $3/1024, $4}' | head -11

echo
echo "========== 磁盘 =========="
df -h / /System/Volumes/Data 2>/dev/null | awk 'NR==1 || /\/$/ || /Data/'
