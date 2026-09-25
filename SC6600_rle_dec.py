import struct
import sys
import zlib

def parse_int(s):
    s = s.strip().lower()
    if s.endswith("h"):
        return int(s[:-1], 16)
    return int(s, 0) if s.startswith("0x") else (int(s, 16) if any(c in "abcdef" for c in s) else int(s, 10))

def be16(buf, o):
    return (buf[o] << 8) | buf[o + 1]

def be32(buf, o):
    return struct.unpack(">I", buf[o:o + 4])[0]

def write_png(path, width, height, rgb_rows):
    raw = b"".join(b"\x00" + bytes(row) for row in rgb_rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)

def rgb565_to_rgb(p):
    r = (p >> 11) & 31
    g = (p >> 5) & 63
    b = p & 31
    return (r * 255 // 31, g * 255 // 63, b * 255 // 31)

def decode_rle(buf, pos, end, width, height):
    rows, cur, warn = [], [], []
    while pos + 2 <= end and len(rows) < height:
        t = be16(buf, pos)
        run, lit = t >> 8, t & 0xFF
        tpos = pos
        pos += 2
        if run == 0 and lit == 0:
            if len(cur) != width:
                warn.append(f"row {len(rows)}: {len(cur)} px (expected {width}) at 0x{tpos:X}")
            rows.append(cur)
            cur = []
            continue
        if pos + 2 * lit > end:
            warn.append(f"literal overrun at 0x{tpos:X}")
            break
        for _ in range(lit):
            cur.append(be16(buf, pos))
            pos += 2
        if run:
            if pos + 2 > end:
                warn.append(f"run pixel missing at 0x{tpos:X}")
                break
            cur.extend([be16(buf, pos)] * run)
            pos += 2
    if cur and len(rows) < height:
        warn.append(f"last row not terminated ({len(cur)} px)")
        rows.append(cur)
    return rows, warn, pos

def decode_raw(buf, pos, end, width, height):
    rows, stride = [], ((width * 2 + 3) // 4) * 4
    for y in range(height):
        o = pos + y * stride
        if o + width * 2 > end:
            break
        rows.append([be16(buf, o + 2 * x) for x in range(width)])
    return rows, [], pos + stride * len(rows)

MAXDIM = 4096

def find_headers(buf):
    pos = 0
    while True:
        o = buf.find(b"MB", pos)
        if o < 0:
            return
        pos = o + 1
        if o + 66 > len(buf) or be32(buf, o + 14) != 40:
            continue
        w, h = be32(buf, o + 18), be32(buf, o + 22)
        planes, bpp, comp = be16(buf, o + 26), be16(buf, o + 28), be32(buf, o + 30)
        total, dataoff = be32(buf, o + 2), be32(buf, o + 10)
        if not (1 <= w <= MAXDIM and 1 <= h <= MAXDIM):
            continue
        if planes != 1 or bpp != 16 or comp not in (0x0003, 0x1003) or dataoff != 0x42:
            continue
        if total < dataoff or o + total > len(buf):
            continue
        yield o, w, h, comp, total

def decode_at(buf, o, w, h, comp, total):
    pos, end = o + be32(buf, o + 10), o + total
    fn = decode_rle if comp & 0x1000 else decode_raw
    rows, warn, endpos = fn(buf, pos, end, w, h)
    return rows, warn, endpos, end

def to_rgb_rows(rows, w, h, flip=True):
    out = []
    for y in range(h):
        r = rows[y] if y < len(rows) else []
        r = (r + [0] * w)[:w]
        out.append([c for p in r for c in rgb565_to_rgb(p)])
    if flip:
        out.reverse()
    return out

def auto_scan(path, outdir, flip, min_size, strict):
    import os
    buf = open(path, "rb").read()
    n = ok = 0
    for o, w, h, comp, total in find_headers(buf):
        if w < min_size or h < min_size:
            continue
        rows, warn, endpos, end = decode_at(buf, o, w, h, comp, total)
        valid = not warn and len(rows) == h and endpos == end
        n += 1
        ok += valid
        if strict and not valid:
            continue
        name = os.path.join(outdir, f"{o:08X}_{w}x{h}{'' if valid else '_BAD'}.png")
        write_png(name, w, h, to_rgb_rows(rows, w, h, flip))
        print(f"0x{o:08X}  {w:4d}x{h:<4d} {'RLE' if comp & 0x1000 else 'raw'}  "
              f"{'OK' if valid else f'{len(warn)} warning(s)'}  -> {name}")
    print(f"\n{n} bitmaps found, {ok} decoded exactly; output in {outdir}/")

def main():
    argv = sys.argv[1:]
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--") and not a.startswith("--min-size")}
    flip = "--no-flip" not in flags
    min_size = 1
    for i, a in enumerate(argv):
        if a == "--min-size" and i + 1 < len(argv):
            min_size = int(argv[i + 1])
            args = [x for x in args if x != argv[i + 1]]

    if len(args) in (1, 2):
        auto_scan(args[0], args[1] if len(args) == 2 else ".", flip, min_size, "--strict" in flags)
        return
    if len(args) not in (3, 5):
        print(__doc__)
        sys.exit(1)

    path, offset = args[0], parse_int(args[1])
    buf = open(path, "rb").read()
    if len(args) == 3:
        out = args[2]
        hdr = next((h for h in find_headers(buf[offset:offset + 66 + (1 << 24)]) if h[0] == 0), None)
        if not hdr:
            sys.exit(f"no valid header at 0x{offset:X}; give width/height manually")
        _, w, h, comp, total = hdr
        rows, warn, endpos, end = decode_at(buf, offset, w, h, comp, total)
        print(f"header @0x{offset:X}: {w}x{h}, {'RLE' if comp & 0x1000 else 'raw'}, size={total}")
        for x in warn[:20]:
            print("warning:", x)
        if not warn and len(rows) == h and endpos == end:
            print("OK: valid data")
        write_png(out, w, h, to_rgb_rows(rows, w, h, flip))
        print("wrote", out)
        return

    width, height, out = int(args[2]), int(args[3]), args[4]
    pos, end = offset, len(buf)
    rows, warn, endpos = decode_rle(buf, pos, end, width, height)
    print(f"decoded {len(rows)}/{height} rows, up to 0x{endpos:X}")
    for x in warn[:20]:
        print("warning:", x)
    write_png(out, width, height, to_rgb_rows(rows, width, height, flip))
    print("wrote", out)

if __name__ == "__main__":
    main()
