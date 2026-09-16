# main entry point for the application
import platform, os
import subprocess
import cpuinfo


def l3_cache_size(info):
    # py-cpuinfo only reports L2 on Windows; fall back to WMI, which gives L3 in KB
    if "l3_cache_size" in info:
        return info["l3_cache_size"]
    if platform.system() != "Windows":
        return None
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).L3CacheSize"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    return int(out) * 1024 if out.isdigit() else None


def main():
    info = cpuinfo.get_cpu_info()
    print(info["brand_raw"])  # 'Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz'
    print(info["arch"])  # 'X86_64'
    print(info["bits"])  # 64
    print(info["hz_advertised_friendly"])  # '2.6000 GHz'
    print(info.get("l2_cache_associativity", "unknown"))
    print(l3_cache_size(info))  # bytes, or None if unavailable
    print(info["flags"])  # list of instruction set flags: 'avx2', 'sse4_2', etc.


main()
