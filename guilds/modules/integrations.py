"""External adapters are opt-in. Fixtures exercise the same review workflow."""
import io, os, re
from html.parser import HTMLParser
import httpx
from .core import *

class RosterParser(HTMLParser):
    def __init__(self): super().__init__(); self.names=[]; self.capture=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='a' and ('Adventure/Profile' in a.get('href','') or 'Adventure?profileTarget' in a.get('href','')): self.capture=True
    def handle_data(self,data):
        if self.capture and data.strip(): self.names.append(data.strip())
    def handle_endtag(self,tag):
        if tag=='a': self.capture=False

def roster_html(html):
    parser=RosterParser(); parser.feed(html)
    return list(dict.fromkeys(parser.names))

def ocr(image_bytes,timeout=30):
    from PIL import Image, ImageOps
    import pytesseract
    if len(image_bytes)>10*1024*1024:
        raise Invalid('Image exceeds 10 MB')
    try:
        with Image.open(io.BytesIO(image_bytes)) as im:
            if im.format not in ('PNG','JPEG','WEBP'):
                raise Invalid('Use a PNG, JPEG or WebP image')
            if im.width*im.height>20000000:
                raise Invalid('Image exceeds 20 megapixels')
            im.verify()
        with Image.open(io.BytesIO(image_bytes)) as im:
            im.load()
            with ImageOps.grayscale(im) as gray, ImageOps.autocontrast(gray) as prepared:
                return pytesseract.image_to_string(prepared,config='--psm 6',timeout=max(.1,min(30,timeout)))
    except (OSError,RuntimeError,SyntaxError,Image.DecompressionBombError): raise Invalid('OCR unavailable, timed out, or image invalid. Check the image and local OCR installation.') from None

def handle(g,action,p,role,user):
    if action=='twitch_link':
        m=owner_or_self(g,role,user,p['member']); handle=p.get('handle','')
        if handle and not re.fullmatch(r'[A-Za-z0-9_]{1,25}',handle):
            raise Invalid('Invalid Twitch handle')
        m.data['twitch']=handle; m.save(); return public(m)
    require(role)
    if action=='roster_preview':
        names=roster_html(text(p['html'],'roster HTML',1000000))
        if not names:
            raise Invalid('No member links recognized. No roster changes were made.')
        return {'names':names,'requires_confirmation':True}
    if action=='streams_fixture':
        streams=p['streams']
        if not isinstance(streams,list):
            raise Invalid('Streams must be a list')
        clean=[]
        for stream in streams: clean.append({'handle':text(stream['handle'],maximum=25),'title':text(stream['title']),'viewers':integer(stream['viewers'],'viewers'),'category':str(stream.get('category','BDO')),'partner':bool(stream.get('partner',False))})
        return public(save(g,'streams',{'items':clean,'source':'fixture','at':now()},'current'))
    if action in ('roster_fetch','roster_source','streams_refresh'):
        raise Invalid('Use the shared service to prepare external integrations')
    raise Invalid('Unknown integration action')

def paired_scores(texts):
    """Read cropped names and K/D columns; mismatch is an error, never a guess."""
    if len(texts)%2 or not 2<=len(texts)<=10:
        raise Invalid('Supply 1–5 pairs: names image followed by kills/deaths image')
    output=[]
    for i in range(0,len(texts),2):
        names=[line.strip() for line in texts[i].splitlines() if line.strip() and line.strip().casefold() not in ['name','names','family','family name']]
        scores=[]
        for line in texts[i+1].splitlines():
            line=line.strip()
            if not line or re.search(r'kills|deaths',line,re.I):continue
            match=re.fullmatch(r'([\d,]+)\s+([\d,]+)',line)
            if not match:
                raise Invalid('Unrecognized score row. Crop to two numeric columns or enter CSV manually.')
            scores.append([int(v.replace(',','')) for v in match.groups()])
        if len(names)!=len(scores) or not names:
            raise Invalid('Names and scores have different row counts. Crop aligned panels and retry.')
        output.extend({'name':name,'kills':score[0],'deaths':score[1]} for name,score in zip(names,scores))
    return output

def gear_numbers(texts):
    value='\n'.join(texts);result={}
    for key,pattern in [('aap',r'(?:AAP|Awakening\s+AP)\s*[:=]?\s*(\d+)'),('dp',r'\bDP\s*[:=]?\s*(\d+)'),('ap',r'(?<!\w)AP\s*[:=]?\s*(\d+)')]:
        match=re.search(pattern,re.sub(r'Awakening\s+AP','AAP',value,flags=re.I),re.I)
        if match:result[key]=int(match.group(1))
    return result

def fetch_roster(url):
    from urllib.parse import urlparse
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in {'www.naeu.playblackdesert.com','www.sea.playblackdesert.com','www.tr.playblackdesert.com','www.jp.playblackdesert.com','www.kr.playblackdesert.com','www.tw.playblackdesert.com'} or parsed.username or parsed.port not in (None,443):
        raise Invalid('Use an official regional Black Desert HTTPS guild page')
    response=httpx.get(url,timeout=15,follow_redirects=False)
    if response.status_code==429:
        raise Invalid('BDO rate limit reached. No roster changes made.')
    response.raise_for_status();names=roster_html(response.text)
    if not names:
        raise Invalid('No roster recognized. No members were changed.')
    return names


def fetch_streams(g):
    if g.config.get('integrations',{}).get('twitch') is False:
        raise Invalid('Twitch is disabled in guild settings')
    client=os.getenv('TWITCH_CLIENT_ID'); token=os.getenv('TWITCH_ACCESS_TOKEN')
    if not client or not token:
        raise Invalid('Set TWITCH_CLIENT_ID and TWITCH_ACCESS_TOKEN, or use the local stream fixture')
    headers={'Client-Id':client,'Authorization':'Bearer '+token}
    response=httpx.get('https://api.twitch.tv/helix/streams',params={'game_id':'386821','first':100},headers=headers,timeout=15)
    if response.status_code==429:
        raise Invalid('Twitch rate limit reached; retry later')
    response.raise_for_status()
    data=response.json()['data']; partner_logins=set()
    if data:
        try:
            users=httpx.get('https://api.twitch.tv/helix/users',params=[('login',s['user_login']) for s in data],headers=headers,timeout=15)
            users.raise_for_status()
            partner_logins={u['login'].casefold() for u in users.json()['data'] if u.get('broadcaster_type')=='partner'}
        except (httpx.HTTPError,KeyError,TypeError,ValueError):
            pass
    streams=[{'handle':s['user_login'],'title':s['title'],'viewers':s['viewer_count'],'category':s.get('game_name') or 'BDO','partner':s['user_login'].casefold() in partner_logins} for s in data]
    return {'items':streams,'source':'Twitch','at':now()}
