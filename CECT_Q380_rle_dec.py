import os
import re
import struct
import sys
from PIL import Image

HDR_RE = re.compile(rb'(BM|VM)(.{4})\x00\x00\x00\x00(.{4})\x28\x00\x00\x00', re.S)

COMP_BITFIELDS = 3
COMP_RLE = 0x1003

def decode_rle(buf, pos, w, h):
    rows = []
    n = len(buf)
    try:
        for _ in range(h):
            row = []
            while True:
                t = buf[pos]
                if t:
                    px = buf[pos + 1] | (buf[pos + 2] << 8)
                    row += [px] * t
                    pos += 3
                else:
                    c = buf[pos + 1]
                    pos += 2
                    if c == 0:
                        break
                    if pos + 2 * c > n:
                        raise ValueError('literal overrun')
                    for _ in range(c):
                        row.append(buf[pos] | (buf[pos + 1] << 8))
                        pos += 2
                if len(row) > w:
                    raise ValueError('row overflow')
            if len(row) != w:
                raise ValueError('row width %d != %d' % (len(row), w))
            rows.append(row)
    except IndexError:
        raise ValueError('unexpected end of data')
    return rows, pos

def decode_raw(buf, w, h):
    if len(buf) < w * h * 2:
        raise ValueError('raw too short')
    return [[buf[(y * w + x) * 2] | (buf[(y * w + x) * 2 + 1] << 8)
             for x in range(w)] for y in range(h)]

def overlay(prev, cur):
    return [[c if c else p for p, c in zip(pr, cr)] for pr, cr in zip(prev, cur)]

def to_image(rows, bottom_up=True):
    h, w = len(rows), len(rows[0])
    if bottom_up:
        rows = rows[::-1]
    px = []
    for r in rows:
        for v in r:
            R = (v >> 11) & 31
            G = (v >> 5) & 63
            B = v & 31
            px.append((R * 255 // 31, G * 255 // 63, B * 255 // 31))
    im = Image.new('RGB', (w, h))
    im.putdata(px)
    return im

def parse_block(d, m):
    fh = m.start()
    magic = m.group(1).decode()
    size = struct.unpack('<I', m.group(2))[0]
    offbits = struct.unpack('<I', m.group(3))[0]
    dib = fh + 14
    if dib + 40 > len(d):
        return None
    _, w, ht, planes, bpp, comp, _, _, _, _, _ = struct.unpack_from('<IiiHHIIiiII', d, dib)
    if bpp != 16 or planes != 1 or not (0 < w <= 1024) or not (0 < abs(ht) <= 1024):
        return None
    if comp not in (COMP_BITFIELDS, COMP_RLE):
        return None
    return dict(fh=fh, magic=magic, size=size, offbits=offbits,
                w=w, h=abs(ht), bottom_up=ht > 0, comp=comp)

def find_blocks(d):
    out = []
    for m in HDR_RE.finditer(d):
        b = parse_block(d, m)
        if b:
            out.append(b)
    return out

def decode_single(d, b):
    p = b['fh'] + b['offbits']
    exact = True
    if b['comp'] == COMP_BITFIELDS:
        rows = decode_raw(d[p:p + b['w'] * b['h'] * 2], b['w'], b['h'])
    else:
        rows, end = decode_rle(d, p, b['w'], b['h'])
        if end != b['fh'] + b['size']:
            print('  warn: end 0x%x != declared 0x%x' % (end, b['fh'] + b['size']))
            exact = False
    return to_image(rows, b['bottom_up']), exact

def decode_container(d, b):
    fh, w, h = b['fh'], b['w'], b['h']
    p = fh + b['offbits']
    n = struct.unpack_from('<I', d, p)[0]
    table = [struct.unpack_from('<I', d, p + 4 + 8 * i)[0] for i in range(n)]
    off = b['offbits'] + 4 + 8 * n
    chunks = [None] * n
    for i in range(n - 1, -1, -1):
        a = table[i]
        L = a & 0x7fffffff
        chunks[i] = (bool(a >> 31), d[fh + off:fh + off + L])
        off += L
    exact = True
    if off != b['size']:
        print('  warn: container size mismatch (%d != %d)' % (off, b['size']))
        exact = False

    frames, cur = [], None
    for i, (is_raw, chunk) in enumerate(chunks):
        if is_raw:
            rows = decode_raw(chunk, w, h)
            cur = rows
        else:
            rows, end = decode_rle(chunk, 0, w, h)
            if end != len(chunk):
                print('  warn: frame %d rle end mismatch' % i)
                exact = False
            cur = rows if cur is None else overlay(cur, rows)
        frames.append(to_image(cur, b['bottom_up']))
    return frames, exact

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    d = open(sys.argv[1], 'rb').read()
    out = sys.argv[2] if len(sys.argv) > 2 else '.'
    blocks = find_blocks(d)
    print('blocks:', len(blocks))
    exact_count = 0
    for i, b in enumerate(blocks):
        addr = '0x%08X' % b['fh']
        dims = '%dx%d' % (b['w'], b['h'])
        comp_name = 'RLE' if b['comp'] == COMP_RLE else 'BITFIELDS'
        tag = '%08X_%s' % (b['fh'], dims)
        try:
            if b['magic'] == 'BM':
                im, exact = decode_single(d, b)
                rel = os.path.join(out, '%s.png' % tag)
                im.save(rel)
                print('%s    %s   %s  OK  -> %s' % (addr, dims, comp_name, rel))
            else:
                fr, exact = decode_container(d, b)
                for k, im in enumerate(fr):
                    im.save(os.path.join(out, '%s_f%d.png' % (tag, k)))
                rel = os.path.join(out, '%s_f0.png' % tag)
                print('%s    %s   %s  OK  -> %s  (frames=%d)' % (addr, dims, comp_name, rel, len(fr)))
            if exact:
                exact_count += 1
        except ValueError as e:
            print('%s    %s   %s  FAILED: %s' % (addr, dims, comp_name, e))

    print('%d images found, %d decoded exactly' % (len(blocks), exact_count))

if __name__ == '__main__':
    main()