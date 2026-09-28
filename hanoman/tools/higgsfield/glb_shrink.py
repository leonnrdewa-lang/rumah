"""Shrink a GLB for the web: re-encode embedded images as JPEG (max side N px),
rename animations (old=new pairs, FIRST=name renames the first clip), rebuild the
binary chunk. Stdlib + Pillow.   python3 glb_shrink.py in.glb out.glb 1024 [old=new ...]"""
import io, json, struct, sys
from PIL import Image


def read(p):
    b = open(p, 'rb').read()
    magic, ver, length = struct.unpack_from('<III', b, 0)
    off = 12; js = None; binc = b''
    while off < length:
        clen, ctype = struct.unpack_from('<II', b, off); off += 8
        chunk = b[off:off + clen]; off += clen
        if ctype == 0x4E4F534A: js = json.loads(chunk)
        elif ctype == 0x004E4942: binc = chunk
    return js, binc


def write(p, js, views):
    blob = bytearray(); newviews = []
    for data, v in views:
        while len(blob) % 4: blob.append(0)
        v = dict(v); v['byteOffset'] = len(blob); v['byteLength'] = len(data); v['buffer'] = 0
        blob += data; newviews.append(v)
    while len(blob) % 4: blob.append(0)
    js['bufferViews'] = newviews
    js['buffers'] = [{'byteLength': len(blob)}]
    j = json.dumps(js, separators=(',', ':')).encode()
    while len(j) % 4: j += b' '
    out = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(j) + 8 + len(blob))
    out += struct.pack('<II', len(j), 0x4E4F534A) + j + struct.pack('<II', len(blob), 0x004E4942) + bytes(blob)
    open(p, 'wb').write(out)


def main():
    src, dst, maxside = sys.argv[1], sys.argv[2], int(sys.argv[3])
    renames = dict(a.split('=', 1) for a in sys.argv[4:])
    js, binc = read(src)
    views = []
    for v in js['bufferViews']:
        o = v.get('byteOffset', 0); views.append([binc[o:o + v['byteLength']], v])
    for img in js.get('images', []):
        if 'bufferView' not in img: continue
        im = Image.open(io.BytesIO(views[img['bufferView']][0])).convert('RGB')
        if max(im.size) > maxside: im.thumbnail((maxside, maxside), Image.LANCZOS)
        bio = io.BytesIO(); im.save(bio, 'JPEG', quality=88, optimize=True)
        views[img['bufferView']][0] = bio.getvalue(); img['mimeType'] = 'image/jpeg'
    for a in js.get('animations', []):
        if a.get('name') in renames: a['name'] = renames[a['name']]
    if 'FIRST' in renames and js.get('animations'): js['animations'][0]['name'] = renames['FIRST']
    write(dst, js, views)
    print('wrote', dst)


main()
