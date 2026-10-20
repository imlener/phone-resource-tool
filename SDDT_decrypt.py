import struct, sys

def pi_words(n):
    bits = 32 * n + 64
    one = 1 << bits
    def atan_inv(x):
        s = t = one // x; x2 = x * x; k = 1; sign = -1
        while t:
            t //= x2; k += 2; s += sign * (t // k); sign = -sign
        return s
    pi = 16 * atan_inv(5) - 4 * atan_inv(239)
    frac = (pi - 3 * one) >> 64
    return [(frac >> (32 * (n - 1 - i))) & 0xFFFFFFFF for i in range(n)]

_t = pi_words(18 + 1024)
P0, S0 = _t[:18], _t[18:]
M = 0xFFFFFFFF

class BF:
    def __init__(s, key):
        s.P = P0[:]; s.S = S0[:]
        j = 0
        for i in range(18):
            w = 0
            for _ in range(4):
                w = (w << 8) | key[j % len(key)]; j += 1
            s.P[i] ^= w
        l = r = 0
        for i in range(0, 18, 2):
            l, r = s.enc(l, r); s.P[i], s.P[i + 1] = l, r
        for i in range(0, 1024, 2):
            l, r = s.enc(l, r); s.S[i], s.S[i + 1] = l, r
    def F(s, x):
        S = s.S
        return ((((S[x >> 24] + S[256 + ((x >> 16) & 255)]) & M) ^ S[512 + ((x >> 8) & 255)]) + S[768 + (x & 255)]) & M
    def enc(s, l, r):
        P = s.P
        for i in range(16):
            l ^= P[i]; r ^= s.F(l); l, r = r, l
        l, r = r, l
        return l ^ P[17], r ^ P[16]
    def dec(s, l, r):
        P = s.P
        for i in range(17, 1, -1):
            l ^= P[i]; r ^= s.F(l); l, r = r, l
        l, r = r, l
        return l ^ P[0], r ^ P[1]
    def decrypt(s, buf):
        out = bytearray()
        for i in range(0, len(buf) - 7, 8):
            l, r = struct.unpack('<2I', buf[i:i + 8])
            out += struct.pack('<2I', *s.dec(l, r))
        return bytes(out)

def decrypt_dump(f):
    if f[:4] != b'SDDT':
        print("Warn: This file's header is not SDDT", file=sys.stderr)
    blk = f[:0x4000]
    hdr = blk[:16] + BF(blk[:16]).decrypt(blk[16:])
    total = struct.unpack('<I', hdr[0x114:0x118])[0]
    k8, k12 = hdr[0x118:0x120], hdr[0x120:0x12c]
    out = bytearray()
    for j in range(total // 0x4000):
        off = j * 0x4000
        key = k12 + k8 + struct.pack('<I', off)
        out += BF(key).decrypt(f[0x4000 + off:0x8000 + off])
    return bytes(out)

if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src.rsplit('.', 1)[0] + '_decrypted.bin'
    data = decrypt_dump(open(src, 'rb').read())
    open(dst, 'wb').write(data)
    print(f'{src} -> {dst} ({len(data)} bytes)')
