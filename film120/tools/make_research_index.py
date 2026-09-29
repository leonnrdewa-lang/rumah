#!/usr/bin/env python3
"""Index of every distinct source page cited in the verified research pool (data/research/R*.json) -> docs/RESEARCH_SOURCES.md
usage: make_research_index.py OUT.md"""
import glob, json, re, sys, collections
def walk(o, f, path):
    if isinstance(o, dict):
        u = o.get('source_url') or o.get('url')
        if isinstance(u, str) and u.startswith('http'): f[u].append((path, o.get('date') or o.get('quote', '')[:0]))
        for k, v in o.items(): walk(v, f, path)
    elif isinstance(o, list):
        for v in o: walk(v, f, path)
def main():
    found = collections.defaultdict(list); per = {}
    for p in sorted(glob.glob('data/research/R*.json')):
        d = json.load(open(p)); rid = p.split('/')[-1][:-5]; f = collections.defaultdict(list); walk({k: d[k] for k in ('milestones', 'capabilities', 'limitations') if k in d}, f, rid); per[rid] = (d.get('topic', ''), len(f))
        for u, v in f.items(): found[u] += v
    def host(u): return re.sub(r'^https?://(web\.archive\.org/web/\d+(id_)?/)?(https?://)?', '', u).split('/')[0]
    hosts = collections.Counter(host(u) for u in found)
    L = ['# Research source index', '', f'{len(found)} distinct source pages cited by the verified research pool ({sum(1 for _ in per)} researcher files). Each claim in the pool carries a verbatim quote checked against the fetched page.', '', '## Researchers', '']
    L += [f'- **{k}** - {t} - {n} distinct pages' for k, (t, n) in per.items()]
    L += ['', '## Hosts', ''] + [f'- {h}: {n}' for h, n in hosts.most_common(60)] + ['', '## Pages', '']
    L += [f'- {u} ({", ".join(sorted({p for p, _ in v}))}; {len(v)} claim(s))' for u, v in sorted(found.items())]
    open(sys.argv[1], 'w').write('\n'.join(L) + '\n'); print(len(found), 'pages', len(hosts), 'hosts')
if __name__ == '__main__': main()
