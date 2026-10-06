from app.dossier_model_stream import repeated_tail,generate
import app.dossier_model_stream as module
import json,pytest


def test_repetitive_tail_is_not_successful_reasoning():
    assert repeated_tail(('the same unsupported financial assertion repeated. '*5)*12)
    assert not repeated_tail('A distinct short factual explanation.')
    assert not repeated_tail(''.join(str(i)+' unique text. ' for i in range(100)))


class Reply:
    def __init__(self,lines):self.lines=lines
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def raise_for_status(self):pass
    def iter_lines(self):return iter(json.dumps(x) for x in self.lines)


def client(lines):
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def stream(self,*a,**kwargs):assert kwargs['json']['stream'] is True;return Reply(lines)
    return Client


def test_stream_requires_terminal_message_and_retains_partial(monkeypatch):
    monkeypatch.setattr(module.httpx,'Client',client([{'message':{'content':'{"analysis":'}},{'message':{'content':'"ok"}'},'done':True,'done_reason':'stop'}]))
    raw=generate('http://local.test',{},lambda p:None,lambda p:None)
    assert raw['message']['content']=='{"analysis":"ok"}'
    saved=[]
    monkeypatch.setattr(module.httpx,'Client',client([{'message':{'content':'unfinished'}}]))
    with pytest.raises(ValueError,match='without completion'):generate('http://local.test',{},lambda p:None,saved.append)
    assert saved[0]['complete'] is False and saved[0]['message']['content']=='unfinished'
