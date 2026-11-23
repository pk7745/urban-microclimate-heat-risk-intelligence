tf = 86.0
rh = 90.0

terms = [
    ('c1', -42.379),
    ('c2*T', 2.04901523 * tf),
    ('c3*R', 10.14333127 * rh),
    ('c4*T*R', -0.22475541 * tf * rh),
    ('c5*T^2', -0.00683783 * (tf**2)),
    ('c6*R^2', -0.05481717 * (rh**2)),
    ('c7*T^2*R', 0.00122874 * (tf**2) * rh),
    ('c8*T*R^2', 0.00085282 * tf * (rh**2)),
    ('c9*T^2*R^2', -0.00000199 * (tf**2) * (rh**2))
]

total = 0.0
for name, val in terms:
    total += val
    print(f"{name:<15}: {val:18.10f} | cum: {total:18.10f}")

adj = ((rh - 85.0) / 10.0) * ((87.0 - tf) / 5.0)
print(f"High-RH adj: {adj:18.10f}")
total_adj = total + adj
print(f"Total HI (F): {total_adj:18.10f}")
celsius = (total_adj - 32.0) * 5.0 / 9.0
print(f"Total HI (C): {celsius:18.10f}")
print(f"Rounded 2 decimals: {round(celsius, 2)} C")
