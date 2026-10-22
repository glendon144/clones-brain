#!/usr/bin/env python3
import json, os, sys, urllib.parse, urllib.request, urllib.error

BASE_URL = os.environ.get('CLONES_BRAIN_URL', 'http://127.0.0.1:8765').rstrip('/')
ALLOW_WRITE = os.environ.get('CLONES_BRAIN_MCP_ALLOW_WRITE', '0') == '1'
TIMEOUT = float(os.environ.get('CLONES_BRAIN_MCP_TIMEOUT', '30'))

TOOLS = [
  {'name':'health','description':'Check local clones-brain health and thought count.','inputSchema':{'type':'object','properties':{},'required':[]}},
  {'name':'list_recent','description':'List recent thoughts from local clones-brain memory.','inputSchema':{'type':'object','properties':{'limit':{'type':'integer','minimum':1,'maximum':200,'default':20}},'required':[]}},
  {'name':'search_thoughts','description':'Search local clones-brain memory.','inputSchema':{'type':'object','properties':{'query':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':200,'default':10}},'required':['query']}},
  {'name':'recover_context','description':'Recover a compact context bundle relevant to a topic or question.','inputSchema':{'type':'object','properties':{'query':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':200,'default':10},'max_chars':{'type':'integer','minimum':256,'maximum':100000,'default':12000}},'required':['query']}}
]
if ALLOW_WRITE:
  TOOLS.append({'name':'capture_thought','description':'Save a new thought to local clones-brain.','inputSchema':{'type':'object','properties':{'body':{'type':'string'},'title':{'type':'string'},'thought_type':{'type':'string','default':'observation'},'source':{'type':'string'},'project':{'type':'string'},'tags':{'type':'array','items':{'type':'string'}},'metadata':{'type':'object'}},'required':['body']}})
TOOL_NAMES = {t['name'] for t in TOOLS}

def get(path):
  req=urllib.request.Request(BASE_URL+path,headers={'Accept':'application/json'})
  with urllib.request.urlopen(req,timeout=TIMEOUT) as r: return json.loads(r.read().decode())

def post(path,payload):
  data=json.dumps(payload).encode()
  req=urllib.request.Request(BASE_URL+path,data=data,method='POST',headers={'Accept':'application/json','Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=TIMEOUT) as r: return json.loads(r.read().decode())

def call_tool(name,args):
  if name not in TOOL_NAMES: raise ValueError(f'unknown or disabled tool: {name}')
  if name=='health': return get('/health')
  if name=='list_recent': return get('/list_recent?'+urllib.parse.urlencode({'limit':int(args.get('limit',20))}))
  if name=='search_thoughts': return post('/search_thoughts',{'query':args['query'],'limit':int(args.get('limit',10))})
  if name=='recover_context': return post('/recover_context',{'query':args['query'],'limit':int(args.get('limit',10)),'max_chars':int(args.get('max_chars',12000))})
  if name=='capture_thought': return post('/capture_thought',{k:v for k,v in args.items() if v is not None})

def send(obj):
  sys.stdout.write(json.dumps(obj,separators=(',',':'))+'\n'); sys.stdout.flush()

def result(i,p): send({'jsonrpc':'2.0','id':i,'result':p})
def error(i,c,m): send({'jsonrpc':'2.0','id':i,'error':{'code':c,'message':m}})

def main():
  for raw in sys.stdin:
    raw=raw.strip()
    if not raw: continue
    try: msg=json.loads(raw)
    except Exception as e: error(None,-32700,f'parse error: {e}'); continue
    if 'id' not in msg: continue
    i=msg.get('id'); method=msg.get('method'); params=msg.get('params') or {}
    try:
      if method=='initialize': result(i,{'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'clones-brain','version':'0.1.0'}})
      elif method=='ping': result(i,{})
      elif method=='tools/list': result(i,{'tools':TOOLS})
      elif method=='tools/call':
        payload=call_tool(params.get('name',''),params.get('arguments') or {})
        result(i,{'content':[{'type':'text','text':json.dumps(payload,ensure_ascii=False,indent=2)}],'isError':False})
      else: error(i,-32601,f'method not found: {method}')
    except urllib.error.HTTPError as e:
      body=e.read().decode(errors='replace')
      result(i,{'content':[{'type':'text','text':f'clones-brain HTTP {e.code}: {body}'}],'isError':True})
    except Exception as e:
      result(i,{'content':[{'type':'text','text':f'clones-brain error: {e}'}],'isError':True})

if __name__=='__main__': main()
