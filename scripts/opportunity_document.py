"""Bounded complete SEC HTML-to-text streaming; never truncate accepted evidence."""
from codecs import getincrementaldecoder
from html.parser import HTMLParser
import hashlib
import re
from urllib.parse import urlsplit
from .opportunity_common import DataUnavailable

RAW_LIMIT=24_000_000
TEXT_LIMIT=3_000_000


class CompleteText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip=[]
        self.parts=[]
        self.pending=[]
        self.text_bytes=0
    def flush(self):
        text=' '.join(''.join(self.pending).split())
        if text:
            self.parts.append(text)
        self.pending=[]
    def handle_starttag(self,tag,attrs):
        self.flush()
        if tag in ('script','style'):
            self.skip.append(tag)
    def handle_endtag(self,tag):
        self.flush()
        if self.skip and tag==self.skip[-1]:
            self.skip.pop()
    def handle_data(self,data):
        if self.skip:
            return
        self.text_bytes += len(data.encode('utf-8'))
        if self.text_bytes > TEXT_LIMIT:
            raise DataUnavailable('issuer_document_text_safety_limit')
        self.pending.append(data)
    def handle_comment(self,data):
        self.flush()
    def result(self):
        self.flush()
        if self.skip or getattr(self,'rawdata','').strip():
            raise DataUnavailable('issuer_document_incomplete_markup')
        result=' '.join(self.parts)
        if not result:
            raise DataUnavailable('empty_issuer_document')
        return result


def stream_document(session,url,user_agent,timeout):
    parts=urlsplit(url)
    if parts.scheme!='https' or parts.hostname!='www.sec.gov' or parts.username or parts.password or not parts.path.startswith('/Archives/edgar/data/'):
        raise DataUnavailable('unapproved_issuer_source')
    response=None
    try:
        response=session.get(url,headers={'User-Agent':user_agent},timeout=timeout,allow_redirects=False,stream=True)
        if response.status_code!=200:
            raise DataUnavailable('issuer_redirect_or_non_success')
        headers=getattr(response,'headers',{})
        length=headers.get('Content-Length')
        if length and str(length).isdigit() and int(length)>RAW_LIMIT:
            raise DataUnavailable('issuer_document_transport_safety_limit')
        parser=CompleteText(); digest=hashlib.sha256(); raw_bytes=0; decoder=None; encoding=None
        for block in response.iter_content(65536):
            if not block:
                continue
            raw_bytes+=len(block)
            if raw_bytes>RAW_LIMIT:
                raise DataUnavailable('issuer_document_transport_safety_limit')
            digest.update(block)
            if decoder is None:
                match=re.search(r'charset\s*=\s*[\"\x27]?([A-Za-z0-9_-]+)',headers.get('Content-Type',''),re.I)
                if not match:
                    match=re.search(r'charset\s*=\s*[\"\x27]?([A-Za-z0-9_-]+)',block[:8192].decode('ascii','ignore'),re.I)
                encoding=match.group(1).lower() if match else 'utf-8-sig'
                if encoding not in ('utf-8','utf-8-sig','utf8','us-ascii','ascii','windows-1252','iso-8859-1'):
                    raise DataUnavailable('issuer_document_encoding_requires_review')
                decoder=getincrementaldecoder(encoding)(errors='strict')
            parser.feed(decoder.decode(block,final=False))
        if decoder is None:
            raise DataUnavailable('empty_issuer_document')
        parser.feed(decoder.decode(b'',final=True)); parser.close()
        text=parser.result()
        return {'text':text,'sha256':digest.hexdigest(),'raw_bytes':raw_bytes,
                'text_bytes':len(text.encode('utf-8')),'encoding':encoding,
                'extraction':'complete_streamed_text_excluding_script_style','complete':True}
    except DataUnavailable:
        raise
    except Exception as exc:
        raise DataUnavailable('issuer_document_unavailable:'+type(exc).__name__) from None
    finally:
        if response is not None:
            response.close()
