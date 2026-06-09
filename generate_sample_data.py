"""
生成示例GeoTIFF数据 - 模拟东北黑土区水蚀因子

输出文件:
  标签: label_2018.tif, label_2019.tif, label_2020.tif
  动态因子: R_2018.tif, R_2019.tif, R_2020.tif, C_2018.tif, C_2019.tif, C_2020.tif
  静态因子: K.tif, LS.tif, P.tif
  未来情景: R_2050_ssp245.tif, C_2050_ssp245.tif

模拟区域: 黑龙江省中南部 (125°E~129°E, 44°N~47°N), 约300km×330km
"""
import os
import sys
import numpy as np
from scipy.ndimage import gaussian_filter

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.raster_io import create_sample_tif

# 模拟区域参数
GRID_SIZE = 40  # 40x40 grid
LON_MIN, LON_MAX = 125.0, 129.0  # 经度范围
LAT_MIN, LAT_MAX = 44.0, 47.0    # 纬度范围
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "uploads")


def generate_base_topography():
    """生成基础地形模式（DEM-like）"""
    x = np.linspace(0, 1, GRID_SIZE)
    y = np.linspace(0, 1, GRID_SIZE)
    xx, yy = np.meshgrid(x, y)

    # 东南高西北低的基本趋势
    base = 200 + 500 * (1 - yy) + 300 * xx

    # 加入山丘起伏
    hill1 = 300 * np.exp(-((xx - 0.3) ** 2 + (yy - 0.4) ** 2) / 0.02)
    hill2 = 200 * np.exp(-((xx - 0.7) ** 2 + (yy - 0.6) ** 2) / 0.03)
    hill3 = 250 * np.exp(-((xx - 0.5) ** 2 + (yy - 0.3) ** 2) / 0.025)

    # Perlin-like noise via Gaussian smoothing
    noise = np.random.randn(GRID_SIZE, GRID_SIZE) * 30
    noise = gaussian_filter(noise, sigma=1.5)

    dem = base + hill1 + hill2 + hill3 + noise
    return dem.clip(50, 1200)


def generate_rainfall(year_seed: int):
    """生成降雨侵蚀力R因子（MJ·mm/(ha·h·yr)），空间相关随机场"""
    np.random.seed(year_seed)

    x = np.linspace(0, 1, GRID_SIZE)
    y = np.linspace(0, 1, GRID_SIZE)
    xx, yy = np.meshgrid(x, y)

    # 东南高西北低的趋势（模拟季风影响）
    base = 1500 + 2500 * (1 - yy) + 1500 * xx

    noise = np.random.randn(GRID_SIZE, GRID_SIZE) * 300
    noise = gaussian_filter(noise, sigma=2.0)

    # 年度随机偏移
    year_anomaly = (year_seed - 2018) * np.random.uniform(-50, 50, (GRID_SIZE, GRID_SIZE))
    year_anomaly = gaussian_filter(year_anomaly, sigma=3.0)

    return (base + noise + year_anomaly).clip(500, 8000)


def generate_soil_erodibility():
    """生成土壤可蚀性K因子（t·ha·h/(ha·MJ·mm)），空间相关"""
    np.random.seed(42)

    x = np.linspace(0, 1, GRID_SIZE)
    y = np.linspace(0, 1, GRID_SIZE)
    xx, yy = np.meshgrid(x, y)

    # 黑土区K值一般在0.02~0.06之间
    base = 0.03 + 0.02 * (1 - xx) + 0.015 * yy

    noise = np.random.randn(GRID_SIZE, GRID_SIZE) * 0.005
    noise = gaussian_filter(noise, sigma=1.5)

    return (base + noise).clip(0.01, 0.08)


def generate_slope_length():
    """生成坡长坡度LS因子"""
    np.random.seed(43)
    dem = generate_base_topography()

    # 从DEM推算坡度
    dy, dx = np.gradient(dem, 1.0)
    slope_deg = np.degrees(np.arctan(np.sqrt(dx ** 2 + dy ** 2)))

    # RUSLE LS因子近似
    beta = np.where(slope_deg < 5, 0.5, 0.7)
    m = np.where(slope_deg < 5, 0.2, np.where(slope_deg < 10, 0.4, 0.5))
    L_factor = (22.13 ** m) / (22.13 ** m) * (1 + np.random.randn(GRID_SIZE, GRID_SIZE) * 0.1)
    S_factor = np.where(slope_deg < 9, 10.8 * np.sin(np.radians(slope_deg)) + 0.03,
                         16.8 * np.sin(np.radians(slope_deg)) - 0.5)
    slope_rad = np.radians(slope_deg)
    S_factor = np.where(slope_deg < 9,
                         10.8 * np.sin(slope_rad) + 0.03,
                         16.8 * np.sin(slope_rad) - 0.5)

    ls = L_factor * S_factor
    return ls.clip(0.01, 20)


def generate_cover_management(year_seed: int):
    """生成覆盖管理C因子，受年份影响"""
    np.random.seed(year_seed + 100)

    x = np.linspace(0, 1, GRID_SIZE)
    y = np.linspace(0, 1, GRID_SIZE)
    xx, yy = np.meshgrid(x, y)

    # C值范围0.01（密林）到0.8（裸地）
    # 西北部较高（耕作区），东南部较低（林区）
    base = 0.2 + 0.3 * (1 - yy) - 0.15 * xx

    noise = np.random.randn(GRID_SIZE, GRID_SIZE) * 0.08
    noise = gaussian_filter(noise, sigma=1.5)

    # 逐年改善（退耕还林效果）
    improvement = (year_seed - 2018) * 0.03

    return (base + noise - improvement).clip(0.01, 0.8)


def generate_conservation_practice():
    """生成水土保持措施P因子"""
    np.random.seed(45)

    x = np.linspace(0, 1, GRID_SIZE)
    y = np.linspace(0, 1, GRID_SIZE)
    xx, yy = np.meshgrid(x, y)

    # P值范围0.5~1.0
    base = 0.7 + 0.25 * (1 - xx) * yy

    noise = np.random.randn(GRID_SIZE, GRID_SIZE) * 0.05
    noise = gaussian_filter(noise, sigma=2.0)

    return (base + noise).clip(0.4, 1.0)


def generate_label(dem, r_factor, k_factor, ls_factor, c_factor, p_factor, year_seed: int):
    """根据RUSLE公式生成侵蚀量标签 A = R * K * LS * C * P + noise"""
    np.random.seed(year_seed + 200)

    # RUSLE理论值
    aerial = r_factor * k_factor * ls_factor * c_factor * p_factor

    # 添加观测噪声和随机扰动
    noise = np.random.randn(GRID_SIZE, GRID_SIZE) * aerial * 0.15
    noise = gaussian_filter(noise, sigma=1.0)

    label = aerial + noise

    # 添加极端事件（个别点侵蚀异常高）
    extreme_mask = np.random.rand(GRID_SIZE, GRID_SIZE) < 0.03
    label[extreme_mask] *= np.random.uniform(1.5, 3.0, extreme_mask.sum())

    return label.clip(0, 500)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    bounds = (LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)

    print("=" * 60)
    print("  生成示例GeoTIFF数据 - 东北黑土区水蚀因子模拟")
    print("=" * 60)
    print(f"  输出目录: {OUTPUT_DIR}")
    print(f"  网格大小: {GRID_SIZE}×{GRID_SIZE}")
    print(f"  空间范围: {bounds}")

    # 1. 生成静态因子
    print("\n[1/4] 生成静态因子...")
    dem = generate_base_topography()
    k_factor = generate_soil_erodibility()
    ls_factor = generate_slope_length()
    p_factor = generate_conservation_practice()

    create_sample_tif(os.path.join(OUTPUT_DIR, "K.tif"), k_factor, bounds)
    print("  -> K.tif (土壤可蚀性)")

    create_sample_tif(os.path.join(OUTPUT_DIR, "LS.tif"), ls_factor, bounds)
    print("  -> LS.tif (坡长坡度)")

    create_sample_tif(os.path.join(OUTPUT_DIR, "P.tif"), p_factor, bounds)
    print("  -> P.tif (水土保持措施)")

    create_sample_tif(os.path.join(OUTPUT_DIR, "DEM.tif"), dem, bounds)
    print("  -> DEM.tif (数字高程)")

    # 2. 生成动态因子 (2018-2020)
    print("\n[2/4] 生成历史动态因子 (2018-2020)...")
    years = [2018, 2019, 2020]
    for year in years:
        r = generate_rainfall(year)
        c = generate_cover_management(year)
        label = generate_label(dem, r, k_factor, ls_factor, c, p_factor, year)

        create_sample_tif(os.path.join(OUTPUT_DIR, f"R_{year}.tif"), r, bounds)
        create_sample_tif(os.path.join(OUTPUT_DIR, f"C_{year}.tif"), c, bounds)
        create_sample_tif(os.path.join(OUTPUT_DIR, f"label_{year}.tif"), label, bounds)

        print(f"  -> R_{year}.tif, C_{year}.tif, label_{year}.tif")

    # 3. 生成未来情景 (2050 SSP245)
    print("\n[3/4] 生成未来情景 (2050 SSP245)...")
    np.random.seed(2050)
    r_2050 = generate_rainfall(2050) * 1.15  # SSP245情景降雨增加15%
    r_2050 = gaussian_filter(r_2050, sigma=1.0)

    np.random.seed(2050 + 100)
    c_2050 = generate_cover_management(2050) * 0.85  # 植被覆盖改善
    c_2050 = gaussian_filter(c_2050, sigma=1.0)

    create_sample_tif(os.path.join(OUTPUT_DIR, "R_2050_ssp245.tif"), r_2050, bounds)
    create_sample_tif(os.path.join(OUTPUT_DIR, "C_2050_ssp245.tif"), c_2050, bounds)

    print("  -> R_2050_ssp245.tif, C_2050_ssp245.tif")

    # 4. 验证
    print(f"\n[4/4] 验证生成结果...")
    files = sorted(os.listdir(OUTPUT_DIR))
    for f in files:
        path = os.path.join(OUTPUT_DIR, f)
        size_kb = os.path.getsize(path) / 1024
        print(f"  [OK] {f} ({size_kb:.1f} KB)")

    print(f"\n[OK] 共生成 {len(files)} 个GeoTIFF文件")
    print("=" * 60)


if __name__ == "__main__":
    main()
