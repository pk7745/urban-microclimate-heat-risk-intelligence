import sys
sys.path.insert(0, ".")
from app.services.sensor_simulator import assess_heat_index

t_c = (80.0 - 32.0) * 5.0 / 9.0

print(f"Testing at T_F = 80.0 F (T_C = {t_c:.6f} C)")
for rh in [40.0, 42.0, 48.0, 48.9, 48.936, 48.94, 49.0, 50.0]:
    res = assess_heat_index(t_c, rh)
    t_f = 80.0
    hi_simple = 0.5 * (t_f + 61.0 + (t_f - 68.0) * 1.2 + rh * 0.094)
    hi_avg = 0.5 * (hi_simple + t_f)
    hi_c = res["heat_index_celsius"]
    hi_f = hi_c * 9.0 / 5.0 + 32.0 if hi_c is not None else None
    print(f"RH={rh:6.3f}% | hi_simple={hi_simple:7.3f} F | hi_avg={hi_avg:7.3f} F | Project Output: {hi_c} C ({hi_f:.2f} F) | Status: {res['status']}")
