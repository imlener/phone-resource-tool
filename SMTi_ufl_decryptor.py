import sys
import collections
import numpy as np

CH = 0x10000
HDR = 0x80

def detect_regions(d, nch):
    a, b = d[0x34], d[0x38]
    if a and b and a + b == nch:
        return [a, b]
    return [nch]

def derive_key(chunks, lo, hi):
    first = max(lo, 1)
    groups = collections.defaultdict(list)
    for i in range(first, hi):
        groups[chunks[i].tobytes()].append(i)
    best = max(groups.values(), key=len)
    if len(best) >= 2:
        return chunks[best[0]] ^ 0xFF
    key = np.zeros(CH, dtype=np.uint8)
    for off in range(0, CH, 16):
        c = collections.Counter(chunks[i][off:off + 16].tobytes() for i in range(first, hi))
        k, v = c.most_common(1)[0]
        if v < 3:
            raise SystemExit("Can't derive key (regions %d-%d)" % (lo, hi))
        key[off:off + 16] = np.frombuffer(k, dtype=np.uint8) ^ 0xFF
    return key

def decrypt(d):
    nch = len(d) // CH
    regions = detect_regions(d, nch)
    arr = np.frombuffer(d[:nch * CH], dtype=np.uint8).reshape(nch, CH)
    out = np.frombuffer(d, dtype=np.uint8).copy()
    keys = []
    start = 0
    for r in regions:
        key = derive_key(arr, start, start + r)
        keys.append(key)
        for i in range(start, start + r):
            out[i * CH:(i + 1) * CH] ^= key
        start += r
    rem = len(d) - nch * CH
    if rem:
        out[nch * CH:] ^= keys[-1][:rem]
    out[:HDR] = np.frombuffer(d[:HDR], dtype=np.uint8)
    return out.tobytes()

def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    path = sys.argv[1]
    with open(path, "rb") as f:
        data = f.read()
    result = decrypt(data)
    with open(path + "_decrypted.bin", "wb") as f:
        f.write(result)

if __name__ == "__main__":
    main()