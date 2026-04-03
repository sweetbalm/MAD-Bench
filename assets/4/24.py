import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import matplotlib.dates as mdates


plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

years = np.arange(1980, 2024)

temp_anomaly = np.array([
    0.28, 0.31, 0.12, 0.28, 0.16, 0.10, 0.17, 0.31, 0.37, 0.25,  # 1980-1989
    0.42, 0.38, 0.21, 0.27, 0.30, 0.43, 0.33, 0.44, 0.57, 0.41,  # 1990-1999
    0.38, 0.51, 0.60, 0.58, 0.54, 0.64, 0.60, 0.62, 0.54, 0.63,  # 2000-2009
    0.68, 0.57, 0.62, 0.65, 0.74, 0.86, 0.99, 0.92, 0.98, 1.02,  # 2010-2019
    1.05, 1.03, 1.15, 1.18                                       # 2020-2023
])

z = np.polyfit(years, temp_anomaly, 1)
p = np.poly1d(z)
trend_line = p(years)

fig, ax = plt.subplots(figsize=(14, 8))

ax.plot(years, temp_anomaly, marker='o', linestyle='-', linewidth=2,
        markersize=6, color='#E64B2E', label='Temperature Anomaly',
        markerfacecolor='white', markeredgewidth=1.5)

ax.plot(years, trend_line, linestyle='--', linewidth=2,
        color='#2C6E9E', label=f'Trend Line (Slope: {z[0]:.3f}°C/year)')

ax.fill_between(years, temp_anomaly, 0, alpha=0.3, color='#E64B2E')

ax.set_title('Global Average Temperature Anomaly Trend (1980-2023)',
             fontsize=18, fontweight='bold', pad=20)
ax.set_xlabel('Year', fontsize=14, fontweight='bold')
ax.set_ylabel('Temperature Anomaly (Relative to 1951-1980 Baseline) [°C]',
              fontsize=14, fontweight='bold')

ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)

ax.set_xticks(np.arange(1980, 2025, 5))
ax.set_xticklabels(np.arange(1980, 2025, 5), rotation=45)

ax.axhline(y=0, color='black', linestyle='-', linewidth=1, alpha=0.5)

key_years = [1998, 2016, 2023]
for year in key_years:
    idx = np.where(years == year)[0][0]
    ax.annotate(f'{year}: {temp_anomaly[idx]:.2f}°C',
                xy=(year, temp_anomaly[idx]),
                xytext=(year + 1, temp_anomaly[idx] + 0.1),
                arrowprops=dict(arrowstyle='->', color='gray', lw=1),
                fontsize=10,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))

ax.legend(loc='upper left', fontsize=12, framealpha=0.9)

ax.set_ylim(-0.2, 1.4)

stats_text = f'Highest Anomaly: {temp_anomaly.max():.2f}°C (2023)\n'
stats_text += f'Lowest Anomaly: {temp_anomaly.min():.2f}°C (1982)\n'
stats_text += f'Average Warming Rate: {z[0]:.3f}°C/year\n'
stats_text += f'Total Warming: {temp_anomaly[-1] - temp_anomaly[0]:.2f}°C'

ax.text(0.98, 0.02, stats_text, transform=ax.transAxes, fontsize=10,
        verticalalignment='bottom', horizontalalignment='right',
        bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

plt.tight_layout()

plt.savefig('global_temperature_trend.png', dpi=300, bbox_inches='tight')