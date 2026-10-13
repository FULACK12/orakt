"""One explicit chapter retry; shared locks and cumulative rejection policy.

Mechanical success remains content_review_pending. No publication or training.
"""
import argparse
from pathlib import Path
from sqlalchemy import text
from app.db.session import get_session_factory
from app.dossier_compact_writer import run as write_chapter
from app.model_workload import MODEL_WORKLOAD_LOCK_ID
from app.report_rejections import guard
from app.report_usage import collect_usage


def run(source, output, chapter, root):
    if output.exists():raise ValueError('Preserve prior chapter attempt')
    if not output.resolve().is_relative_to((root/'drafts'/chapter).resolve()):
        raise ValueError('Output must remain under the existing chapter rejection root')
    guard(root,chapter)
    usage=collect_usage(root/'drafts')
    if usage['inputTokensKnown']+usage['outputTokensKnown']>=120000:
        raise RuntimeError('Known local-token budget exhausted; no automatic retry')
    with get_session_factory()().get_bind().connect() as connection:
        owned=[]
        try:
            for key in (624730015831,624730015811):
                if not connection.scalar(text('SELECT pg_try_advisory_lock(:key)'),{'key':key}):
                    raise RuntimeError('Another report worker owns the global lock')
                owned.append(key)
            if not connection.scalar(text('SELECT pg_try_advisory_xact_lock(:key)'),{'key':MODEL_WORKLOAD_LOCK_ID}):
                raise RuntimeError('Local model busy')
            write_chapter(source,output,chapter,redact_numbers=True,reasoning=True,
                          max_attempts=1,rejection_root=root,model_connection=connection)
        finally:
            for key in reversed(owned):connection.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':key})


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--chapter',required=True)
    a=p.parse_args();run(a.source,a.output,a.chapter,a.root)
