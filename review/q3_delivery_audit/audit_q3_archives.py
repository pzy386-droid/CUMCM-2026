"""Independent audit of archived ledgers and snapshots; imports no production microgrid code."""
import argparse,csv,datetime as dt,hashlib,json,math
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from audit_q3_delivery import rows,day

def readj(p):return json.loads(p.read_text(encoding='utf-8'))
def readc(p):
    with p.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def require(ok,msg):
    if not ok:raise ValueError(msg)

def audit_run(path,raw,record):
    checked=0
    for name,info in record['files'].items():
        p=path/name
        require(p.is_file() and p.stat().st_size==info['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==info['sha256'],f'hash {p}')
        checked+=1
    meta=readj(path/'run_metadata.json');ledger=readc(path/'ledger_full_year.csv');n=len(ledger)
    require(n==meta['days_simulated']*144,'number of slots')
    A=lambda key:np.array([float(r[key]) for r in ledger])
    p=A('price_yuan_per_kwh'); L=A('load_kw');V=A('pv_kw');g=A('g0_kwh');a=A('effective_contract_kwh');e=A('emergency_grid_kwh');c=A('charge_kwh');d=A('discharge_kwh');r=A('spill_kwh');s0=A('soc_start_kwh');s1=A('soc_end_kwh')
    z=np.arange(n);days=z//144;slots=z%144
    require(all(x['date']==str(dt.date(2025,1,1)+dt.timedelta(days=int(di))) and int(x['slot'])==ki+1 for x,di,ki in zip(ledger,days,slots)),'calendar')
    price=np.array([x[1] for x in next(iter(rows(raw/'附件1.xlsx').values()))[1:]],float)
    input_=rows(raw/'附件2.xlsx');load=np.array([x[1:] for x in input_['小区负载'][1:]],float);pv=np.array([x[1:] for x in input_['光伏发电实际功率'][1:]],float)
    forecasts={};current_date=None
    for rr in next(iter(rows(raw/'附件3.xlsx').values()))[1:]:
        if rr[0] not in (None,''):current_date=day(rr[0])
        hour=rr[1].hour if hasattr(rr[1],'hour') else int(str(rr[1]).split(':')[0])
        if hour==0:forecasts[current_date]=np.array(rr[2:26],float)
    require(np.array_equal(p,price[slots]) and np.array_equal(L,load[days,slots]) and np.array_equal(V,pv[days,slots]),'raw input binding')
    for key,fn in [('附件1','附件1.xlsx'),('附件2','附件2.xlsx'),('附件3','附件3.xlsx')]:
        require(meta['input_sha256'][key]==hashlib.sha256((raw/fn).read_bytes()).hexdigest(),'input SHA')
    kappa=meta['strategy_parameters']['kappa']
    pg=p*g; adj=p*(1.5*np.maximum(a-g,0)+kappa*np.maximum(g-a,0)); ec=5*p*e; total=pg+adj+ec
    maxabs=lambda x:float(np.max(np.abs(x)))
    residuals={'energy':maxabs(a+V/6+d+e-L/6-c-r),'soc':maxabs(s1-s0-.9*c+d/.9),'cross_slot_soc':maxabs(s0[1:]-s1[:-1]),
      'planned_cost':maxabs(pg-A('planned_cost_yuan')),'adjustment_cost':maxabs(adj-A('adjustment_cost_yuan')),'emergency_cost':maxabs(ec-A('emergency_cost_yuan')),'total_cost':maxabs(total-A('total_cost_yuan'))}
    require(all(v<=1e-6 for v in residuals.values()),str(residuals))
    require(all(np.isfinite(x).all() for x in [g,a,e,c,d,r,s0,s1,total]),'nonfinite')
    require(min(x.min() for x in [g,a,e,c,d,r])>=-1e-6,'negative energy')
    require(min(s0.min(),s1.min())>=1200-1e-6 and max(s0.max(),s1.max())<=10800+1e-6,'SOC bounds')
    require(max(c.max(),d.max())<=5000/6+1e-6,'power')
    require(max(np.minimum(c,d).max(),np.minimum(c,e).max(),np.minimum(d,r).max())<=1e-6,'mode')
    require(s0[0]==6000 and np.all(g[:144]==0) and np.all(c[:144]==0) and np.all(d[:144]==0),'cold start')
    efull=[]
    for di in range(n//144):
        start=di*144; k=0
        while k<144:
            if e[start+k]<=1e-9:k+=1;continue
            left=k
            while k<144 and e[start+k]>1e-9:k+=1
            efull.append((str(dt.date(2025,1,1)+dt.timedelta(days=di)),left+1,k,float(e[start+left:start+k].sum())))
    events=readc(path/'emergency_events.csv')
    require(len(events)==len(efull),'event count')
    for x,y in zip(events,efull):require((x['date'],int(x['slot_first']),int(x['slot_last']))==y[:3] and abs(float(x['emergency_kwh'])-y[3])<1e-6,'event contents')
    actions=Counter();policy_error=projection_error=0.;candidate_violations=[]
    for di in range(n//144):
        date=str(dt.date(2025,1,1)+dt.timedelta(days=di));off=di*144
        cs=readj(path/'contract_snapshots'/f'{date}.json');ps=readj(path/'policy_snapshots'/f'{date}.json');fa=readj(path/'forecast_archive'/f'{date}.json')
        if di:
            forecast_load=load[di-7] if di>=7 else load[:di].mean(axis=0)
            forecast_pv=np.interp(np.arange(1,145)/6,np.arange(25),np.r_[pv[di-1,-1],forecasts[date]])
            require(maxabs(forecast_load-np.array(fa['load_kw']))<1e-9,'historical load forecast binding')
            require(maxabs(forecast_pv-np.array(fa['vintages']['0']['today_kw']))<1e-9,'published PV forecast binding')
            require(maxabs((forecast_load-forecast_pv)/6-np.array(fa['nhat0_kwh']))<1e-9,'net forecast binding')
        require(len(cs)==len(ps),'snapshots count')
        inforce=g[off:off+144].copy();gh=hashlib.sha256(inforce.astype(np.float64).tobytes()).hexdigest()
        eps=(L[off:off+144]-V[off:off+144])/6-np.array(fa.get('nhat0_kwh',[0]*144))
        for ii,(cc,pol) in enumerate(zip(cs,ps)):
            k0=cc['k0'];end=cs[ii+1]['k0'] if ii+1<len(cs) else 144
            require(cc['g0_sha256']==gh and abs(cc['soc_start']-s0[off+k0])<1e-6,'snapshot state/hash')
            require(all(h<di for h in cc['source_days']),'future source day')
            require(cc['vintage_used']<=k0/6,'future forecast vintage')
            if k0:
                require(maxabs(np.array(cc['contract_before'])-inforce)<1e-6,'contract before')
                aft=np.array(cc['contract_after']); require(maxabs(aft[:k0]-inforce[:k0])<1e-6,'revised past')
                if cc['action']!='accept':require(maxabs(aft-inforce)<1e-6,'nonaccept changed contract')
                if cc['action']=='accept' and meta['strategy_parameters']['guard']:
                    old,new=cc['keep_score'],cc['new_score']; require(old is not None and new is not None and new<old-max(1e-6,1e-8*abs(old)),'guard ordering')
                inforce=aft
                if di>=31:actions[(cc['stage'],cc['action'])]+=1
            require(maxabs(a[off+k0:off+end]-inforce[k0:end])<1e-6,'effective vs snapshots')
            for k in range(k0,end):
                alpha=float(pol['alpha'][k]);F=pol['feature_dim'];feat=[eps[k],float(eps[max(0,k-6):k].mean()) if k else 0]
                x=alpha+sum(float(b)*f for b,f in zip(pol['beta'][k//36],feat[:F])) if F else alpha
                policy_error=max(policy_error,abs(x-float(ledger[off+k]['x_raw_kwh'])))
                j=off+k;net=L[j]/6-V[j]/6-a[j]
                low=-min(s0[j]-1200,5000/6/.9,max(net,0)/.9)
                high=min(10800-s0[j],.9*5000/6,.9*max(-net,0))
                exe=min(max(x,low),high)
                projection_error=max(projection_error,abs(exe-(s1[j]-s0[j])))
        if len(cs)>1:require(len({tuple(cc['source_days']) for cc in cs})==1,'changed source days')
    require(policy_error<1e-6 and projection_error<1e-6,'policy/execution mismatch')
    solver=readc(path/'solver_log.csv')
    for sr in solver:
        if sr['max_violation'] and float(sr['max_violation'])>1e-6:candidate_violations.append({'date':sr['date'],'stage':sr['stage'],'violation':float(sr['max_violation']),'guard_action':sr.get('guard_action'),'fallback':sr['fallback']})
    idx=np.arange(n)>=31*144
    def summ(mask):return {'cost':float(total[mask].sum()),'planned':float(pg[mask].sum()),'adjust':float(adj[mask].sum()),'emergency_cost':float(ec[mask].sum()),'emergency_kwh':float(e[mask].sum()),'S_start':float(s0[mask][0]),'S_end':float(s1[mask][-1])} if np.any(mask) else None
    if (path/'ledger_submission.csv').exists():require(readc(path/'ledger_submission.csv')==ledger[31*144:],'submission exact slice')
    excel_cells=0
    if (path/'result3.xlsx').exists():
        book=rows(path/'result3.xlsx'); require(list(book)==['计划购电量','调整购电量','充放电量','紧急购电量'],'sheet order')
        for name,arr,cost in [('计划购电量',g,pg),('调整购电量',a,total)]:
            rr=book[name];require(len(rr)==335 and len(rr[0])==147,'plan dimensions')
            for j,line in enumerate(rr[1:]):
                di=j+31;ix=slice(di*144,(di+1)*144)
                require(day(line[0])==str(dt.date(2025,1,1)+dt.timedelta(days=di)),'Excel plan dates')
                require(maxabs(np.array(line[1:145])-arr[ix])<1e-6 and abs(line[145]-arr[ix].sum())<1e-6 and abs(line[146]-cost[ix].sum())<1e-6,'Excel plan numeric values')
                excel_cells+=146
        sr=book['充放电量'][1:];require(len(sr)==2004,'Excel storage length')
        for j,line in enumerate(sr):
            di=31+j//6;b=j%6;ix=slice(di*144+b*24,di*144+(b+1)*24)
            require(abs(line[2]-c[ix].sum())<1e-6 and abs(line[3]-d[ix].sum())<1e-6,'Excel storage')
            if b==0:require(abs(line[5]-s0[di*144])<1e-6,'Excel start SOC')
            if b==1:require(abs(line[5]-s1[(di+1)*144-1])<1e-6,'Excel end SOC')
            excel_cells+=2+(b<2)
        exevents=[];cur=None
        for date,interval,q in book['紧急购电量'][1:]:
            if date is not None:cur=day(date)
            if q:exevents.append((cur,interval,float(q)))
        actualevents=[x for x in efull if x[0]>='2025-02-01'];require(len(exevents)==len(actualevents),'Excel event count')
        def label(k):return f'{k//6:02d}:{(k%6)*10:02d}'
        for ex,ac in zip(exevents,actualevents):require(ex[0]==ac[0] and ex[1]==label(ac[1]-1)+'-'+label(ac[2]) and abs(ex[2]-ac[3])<1e-6,'Excel event')
        excel_cells+=len(exevents)
    return {'status':'passed_ledger_and_saved_execution','files_hash_checked':checked,'slots':n,'source_commit':meta['source_git_commit'],'source_dirty':meta['source_dirty'],
      'excel_numeric_cells_checked':excel_cells,'forecasts_reconstructed_independently':True,
      'residual_max':residuals,'policy_raw_max_difference':policy_error,'physical_projection_max_difference':projection_error,'full_period':summ(np.ones(n,bool)),'submission':summ(idx),
      'submission_guard_actions':{f'{k[0]} {k[1]}':v for k,v in actions.items()},'candidate_violations_above_1e_minus6':candidate_violations,
      'tail_mode_violation_sum_reported':sum(int(x.get('tail_mode_violations') or 0) for x in solver),
      'solver_fallbacks':[{'date':x['date'],'stage':x['stage'],'message':x['message']} for x in solver if x['fallback']=='True'],
      'limits':'Does not establish optimality or rerun every MILP/guard tail; checks saved policy execution and information timestamps/source dates.'}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--archives',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();mf=readj(a.manifest);report={}
    for name,rec in mf['runs'].items():
        try: report[name]=audit_run(a.archives/name,a.repo/'data/raw',rec)
        except Exception as exc:report[name]={'status':'failed','error':str(exc)}
        a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(name,report[name].get('status'),report[name].get('error',''),flush=True)
