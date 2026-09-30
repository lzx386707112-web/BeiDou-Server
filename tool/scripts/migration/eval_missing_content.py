#!/usr/bin/env python3
"""评估「TMS 273 有、BeiDou 目前没有」的玩法内容。

口径：
  1. 用 MapScan 全量 TMS 地图 info（/tmp/test_one.tsv），按 fieldScript / onFirstUserEnter 聚成玩法簇；
  2. 与 BeiDou 客户端地图 ID 集合比对 → 完全缺失（cov=0）/ 部分缺失 / 完整；
  3. 对候选簇进一步扫描 TMS 地图 life/npc，统计「需要新迁移的怪物 / NPC」数量。

只读，不写任何客户端/服务端文件。产物 JSON 打到 stdout 指定的路径。
"""
import os
import sys
import json
import glob
from collections import defaultdict, Counter

ROOT = '/Users/lizixian/Documents/mxd/BeiDou-Server'
sys.path.insert(0, os.path.join(ROOT, 'tool/wz-python'))
os.chdir(ROOT)

TMS = os.path.expanduser('~/Documents/mxd/TMS/MapleStory-IMG/Data')
SCAN = '/tmp/test_one.tsv'

from wzpy.wz_image import WzImage           # noqa: E402
from wzpy.crypto import WzKey               # noqa: E402

TMS_KEY = WzKey.for_region('BMS')


def load_beidou_sets():
    maps, mobs, npcs = set(), set(), set()
    for p in glob.glob('clien/Data/Map/Map/Map*/*.img'):
        maps.add(os.path.basename(p)[:-4])
    for p in glob.glob('clien/Data/Mob/*.img'):
        mobs.add(os.path.basename(p)[:-4])
    for p in glob.glob('clien/Data/Npc/*.img'):
        npcs.add(os.path.basename(p)[:-4])
    return maps, mobs, npcs


def load_scan():
    rows = []
    for line in open(SCAN):
        p = line.rstrip('\n').split('\t')
        if len(p) < 4:
            continue
        d = {}
        for kv in p[1].split(';'):
            if '=' in kv:
                k, v = kv.split('=', 1)
                d[k] = v
        rows.append((p[0], d, p[2], p[3]))
    return rows


def tms_map_path(mid):
    return os.path.join(TMS, 'Map/Map/Map%s/%s.img' % (mid[0], mid))


def scan_cluster_maps(mids):
    """扫一组 TMS 地图，返回 mob/npc/reactor 统计。"""
    mobs, npcs, reactors = set(), set(), 0
    mob_hits = Counter()
    detail = []
    for mid in mids:
        p = tms_map_path(mid)
        if not os.path.exists(p):
            continue
        try:
            img = WzImage.from_bytes(open(p, 'rb').read(), key=TMS_KEY)
        except Exception as e:
            detail.append({'map': mid, 'err': '%s: %s' % (type(e).__name__, e)})
            continue
        n_mob = n_npc = n_re = 0
        for c in img.children():
            if c.name == 'life':
                for g in c.children():
                    kind = None
                    cid = None
                    for f in g.children():
                        if f.name == 'type':
                            kind = f.value
                        elif f.name == 'id':
                            cid = f.value
                    if cid is None:
                        continue
                    if kind == 'm':
                        mobs.add(cid)
                        mob_hits[cid] += 1
                        n_mob += 1
                    elif kind == 'n':
                        npcs.add(cid)
                        n_npc += 1
            elif c.name == 'reactor':
                reactors += len(c.children())
                n_re = len(c.children())
        detail.append({'map': mid, 'mob': n_mob, 'npc': n_npc, 'reactor': n_re})
    return {'mobs': mobs, 'npcs': npcs, 'reactor_total': reactors,
            'mob_hits': mob_hits, 'detail': detail}


def main():
    bd_maps, bd_mobs, bd_npcs = load_beidou_sets()
    rows = load_scan()
    tms_names = json.load(open('/tmp/tms_mapnames.json'))

    clusters = defaultdict(list)
    for mid, d, portals, tail in rows:
        fs = d.get('fieldScript')
        fe = d.get('onFirstUserEnter')
        k = fs or ('FUE:' + fe if fe else None)
        if k:
            clusters[k].append((mid, d, portals, tail))

    out = []
    for k, items in clusters.items():
        if len(items) < 3:
            continue
        hit = [m for m, d, p, t in items if m in bd_maps]
        streets = Counter(tms_names.get(m, {}).get('streetName') for m, d, p, t in items)
        out.append({
            'key': k,
            'n': len(items),
            'hit': len(hit),
            'cov': round(len(hit) / len(items), 3),
            'street': streets.most_common(1)[0][0],
            'sample': [tms_names.get(m, {}).get('mapName') for m, d, p, t in sorted(items)[:4]],
            'maps': sorted(m for m, d, p, t in items),
        })
    out.sort(key=lambda r: (-r['n'], r['key']))

    # 候选簇：传统机制、不依赖 273 专属 UI / 083 后职业
    cand = json.load(open(os.path.join(ROOT, 'tool/scripts/migration/eval_candidates.json')))
    cand_res = {}
    for group in cand:
        keys = group['keys']
        mids = []
        for r in out:
            if r['key'] in keys:
                mids += r['maps']
        mids = sorted(set(mids))
        st = scan_cluster_maps(mids)
        new_mobs = sorted(m for m in st['mobs'] if m.lstrip('0') not in
                          {x.lstrip('0') for x in bd_mobs} and m not in bd_mobs)
        new_npcs = sorted(n for n in st['npcs'] if n.lstrip('0') not in
                          {x.lstrip('0') for x in bd_npcs} and n not in bd_npcs)
        cand_res[group['id']] = {
            'name': group['name'], 'keys': keys, 'maps': len(mids),
            'mob_kinds': len(st['mobs']), 'new_mobs': len(new_mobs),
            'npc_kinds': len(st['npcs']), 'new_npcs': len(new_npcs),
            'reactors': st['reactor_total'],
            'top_mobs': [m for m, _ in st['mob_hits'].most_common(12)],
            'new_mob_list': new_mobs[:40],
            'new_npc_list': new_npcs[:20],
            'streets': Counter(tms_names.get(m, {}).get('streetName') for m in mids).most_common(3),
        }
        print('%-24s maps=%4d mobs=%4d(new %3d) npc=%3d(new %3d)' %
              (group['id'], len(mids), len(st['mobs']), len(new_mobs), len(st['npcs']), len(new_npcs)))

    json.dump({'bd_maps': len(bd_maps), 'tms_maps': len(rows),
               'clusters': out, 'candidates': cand_res},
              open('/tmp/missing_eval.json', 'w'), ensure_ascii=False, indent=1)
    print('\nwritten /tmp/missing_eval.json')


if __name__ == '__main__':
    main()
