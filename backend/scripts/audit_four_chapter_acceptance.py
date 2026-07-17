#!/usr/bin/env python3
"""Read-only audit of real Task 8 browser lineage in the isolated SQLite DB."""
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path

def audit(database: Path, manifest: Path) -> dict:
    if database.resolve() != Path('/tmp/ai-video-platform-four-chapter.db').resolve():
        raise ValueError('audit database must be the fixed isolated Task 8 database')
    payload = json.loads(manifest.read_text())
    db = sqlite3.connect(f'file:{database}?mode=ro', uri=True); db.row_factory = sqlite3.Row
    audited = []
    try:
        for case in payload.get('cases', []):
            expected = 2 if case['mode'] == 'smoke' else 6
            user = db.execute('select id from users where id=?', (case['user_id'],)).fetchone()
            novel = db.execute('select id from novels where id=? and user_id=?', (case['novel_id'], case['user_id'])).fetchone()
            chapters = db.execute('select count(*) from chapters where novel_id=? and user_id=?', (case['novel_id'], case['user_id'])).fetchone()[0]
            run = db.execute('select episodes, run_metadata from series_production_runs where id=? and user_id=?', (case['run_id'], case['user_id'])).fetchone()
            if not user or not novel or chapters != 4 or not run: raise AssertionError(f"missing ownership lineage: {case['mode']}")
            episodes, metadata = json.loads(run['episodes']), json.loads(run['run_metadata'])
            selected = metadata.get('selected_anchor_shot_ids') or []
            reports = list((metadata.get('anchor_quality_reports') or {}).values())
            if len(episodes) != 4 or len(selected) != expected or selected != case['selected_shot_ids'] or len(reports) != expected or not all(item.get('ready') is True for item in reports): raise AssertionError(f"series mismatch: {case['mode']}")
            jobs = db.execute('select id,shot_id,media_type,output_video_url,output_audio_url,input_assets,extra_data from media_generation_jobs where user_id=? and novel_id=?', (case['user_id'], case['novel_id'])).fetchall()
            if len(jobs) != expected or {r['shot_id'] for r in jobs} != set(selected) or {r['media_type'] for r in jobs} != {'audio_video'}: raise AssertionError(f"job mismatch: {case['mode']}")
            for job in jobs:
                calls = json.loads(job['extra_data']).get('provider_calls') or []
                if not job['output_video_url'] or not job['output_audio_url'] or not json.loads(job['input_assets']) or {item.get('capability') for item in calls} != {'reference','video','tts'}: raise AssertionError(f"media lineage mismatch: {case['mode']}")
            marks = ','.join('?' * len(selected))
            evaluations = db.execute(f'select id,artifact_id,shot_id,evidence,score from quality_evaluations where shot_id in ({marks})', selected).fetchall()
            media_jobs = {r['shot_id']: r['id'] for r in jobs}
            if len(evaluations) != expected*6: raise AssertionError(f"evaluation mismatch: {case['mode']}")
            for row in evaluations:
                evidence = json.loads(row['evidence'])
                if evidence.get('job_id') != media_jobs[row['shot_id']] or row['artifact_id'] != media_jobs[row['shot_id']]: raise AssertionError(f"parent mismatch: {case['mode']}")
            scores = [row['score'] for row in evaluations]
            if not any(isinstance(score, (int, float)) and score < 100 for score in scores): raise AssertionError(f"non-constant evaluator score missing: {case['mode']}")
            audited.append({'mode':case['mode'],'user_id':case['user_id'],'novel_id':case['novel_id'],'run_id':case['run_id'],'shots':expected,'jobs':len(jobs),'evaluations':len(evaluations)})
    finally: db.close()
    if {x['mode'] for x in audited} != {'smoke','full'}: raise AssertionError('both cases required')
    return {'status':'passed','database':str(database),'cases':audited}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--database',required=True,type=Path); p.add_argument('--manifest',required=True,type=Path); a=p.parse_args()
    print(json.dumps(audit(a.database,a.manifest),ensure_ascii=False,sort_keys=True))
if __name__ == '__main__': main()
