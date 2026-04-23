text = "219500012023156945"

# Heuristic slice from right to left
total_str = text[-4:]
net_str = text[-8:-4]
dep_str = text[-11:-8]
disc_str = text[-14:-11]
price_str = text[:-14]

def to_float(s):
    if len(s) >= 3:
        return float(s[:-2] + "." + s[-2:])
    elif len(s) == 2:
        return float("0." + s)
    return float(s)

print("Price:", to_float(price_str))
print("Disc:", to_float(disc_str))
print("Dep:", to_float(dep_str))
print("Net:", to_float(net_str))
print("Total:", to_float(total_str))
