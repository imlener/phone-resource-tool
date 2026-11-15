import sys, os, collections, base64, zlib, time
import numpy as np

CH = 0x10000
PRIOR_B64 = "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"

def load_prior():
    p = np.frombuffer(zlib.decompress(base64.b64decode(PRIOR_B64)), dtype='<f4').reshape(4, 256).astype(np.float64)
    return p / p.sum(1, keepdims=True)

def fwht(a):
    n = a.shape[-1]; h = 1
    while h < n:
        v = a.reshape(a.shape[0], -1, 2, h)
        x = v[:, :, 0, :] + v[:, :, 1, :]
        y = v[:, :, 0, :] - v[:, :, 1, :]
        v[:, :, 0, :] = x; v[:, :, 1, :] = y
        h *= 2
    return a

def chunk_agree(chunks):
    n = len(chunks)
    if n < 2: return 0.0
    w = np.ascontiguousarray(chunks).view('<u8').reshape(n, CH // 16, 2)
    key = w[:, :, 0] ^ (w[:, :, 1] * np.uint64(0x9E3779B97F4A7C15))
    s = np.sort(key, axis=0)
    eq = s[1:] == s[:-1]
    flag = np.zeros(s.shape, dtype=bool); flag[1:] |= eq; flag[:-1] |= eq
    return flag.sum() / s.size

def detect_regions(d, body):
    nch = body.shape[0]
    hl = len(d) % CH
    c = collections.Counter(d[0x18:hl])
    cands = sorted((v for v, k in c.items() if k >= 2 and 0 < v < nch and v != 0xFF), reverse=True)
    for v in cands:
        if chunk_agree(body[v:]) >= 0.25:
            return [v, nch - v]
    return [nch]

def exact_key(chunks):
    groups = collections.defaultdict(list)
    for i, c in enumerate(chunks): groups[c.tobytes()].append(i)
    g = max(groups.values(), key=len)
    return chunks[g[0]] ^ 0xFF if len(g) >= 2 else None

def stat_key(R, iters=5, sweeps=2, topn=8):
    n = R.shape[0]
    code = load_prior()
    fill = np.full((4, 256), 0.1 / 254); fill[:, 0xFF] = 0.7; fill[:, 0x00] = 0.2
    prior = (0.5 * fill + 0.5 * code) if n < 16 else code
    prior /= prior.sum(1, keepdims=True)
    cols = np.arange(CH); mm = cols % 4
    cnt = np.bincount((cols[None, :] * 256 + R).ravel(), minlength=CH * 256).reshape(CH, 256).astype(np.float32)
    F = fwht(cnt.copy())
    logH = np.log(prior)
    for it in range(iters):
        Lf = fwht(logH.astype(np.float32).copy())
        S = fwht(F * Lf[mm]) / 256.0
        K = S.argmax(1).astype(np.uint8)
        dec = R ^ K
        hist = np.stack([np.bincount(dec[:, m::4].ravel(), minlength=256) + 1.0 for m in range(4)])
        hist /= hist.sum(1, keepdims=True)
        logH = np.log(0.5 * hist + 0.5 * prior)
    cand = np.argpartition(-S, topn, axis=1)[:, :topn].astype(np.int32)
    K = K.astype(np.int32); R32 = R.astype(np.int32)
    for sw in range(sweeps):
        for parity in (0, 1):
            dec = R32 ^ K
            c = np.bincount((dec[:, :-1] * 256 + dec[:, 1:]).ravel(), minlength=65536).reshape(256, 256) + 0.2
            logB = np.log(c / c.sum(1, keepdims=True)).ravel()
            cc = np.arange(parity, CH, 2); cc = cc[(cc > 0) & (cc < CH - 1)]
            Rc = R32[:, cc]; Rl = R32[:, cc - 1] ^ K[cc - 1]; Rr = R32[:, cc + 1] ^ K[cc + 1]
            best = np.full(len(cc), -1e18); bk = K[cc].copy()
            for j in range(topn):
                k = cand[cc, j]; dk = Rc ^ k
                s = logB[Rl * 256 + dk].sum(0) + logB[dk * 256 + Rr].sum(0)
                u = s > best; best[u] = s[u]; bk[u] = k[u]
            K[cc] = bk
    return K.astype(np.uint8)

def main():
    if len(sys.argv) < 2:
        sys.exit(1)
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + "_decrypted.bin"
    d = open(src, "rb").read()
    hl = len(d) % CH
    body = np.frombuffer(d, dtype=np.uint8)[hl:].reshape(-1, CH)
    regions = detect_regions(d, body)
    res = np.frombuffer(d, dtype=np.uint8).copy()
    rb = res[hl:].reshape(-1, CH)
    s = 0
    for r in regions:
        ch = body[s:s + r]
        K = exact_key(ch)
        if K is None: K = stat_key(ch)
        rb[s:s + r] ^= K
        s += r
    open(out, "wb").write(res.tobytes())

if __name__ == "__main__":
    main()