"""Fault injection: exercise rejection paths, without changing production files."""
import argparse,json,sys
from types import SimpleNamespace
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();sys.path.insert(0,str(a.repo/'src'))
from microgrid import q3_model as m
from microgrid.q2_physics import Battery
from microgrid.q2_model import Policy
bat=Battery();p=np.ones(144);load=np.ones(144)*3000;pv=np.zeros(144);original=m.milp
# All-zero tail violates SOC=6000, SOC minimum, and supply-demand equations.
m.milp=lambda *args,**kwargs:SimpleNamespace(x=np.zeros(865),fun=0.,status=0,message='injected invalid tail')
value,viol,status=m.tail_value(6000,p,load,pv,bat)
m.milp=original
P=m.Q3StageProblem(p,108,6000,load[None,:],pv[None,:],np.zeros((1,144)),np.ones(1),np.zeros(108),load,pv,bat,g_fixed=np.ones(144)*500,a_current=np.ones(144)*500)
pol=Policy('test',np.zeros(144),np.zeros((4,0)),'test',0,0,'optimal')
orig_tail=m.tail_value;m.tail_value=lambda *args,**kwargs:(123.,1,'time_limit')
score=m.score_candidate(m.Candidate('bad-tail',P.a_current,pol),P,np.ones(144)*500,.5)
m.tail_value=orig_tail
result={'invalid_tail_with_SOC_and_energy_violations_returned_value':value,'invalid_tail_rejected':value is None,
 'tail_with_mode_violation_returned_guard_score':score.get('score'),'tail_mode_violation_guard_rejected':score.get('score') is None,
 'meaning':'Confirmed missing failure checks, not evidence that the official executed ledger violates physics.'}
a.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
