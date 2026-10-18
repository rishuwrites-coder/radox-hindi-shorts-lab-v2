#!/usr/bin/env python3
"""Manual Radox API diagnostics and small Hindi-script model comparison.
No secrets in logs; no publishing; no image-generation calls."""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = os.getenv('RADOX_BASE_URL', 'https://radoxai.com/v1').rstrip('/')
KEY = os.getenv('RADOXAI_API_KEY', '').strip()
MODEL_OVERRIDE = os.getenv('RADOX_MODEL_ID', '').strip()
EXTENDED = os.getenv('RADOX_EXTENDED_TESTS', 'false').lower() in {'true','1','yes'}
COMPARE = os.getenv('RADOX_COMPARE_MODELS', 'true').lower() in {'true','1','yes'}
CANDIDATES = ['claude-fable-5', 'gpt-5.6-sol', 'gemini-3.7-flash', 'qwen3.8-max']
OUT = Path('output'); OUT.mkdir(exist_ok=True)
REPORT = {
 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
 'mode': 'TEST ONLY — no publishing', 'base_url': BASE,
 'extended_tests_enabled': EXTENDED, 'model_comparison_enabled': COMPARE,
 'tests': [], 'models': [], 'selected_model': None, 'model_comparison': [],
 'capability_summary': {},
 'safety_notes': [
  'The prompt uses a fictional sample, not a claim about current events.',
  'A successful API response does not establish factual accuracy or newsworthiness.',
  'Vision input does not mean image generation; no image-generation endpoint was called.',
  'No YouTube upload or publishing is implemented.'
 ]}
S = requests.Session()
S.headers.update({'Authorization': f'Bearer {KEY}', 'Content-Type':'application/json', 'User-Agent':'RadoxHindiShortsLab/1.1'})

def safe_error(r):
 try:
  d=r.json(); e=d.get('error',d) if isinstance(d,dict) else d
  msg=e.get('message',e.get('code','API error')) if isinstance(e,dict) else e
 except Exception: msg=(r.text or '')[:300]
 return {'http_status':r.status_code,'error':str(msg)[:400]}

def add(name, status, **kw):
 REPORT['tests'].append({'name':name,'status':status,**kw}); print(f'[{status}] {name}')

def req(method,path,**kw): return S.request(method,BASE+path,timeout=(10,40),**kw)

def extract_content(data):
 """Extract text across common OpenAI-compatible content shapes; reject empty/null output."""
 choices=data.get('choices') or []
 if not choices or not isinstance(choices[0],dict): return '', None, {}
 ch=choices[0]; msg=ch.get('message') or ch.get('delta') or {}
 content=msg.get('content')
 if isinstance(content,str): text=content
 elif isinstance(content,list):
  bits=[]
  for item in content:
   if isinstance(item,str): bits.append(item)
   elif isinstance(item,dict):
    v=item.get('text') or item.get('content')
    if isinstance(v,str): bits.append(v)
  text=''.join(bits)
 else: text=''
 return text.strip(), ch.get('finish_reason'), msg

def chat(model, prompt, max_tokens=500, extra=None):
 payload={'model':model,'messages':[
  {'role':'system','content':'You write clear, natural Hindi voice-over scripts. This is a fictional format test, not real news. Do not claim current facts. Return only the requested content.'},
  {'role':'user','content':prompt}], 'max_tokens':max_tokens, 'temperature':0.2}
 if extra: payload.update(extra)
 start=time.monotonic()
 try: r=req('POST','/chat/completions',json=payload)
 except requests.RequestException as e: return {'ok':False,'elapsed_seconds':round(time.monotonic()-start,2),'error':f'Network error: {type(e).__name__}'}
 elapsed=round(time.monotonic()-start,2)
 if not r.ok: return {'ok':False,'elapsed_seconds':elapsed,**safe_error(r)}
 try: data=r.json()
 except Exception: return {'ok':False,'elapsed_seconds':elapsed,'error':'HTTP success but response body was not JSON'}
 content,finish,msg=extract_content(data)
 return {'ok':bool(content),'response_received':True,'nonempty_text':bool(content),'elapsed_seconds':elapsed,
  'model_returned':data.get('model'),'finish_reason':finish,'content':content[:5000],
  'content_length_chars':len(content),'usage':data.get('usage'),'has_tool_calls':bool(msg.get('tool_calls')),
  'error':None if content else 'Response had no extractable text in choices[0].message.content'}

def caps(m):
 arch=m.get('architecture') or {}
 return {'id':m.get('id'),'name':m.get('name'),'type':m.get('type'),'owned_by':m.get('owned_by'),
 'capabilities':m.get('capabilities') or [],'input_modalities':arch.get('input_modalities',m.get('input_modalities')),
 'output_modalities':arch.get('output_modalities',m.get('output_modalities')),'context_window':m.get('context_window',m.get('context_length')),
 'pricing':m.get('pricing'),'supported_parameters':m.get('supported_parameters')}

def probe_json(model):
 start=time.monotonic(); r=req('POST','/chat/completions',json={'model':model,'messages':[{'role':'user','content':'Return exactly one JSON object with keys ok (boolean true) and language (string Hindi).'}], 'max_tokens':120,'temperature':0,'response_format':{'type':'json_object'}})
 elapsed=round(time.monotonic()-start,2)
 if not r.ok: return {'ok':False,'elapsed_seconds':elapsed,**safe_error(r)}
 try:
  data=r.json(); content,_,_=extract_content(data); parsed=json.loads(content)
  return {'ok':isinstance(parsed,dict) and parsed.get('ok') is True,'elapsed_seconds':elapsed,'valid_json':True,'content':content[:1000]}
 except Exception as e: return {'ok':False,'elapsed_seconds':elapsed,'error':f'Could not extract/parse JSON output: {type(e).__name__}'}

def probe_stream(model):
 start=time.monotonic(); chunks=[]
 try:
  with S.post(BASE+'/chat/completions',json={'model':model,'messages':[{'role':'user','content':'एक छोटा हिंदी अभिवादन लिखें।'}],'max_tokens':80,'stream':True},stream=True,timeout=(10,40)) as r:
   elapsed=round(time.monotonic()-start,2)
   if not r.ok: return {'ok':False,'elapsed_seconds':elapsed,**safe_error(r)}
   for raw in r.iter_lines(decode_unicode=True):
    if not raw: continue
    if isinstance(raw,bytes): raw=raw.decode('utf-8','replace')
    if not raw.startswith('data:'): continue
    d=raw[5:].strip()
    if d=='[DONE]': break
    try:
     obj=json.loads(d); choices=obj.get('choices') or []; delta=(choices[0].get('delta') or {}) if choices else {}; c=delta.get('content')
     if isinstance(c,str): chunks.append(c)
    except Exception: continue
  return {'ok':bool(''.join(chunks).strip()),'elapsed_seconds':round(time.monotonic()-start,2),'content_chunks':len(chunks),'content_preview':''.join(chunks)[:1000]}
 except requests.RequestException as e: return {'ok':False,'error':f'Network error: {type(e).__name__}'}

def probe_tools(model):
 tool={'type':'function','function':{'name':'format_test','description':'Return metadata for a fictional test only.','parameters':{'type':'object','properties':{'language':{'type':'string'},'test_only':{'type':'boolean'}},'required':['language','test_only'],'additionalProperties':False}}}
 start=time.monotonic(); r=req('POST','/chat/completions',json={'model':model,'messages':[{'role':'user','content':'Call format_test with language Hindi and test_only true.'}],'tools':[tool],'tool_choice':{'type':'function','function':{'name':'format_test'}},'max_tokens':150,'temperature':0})
 elapsed=round(time.monotonic()-start,2)
 if not r.ok: return {'ok':False,'elapsed_seconds':elapsed,**safe_error(r)}
 try:
  d=r.json(); _,_,msg=extract_content(d); calls=msg.get('tool_calls') or []
  return {'ok':bool(calls),'elapsed_seconds':elapsed,'tool_call_returned':bool(calls),'tool_calls':calls[:2]}
 except Exception as e: return {'ok':False,'elapsed_seconds':elapsed,'error':f'Could not parse response: {type(e).__name__}'}

def save():
 (OUT/'radox-report.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2),encoding='utf-8')
 lines=['# Radox API diagnostic report','',f"- Generated: {REPORT['generated_at_utc']}",f"- Selected model: {(REPORT.get('selected_model') or {}).get('id','None')}",f"- Model comparison: {COMPARE}",f"- Extended probes: {EXTENDED}",'- Publishing: disabled.','', '## Test results','']
 for t in REPORT['tests']:
  lines.append(f"- **{t['status']}** — {t['name']}")
  if t.get('error'): lines.append('  - '+str(t['error']))
  if t.get('output_preview') is not None: lines += ['', '```text', str(t['output_preview']), '```', '']
 lines += ['', '## Model comparison','']
 for x in REPORT['model_comparison']:
  lines.append(f"### {x['model_id']} — {'PASS' if x['ok'] else 'FAIL'}")
  lines.append(f"- Latency: {x.get('elapsed_seconds','?')} s; characters: {x.get('content_length_chars',0)}; finish: {x.get('finish_reason')}")
  if x.get('error'): lines.append('- Error: '+str(x['error']))
  if x.get('content'): lines += ['', '```text', x['content'][:2500], '```', '']
 lines += ['', '## Advertised capability counts','']
 for k,v in REPORT.get('capability_summary',{}).items(): lines.append(f'- {k}: {v}')
 lines += ['', '## Notes','',*[f'- {n}' for n in REPORT['safety_notes']]]
 (OUT/'radox-report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def main():
 if not KEY:
  add('configuration','FAIL',error='RADOXAI_API_KEY secret is missing'); save(); sys.exit(2)
 try: r=req('GET','/models')
 except requests.RequestException as e:
  add('GET /models','FAIL',error=f'Network error: {type(e).__name__}'); save(); sys.exit(1)
 if not r.ok: add('GET /models','FAIL',**safe_error(r)); save(); sys.exit(1)
 try:
  raw=r.json(); models=raw.get('data',[]) if isinstance(raw,dict) else []
  REPORT['models']=[caps(m) for m in models if isinstance(m,dict)]
  REPORT['capability_summary']={cap:sum(1 for m in models if cap in (m.get('capabilities') or [])) for cap in ['vision','tools','streaming','reasoning','json_mode','web_search']}
  add('GET /models','PASS',model_count=len(models))
 except Exception as e: add('parse /models','FAIL',error=type(e).__name__); save(); sys.exit(1)
 ids={m.get('id') for m in models if isinstance(m,dict)}
 chosen=MODEL_OVERRIDE if MODEL_OVERRIDE else next((x for x in CANDIDATES if x in ids), next(iter(ids),None))
 if MODEL_OVERRIDE and MODEL_OVERRIDE not in ids:
  add('select model','FAIL',error=f'Requested model not in catalog: {MODEL_OVERRIDE}'); chosen=None
 elif chosen:
  REPORT['selected_model']=next((caps(m) for m in models if m.get('id')==chosen),{'id':chosen}); add('select model','PASS',model_id=chosen)
 else: add('select model','FAIL',error='No model IDs found')
 prompt='काल्पनिक नमूना: शहर की लाइब्रेरी ने विद्यार्थियों के लिए अपने खुलने का समय बढ़ाया है। 2–3 छोटे वाक्यों में स्वाभाविक हिंदी Shorts voice-over लिखें। स्पष्ट रूप से “काल्पनिक नमूना” कहें। कोई असली समाचार या तथ्य न गढ़ें।'
 targets=[]
 if chosen: targets.append(chosen)
 if COMPARE and not MODEL_OVERRIDE: targets += [x for x in CANDIDATES if x in ids and x not in targets]
 # If explicitly requested model, test only that model; comparison avoids surprise cost.
 for mid in targets:
  result=chat(mid,prompt, max_tokens=350)
  entry={'model_id':mid,**result}; REPORT['model_comparison'].append(entry)
  add(f'Hindi script response: {mid}','PASS' if result.get('ok') else 'FAIL',elapsed_seconds=result.get('elapsed_seconds'),content_length_chars=result.get('content_length_chars',0),finish_reason=result.get('finish_reason'),error=result.get('error'),output_preview=result.get('content',''))
 if chosen and EXTENDED:
  for name,fn in [('JSON mode',probe_json),('streaming',probe_stream),('tool calling',probe_tools)]:
   try:
    x=fn(chosen); add(name,'PASS' if x.get('ok') else 'FAIL',**x)
   except Exception as e: add(name,'FAIL',error=type(e).__name__)
 save(); print(f"Reports written; catalog models={len(REPORT['models'])}, compared={len(REPORT['model_comparison'])}.")
 if not any(t['name']=='GET /models' and t['status']=='PASS' for t in REPORT['tests']): sys.exit(1)
 if chosen and not any(x.get('ok') for x in REPORT['model_comparison']): sys.exit(1)
if __name__=='__main__': main()
