#!/usr/bin/env python3
"""Collect every sequence's audio events into one cue sheet for the mixer.
usage: dump_events.py PLAN SCRIPT VO OUT.json"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.compose import Ctx, collect_events

if __name__ == '__main__':
    plan, script, vo, out = sys.argv[1:5]; ctx = Ctx(plan, script, vo)
    ev = [dict(kind=k, t=round(float(t), 3), params=p) for k, t, p in collect_events(ctx)]
    json.dump(ev, open(out, 'w'), indent=0); print(len(ev), 'events ->', out)
