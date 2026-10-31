"""Live Neon verification using synthetic records only; no local-record export."""
import json, os, secrets, subprocess, sys, time, uuid
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from emergencycore import create_app
from emergencycore.database import get_db

def main():
 token=secrets.token_urlsafe(32)
 environment=dict(os.environ,PORT='5003',APP_ENV='production',API_TOKEN=token,AI_PROVIDER='none',LOCAL_MODEL_ENABLED='false')
 headers={'Authorization':'Bearer '+token}
 base='http://127.0.0.1:5003/api/v1'
 process=None; identifier=None; scenario_id=None
 def start():
  p=subprocess.Popen([sys.executable,'backend/serve.py'],cwd=ROOT,env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(150):
   if p.poll() is not None:raise RuntimeError('Verification backend exited at startup')
   try:
    if requests.get(base+'/health',timeout=2).status_code==200:return p
   except requests.RequestException:pass
   time.sleep(.2)
  p.terminate();raise RuntimeError('Verification server startup timed out')
 try:
  process=start();print('PASS: production PostgreSQL backend started on port 5003',flush=True)
  response=requests.post(base+'/incidents',headers=headers,json={'description':'NEON VERIFICATION ONLY: Synthetic flood report with stranded people. Not an actual emergency.','urgency':'low'},timeout=30)
  assert response.status_code==201,response.status_code
  identifier=response.json()['id'];assert response.json()['analysis']['priority']=='critical'
  print('PASS: HTTP incident creation and local triage',flush=True)
  app=create_app({'APP_ENV':'production','API_TOKEN':token,'AI_PROVIDER':'none'})
  with app.app_context():
   assert get_db().execute('SELECT id FROM incidents WHERE id=?',(identifier,)).fetchone()
   event=get_db().execute("SELECT id,payload FROM events WHERE type='incident.created' ORDER BY id DESC LIMIT 1").fetchone()
   assert json.loads(event['payload'])['id']==identifier
   event_id=event['id']
   rollback_id=str(uuid.uuid4())
   try:
    with get_db():
     get_db().execute('INSERT INTO incidents SELECT ?,description,location,latitude,longitude,urgency,status,analysis,created_at,updated_at FROM incidents WHERE id=?',(rollback_id,identifier))
     get_db().execute('INSERT INTO events(type,payload,created_at) VALUES(?,?,?)',('verification.rollback',json.dumps({'id':rollback_id}),'2026-11-01T00:00:00+00:00'))
     raise RuntimeError('Intentional rollback')
   except RuntimeError:pass
   assert get_db().execute('SELECT id FROM incidents WHERE id=?',(rollback_id,)).fetchone() is None
   assert get_db().execute('SELECT id FROM events WHERE payload=?',(json.dumps({'id':rollback_id}),)).fetchone() is None
  print('PASS: incident/event atomic commit and atomic rollback',flush=True)
  with requests.get(base+'/events?after='+str(event_id-1),headers=headers,stream=True,timeout=15) as stream:
   assert stream.status_code==200
   found=False
   for line in stream.iter_lines(chunk_size=1):
    if line.startswith(b'data:'):
     assert json.loads(line[5:])['id']==identifier;found=True;break
   assert found
  print('PASS: persisted SSE event replay over HTTP',flush=True)
  response=requests.patch(base+'/incidents/'+identifier,headers=headers,json={'status':'verified'},timeout=20);assert response.status_code==200
  process.terminate();process.wait(timeout=15);process=start()
  restored=requests.get(base+'/incidents/'+identifier,headers=headers,timeout=20)
  assert restored.status_code==200 and restored.json()['status']=='verified'
  print('PASS: incident and verified status persisted across backend process restart',flush=True)
  scenario=requests.post(base+'/scenarios',headers=headers,json={'region_id':'anchorage','name':'NEON VERIFICATION ONLY','mode':'simulation'},timeout=30)
  assert scenario.status_code==201,scenario.status_code
  scenario_id=scenario.json()['id']
  with app.app_context():
   from emergencycore.services.regions import load_network
   from emergencycore.services.routing import graph_from,route
   import networkx as nx
   network=load_network('anchorage');nodes={n['id']:n for n in network['nodes']};graph=graph_from(network)
   origin=next(iter(graph));distances=nx.single_source_dijkstra_path_length(graph,origin,weight='travel_time_s');destination=max(distances,key=distances.get)
   baseline=route(graph,origin,destination,nodes);edge=baseline['edge_ids'][len(baseline['edge_ids'])//2]
  observation=requests.post(base+'/scenarios/'+scenario_id+'/observations',headers=headers,json={'asset_id':edge,'state':'blocked','note':'Synthetic Neon verification closure'},timeout=30);assert observation.status_code==201
  compared=requests.post(base+'/scenarios/'+scenario_id+'/routes',headers=headers,json={'origin':nodes[origin]['coordinates'],'destination':nodes[destination]['coordinates']},timeout=45)
  assert compared.status_code==201,compared.status_code
  assert edge not in (compared.json().get('adapted') or {}).get('edge_ids',[])
  assert requests.get(base+'/scenarios/'+scenario_id+'/routes',headers=headers,timeout=20).json()['items']
  print('PASS: Neon road dataset, scenario, observation and saved blocked-edge route comparison',flush=True)
  print('LIVE NEON VERIFICATION PASSED',flush=True)
 finally:
  if process and process.poll() is None:process.terminate();process.wait(timeout=15)
  if identifier or scenario_id:
   app=create_app({'APP_ENV':'development'})
   with app.app_context(),get_db():
    if scenario_id:
     for table in ['route_results','observations']:get_db().execute('DELETE FROM '+table+' WHERE scenario_id=?',(scenario_id,))
     get_db().execute('DELETE FROM scenarios WHERE id=?',(scenario_id,))
    if identifier:get_db().execute('DELETE FROM incidents WHERE id=?',(identifier,))
    # Delete only this verifier's synthetic events, preserving all other event history.
    for row in get_db().execute('SELECT id,payload FROM events'):
     payload=json.loads(row['payload'])
     if payload.get('id') in {value for value in (identifier,scenario_id) if value} or (scenario_id and payload.get('scenario_id')==scenario_id):
      get_db().execute('DELETE FROM events WHERE id=?',(row['id'],))
if __name__=='__main__':main()
