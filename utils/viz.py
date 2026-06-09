"""
可视化工具模块 - 图表渲染 + 交互地图
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
import base64
import warnings
import rasterio
from rasterio.warp import transform_bounds

warnings.filterwarnings("ignore")

# 尝试使用中文字体
try:
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
except Exception:
    pass

# 设计系统颜色
COLORS = {
    "primary": "#1a6b5a",
    "secondary": "#b8956a",
    "accent": "#e07b39",
    "background": "#f8f6f0",
    "text": "#2d2d2d",
    "light_gray": "#e8e5df",
    "blue": "#4a90b8",
    "red": "#c0392b",
    "green": "#27ae60",
}

ALGORITHM_COLORS = {
    "lightgbm": "#4a90b8",
    "xgboost": "#1a6b5a",
    "random_forest": "#e07b39",
}


def set_style():
    """设置matplotlib全局样式"""
    try:
        plt.style.use('seaborn-v0_8-whitegrid')
    except OSError:
        try:
            plt.style.use('seaborn-whitegrid')
        except OSError:
            try:
                plt.style.use('ggplot')
            except OSError:
                pass  # 使用默认样式

    plt.rcParams.update({
        'figure.facecolor': COLORS["background"],
        'axes.facecolor': COLORS["background"],
        'axes.edgecolor': COLORS["light_gray"],
        'axes.labelcolor': COLORS["text"],
        'text.color': COLORS["text"],
        'grid.color': COLORS["light_gray"],
        'grid.alpha': 0.5,
    })


def fig_to_base64(fig: plt.Figure) -> str:
    """将matplotlib图表转为base64字符串"""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor=COLORS["background"], edgecolor='none')
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def plot_metrics_comparison(metrics_df: pd.DataFrame) -> plt.Figure:
    """绘制模型指标对比图"""
    set_style()
    algorithms = metrics_df["algorithm"].tolist()
    metrics_names = ["MAE", "RMSE", "R²"]
    metric_cols = ["mae", "rmse", "r2"]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    for ax, metric_name, col in zip(axes, metrics_names, metric_cols):
        values = metrics_df[col].tolist()
        colors = [ALGORITHM_COLORS.get(algo, COLORS["primary"]) for algo in algorithms]
        bars = ax.bar(algorithms, values, color=colors, width=0.5, edgecolor='white', linewidth=0.5)

        # 数值标注
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.02,
                    f'{val:.4f}', ha='center', va='bottom', fontsize=10, fontweight='bold',
                    color=COLORS["text"])

        ax.set_title(metric_name, fontsize=13, fontweight='bold', color=COLORS["text"], pad=10)
        ax.set_ylabel(metric_name)
        ax.tick_params(axis='x', labelsize=10)
        ax.set_ylim(0, max(values) * 1.2 if max(values) > 0 else 1)

    fig.suptitle("Model Performance Comparison", fontsize=15, fontweight='bold',
                 color=COLORS["text"], y=1.02)
    plt.tight_layout()
    return fig


def plot_feature_importance(feature_names: list, importance_values: list,
                            title: str = "Feature Importance") -> plt.Figure:
    """绘制特征重要性图"""
    set_style()
    # 按重要性排序
    sorted_idx = np.argsort(importance_values)
    sorted_names = [feature_names[i] for i in sorted_idx]
    sorted_vals = [importance_values[i] for i in sorted_idx]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.barh(range(len(sorted_names)), sorted_vals, color=COLORS["primary"],
                   height=0.6, edgecolor='white', linewidth=0.5)

    for bar, val in zip(bars, sorted_vals):
        ax.text(bar.get_width() + max(sorted_vals) * 0.02, bar.get_y() + bar.get_height() / 2,
                f'{val:.4f}', va='center', fontsize=9, color=COLORS["text"])

    ax.set_yticks(range(len(sorted_names)))
    ax.set_yticklabels(sorted_names, fontsize=10)
    ax.set_xlabel("Importance", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight='bold', color=COLORS["text"], pad=12)
    ax.set_xlim(0, max(sorted_vals) * 1.25)
    plt.tight_layout()
    return fig


def plot_scatter_prediction(y_true: np.ndarray, y_pred: np.ndarray,
                             title: str = "Predicted vs Observed") -> plt.Figure:
    """绘制预测vs实测散点图"""
    set_style()
    fig, ax = plt.subplots(figsize=(7, 6))

    ax.scatter(y_true, y_pred, alpha=0.5, s=20, c=COLORS["primary"],
               edgecolors='white', linewidth=0.3)

    # 1:1 参考线
    all_vals = np.concatenate([y_true, y_pred])
    min_val, max_val = all_vals.min(), all_vals.max()
    ax.plot([min_val, max_val], [min_val, max_val], '--', color=COLORS["accent"],
            linewidth=2, alpha=0.7, label='1:1 Line')

    # R²标注
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    ax.text(0.05, 0.95, f'R² = {r2:.4f}', transform=ax.transAxes,
            fontsize=12, fontweight='bold', color=COLORS["text"],
            va='top', bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

    ax.set_xlabel("Observed", fontsize=11)
    ax.set_ylabel("Predicted", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight='bold', color=COLORS["text"], pad=12)
    ax.legend(loc='lower right')
    plt.tight_layout()
    return fig


def plot_residual_distribution(residuals: np.ndarray) -> plt.Figure:
    """绘制残差分布图"""
    set_style()
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(residuals, bins=30, color=COLORS["primary"], alpha=0.8,
            edgecolor='white', linewidth=0.5)
    ax.axvline(0, color=COLORS["accent"], linestyle='--', linewidth=2,
               label=f'Mean={np.mean(residuals):.4f}')
    ax.set_xlabel("Residual", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    ax.set_title("Residual Distribution", fontsize=13, fontweight='bold',
                 color=COLORS["text"], pad=12)
    ax.legend()
    plt.tight_layout()
    return fig


def plot_loss_curve(loss_values: list, title: str = "Training Loss") -> plt.Figure:
    """绘制损失曲线"""
    set_style()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(range(1, len(loss_values) + 1), loss_values, color=COLORS["primary"],
            linewidth=2, marker='o', markersize=3)
    ax.set_xlabel("Iteration", fontsize=11)
    ax.set_ylabel("Loss", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight='bold', color=COLORS["text"], pad=12)
    plt.tight_layout()
    return fig


def create_folium_map(raster_data: np.ndarray, transform,
                      crs: str = "EPSG:32651",
                      title: str = "Erosion Map",
                      cmap: str = "YlOrRd") -> str:
    """
    创建folium交互地图，返回HTML字符串

    关键修复：
    1. 将栅格bounds从源CRS重投影到WGS84(EPSG:4326)，Folium需要经纬度
    2. 渲染纯净PNG（无坐标轴/标题/色条），避免ImageOverlay错位
    3. 添加色条图例
    """
    import folium
    from folium.raster_layers import ImageOverlay
    import matplotlib.colors as mcolors
    from matplotlib.colorbar import ColorbarBase
    from matplotlib.colors import Normalize

    height, width = raster_data.shape

    # ---- 1. 将bounds从源CRS重投影到WGS84 ----
    src_bounds = rasterio.transform.array_bounds(height, width, transform)
    # src_bounds: (left, bottom, right, top) in source CRS

    try:
        wgs84_bounds = transform_bounds(crs, "EPSG:4326",
                                        src_bounds[0], src_bounds[1],
                                        src_bounds[2], src_bounds[3])
        # wgs84_bounds: (left, bottom, right, top) in WGS84
    except Exception:
        # 如果重投影失败，假设已经是WGS84
        wgs84_bounds = src_bounds

    west, south, east, north = wgs84_bounds
    center_lat = (south + north) / 2
    center_lon = (west + east) / 2

    # ---- 2. 渲染纯净栅格PNG（无坐标轴/标题/色条） ----
    valid_data = raster_data[~np.isnan(raster_data)]
    if len(valid_data) > 0:
        vmin = float(np.percentile(valid_data, 2))
        vmax = float(np.percentile(valid_data, 98))
    else:
        vmin, vmax = 0.0, 1.0

    # 使用tight布局，关闭所有axes装饰
    fig_render, ax_render = plt.subplots(figsize=(8, 6))
    ax_render.set_axis_off()
    fig_render.subplots_adjust(left=0, right=1, top=1, bottom=0)

    im = ax_render.imshow(raster_data, cmap=cmap, vmin=vmin, vmax=vmax,
                          aspect='auto',
                          extent=[0, width, 0, height])  # 像素坐标，后面由ImageOverlay负责地理配准

    buf = io.BytesIO()
    fig_render.savefig(buf, format='png', dpi=150, pad_inches=0,
                       facecolor='none', edgecolor='none', transparent=True)
    buf.seek(0)
    plt.close(fig_render)

    # ---- 3. 构建Folium地图 ----
    m = folium.Map(location=[center_lat, center_lon], zoom_start=7,
                   tiles='CartoDB positron')

    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    img_url = f"data:image/png;base64,{img_b64}"

    ImageOverlay(
        image=img_url,
        bounds=[[south, west], [north, east]],
        opacity=0.75,
        name=title,
        interactive=True,
    ).add_to(m)

    # ---- 4. 添加色条图例 ----
    try:
        import branca.colormap as bcm

        colormap = bcm.LinearColormap(
            colors=[mcolors.rgb2hex(c) for c in plt.cm.get_cmap(cmap)(np.linspace(0, 1, 256))],
            vmin=round(vmin, 1),
            vmax=round(vmax, 1),
            caption=f'{title} (t/ha/yr)',
        )
        colormap.add_to(m)
    except Exception:
        pass  # branca不可用时跳过色条

    folium.LayerControl().add_to(m)
    return m._repr_html_()


def raster_to_thumbnail_base64(raster_data: np.ndarray,
                                cmap: str = "YlOrRd",
                                figsize: tuple = (6, 4)) -> str:
    """将栅格渲染为缩略图base64，用于报告嵌入"""
    set_style()
    fig, ax = plt.subplots(figsize=figsize)
    valid_data = raster_data[~np.isnan(raster_data)]
    if len(valid_data) > 0:
        vmin = float(np.percentile(valid_data, 2))
        vmax = float(np.percentile(valid_data, 98))
    else:
        vmin, vmax = 0, 1

    im = ax.imshow(raster_data, cmap=cmap, vmin=vmin, vmax=vmax)
    plt.colorbar(im, ax=ax, label='Erosion (t/ha/yr)', shrink=0.8)
    ax.set_title("Erosion Prediction Map", fontsize=12, fontweight='bold')
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")
    plt.tight_layout()

    img_b64 = fig_to_base64(fig)
    plt.close(fig)
    return img_b64
