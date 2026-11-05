#!/usr/bin/env sh
# MANUTÊ — identificação do aparelho e amostragem térmica/bateria.
#
# Modos de execução:
#   No PC com o celular conectado por USB (recomendado: dumpsys exige adb):
#       ADB=1 ./device_info.sh info   > results/device.txt
#       ADB=1 ./device_info.sh sample 5 >> results/sensors.csv   # a cada 5 s
#   Dentro do Termux (sem adb): só o modo "info" funciona parcialmente.
#
# Somente leitura: não altera nenhuma configuração do aparelho.
set -eu

run() {
  if [ "${ADB:-0}" = "1" ]; then adb shell "$@"; else sh -c "$*"; fi
}

prop() { printf '%s=%s\n' "$1" "$(run getprop "$1" 2>/dev/null | tr -d '\r')"; }

info() {
  # ro.board.platform: "taro" => Snapdragon 8 Gen 1; "s5e9925" => Exynos 2200.
  # (Confirme com ro.soc.model / ro.hardware se os valores divergirem.)
  for key in ro.product.model ro.product.device ro.board.platform ro.soc.manufacturer \
             ro.soc.model ro.hardware ro.build.version.release ro.build.version.sdk \
             ro.build.display.id ro.product.cpu.abi; do
    prop "$key"
  done
  printf 'cpu_cores=%s\n' "$(run 'grep -c ^processor /proc/cpuinfo' | tr -d '\r')"
  run 'grep -E "^(MemTotal|MemAvailable|SwapTotal)" /proc/meminfo' | tr -d '\r' \
    | awk '{printf "%s=%s %s\n", $1, $2, $3}' | tr -d ':'
  printf 'storage_data=%s\n' "$(run 'df -h /data 2>/dev/null | tail -1' | tr -d '\r')"
  printf 'vulkan=%s\n' "$(run 'getprop ro.hardware.vulkan' | tr -d '\r')"
  printf 'opencl_lib=%s\n' "$(run 'ls /vendor/lib64/libOpenCL.so 2>/dev/null || echo ausente' | tr -d '\r')"
}

sample() {
  interval="${1:-5}"
  echo "epoch_s,battery_level_pct,battery_temp_dC,charge_counter_uAh,max_thermal_mC"
  while true; do
    battery="$(run dumpsys battery | tr -d '\r')"
    level="$(printf '%s\n' "$battery" | awk -F': ' '/^  level:/{print $2}')"
    temp="$(printf '%s\n' "$battery" | awk -F': ' '/^  temperature:/{print $2}')"
    counter="$(printf '%s\n' "$battery" | awk -F': ' '/Charge counter:/{print $2}')"
    thermal="$(run 'cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null' \
      | tr -d '\r' | sort -n | tail -1)"
    printf '%s,%s,%s,%s,%s\n' "$(date +%s)" "$level" "$temp" "${counter:-}" "${thermal:-}"
    sleep "$interval"
  done
}

case "${1:-info}" in
  info) info ;;
  sample) sample "${2:-5}" ;;
  *) echo "uso: $0 [info|sample [intervalo_s]]" >&2; exit 2 ;;
esac
