"""
栅格读写、重投影、重采样工具模块
"""
import os
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, calculate_default_transform
from rasterio.transform import from_bounds
from rasterio.crs import CRS
from shapely.geometry import box
import warnings

warnings.filterwarnings("ignore", category=rasterio.errors.NotGeoreferencedWarning)

# 默认目标CRS: WGS84 / UTM zone 51N (东北黑土区)
DEFAULT_CRS = "EPSG:32651"
# 默认目标分辨率: 5km
DEFAULT_RESOLUTION_M = 5000


def read_raster(filepath: str) -> dict:
    """读取单个栅格文件，返回数据数组与元信息"""
    with rasterio.open(filepath) as src:
        data = src.read(1).astype(np.float32)
        # 处理nodata
        nodata = src.nodata
        if nodata is not None:
            data = np.where(data == nodata, np.nan, data)
        return {
            "data": data,
            "transform": src.transform,
            "crs": src.crs.to_string() if src.crs else None,
            "bounds": src.bounds,
            "shape": src.shape,
            "resolution": (src.res[0], src.res[1]),
            "nodata": nodata,
        }


def reproject_raster(src_data: np.ndarray, src_transform, src_crs: str,
                      dst_crs: str = DEFAULT_CRS,
                      dst_resolution: float = DEFAULT_RESOLUTION_M) -> dict:
    """将栅格重投影到目标CRS并重采样到目标分辨率"""
    src_crs_obj = CRS.from_string(src_crs) if src_crs else CRS.from_epsg(4326)
    dst_crs_obj = CRS.from_string(dst_crs)

    # 计算目标transform和shape
    src_height, src_width = src_data.shape
    src_bounds = rasterio.transform.array_bounds(src_height, src_width, src_transform)

    dst_transform, dst_width, dst_height = calculate_default_transform(
        src_crs_obj, dst_crs_obj,
        src_width, src_height,
        left=src_bounds[0], bottom=src_bounds[1],
        right=src_bounds[2], top=src_bounds[3],
        dst_width=None, dst_height=None,
        resolution=dst_resolution
    )

    dst_data = np.empty((dst_height, dst_width), dtype=np.float32)
    dst_data[:] = np.nan

    # 处理nan
    nodata_value = -9999.0
    src_fill = np.where(np.isnan(src_data), nodata_value, src_data)

    reproject(
        source=src_fill,
        destination=dst_data,
        src_transform=src_transform,
        src_crs=src_crs_obj,
        dst_transform=dst_transform,
        dst_crs=dst_crs_obj,
        resampling=Resampling.average,
        src_nodata=nodata_value,
        dst_nodata=nodata_value,
    )
    zero_mask = dst_data == 0

    dst_data[dst_data == 0] = np.nan  # 无效区域标记为nan

    dst_data[zero_mask] = 0.0
    dst_data[dst_data == nodata_value] = np.nan

    return {
        "data": dst_data,
        "transform": dst_transform,
        "crs": dst_crs,
        "shape": (dst_height, dst_width),
        "resolution": dst_resolution,
    }


def align_rasters(raster_list: list, target_crs: str = DEFAULT_CRS,
                  target_resolution: float = DEFAULT_RESOLUTION_M) -> list:
    """将多个栅格对齐到统一网格"""
    aligned = []
    for meta in raster_list:
        reprojected = reproject_raster(
            meta["data"], meta["transform"], meta["crs"],
            dst_crs=target_crs, dst_resolution=target_resolution
        )
        reprojected["name"] = meta.get("name", "unnamed")
        reprojected["variable"] = meta.get("variable", "unknown")
        reprojected["year"] = meta.get("year")
        reprojected["scenario"] = meta.get("scenario")
        aligned.append(reprojected)
    return aligned


def raster_to_points(raster_data: np.ndarray, transform) -> tuple:
    """将栅格数据展开为点集 (grid_id, x, y, value)"""
    height, width = raster_data.shape
    xs, ys = [], []
    values = []

    for row in range(height):
        for col in range(width):
            val = raster_data[row, col]
            if np.isnan(val):
                continue
            x, y = rasterio.transform.xy(transform, row, col)
            grid_id = row * width + col
            xs.append(x)
            ys.append(y)
            values.append(val)
            # grid_ids as index is implicit

    return np.array(xs), np.array(ys), np.array(values)


def build_feature_matrix(aligned_rasters: list) -> tuple:
    """从对齐后的栅格列表构建特征矩阵DataFrame"""
    import pandas as pd

    if not aligned_rasters:
        return None, None

    # 使用第一个栅格确定网格
    ref = aligned_rasters[0]
    height, width = ref["shape"]
    transform = ref["transform"]

    records = []
    for row in range(height):
        for col in range(width):
            x, y = rasterio.transform.xy(transform, row, col)
            grid_id = row * width + col

            record = {"grid_id": grid_id, "x": x, "y": y, "row": row, "col": col}
            all_nan = True
            for rast in aligned_rasters:
                val = rast["data"][row, col]
                if np.isnan(val):
                    continue
                all_nan = False
                var = rast["variable"]
                year = rast.get("year")
                scenario = rast.get("scenario")
                col_name = var
                if year is not None:
                    col_name = f"{var}_{year}"
                if scenario:
                    col_name = f"{col_name}_{scenario}"
                record[col_name] = float(val)

            if not all_nan:
                records.append(record)

    df = pd.DataFrame(records)
    return df, transform


def create_sample_tif(filepath: str, data: np.ndarray, bounds: tuple,
                      crs: str = "EPSG:4326", nodata: float = -9999.0):
    """创建GeoTIFF文件"""
    left, bottom, right, top = bounds
    height, width = data.shape
    transform = from_bounds(left, bottom, right, top, width, height)

    with rasterio.open(
        filepath, 'w',
        driver='GTiff',
        height=height, width=width,
        count=1, dtype=rasterio.float32,
        crs=crs, transform=transform,
        nodata=nodata
    ) as dst:
        dst.write(data.astype(np.float32), 1)
