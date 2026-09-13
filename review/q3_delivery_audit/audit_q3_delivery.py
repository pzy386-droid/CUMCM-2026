"""Independent read-only audit of delivered workbook and raw inputs; no production imports."""
import argparse, datetime as dt, hashlib, json, math, re
from pathlib import Path
import numpy as np
from openpyxl import load_workbook

def rows(path):
    w=load_workbook(path,read_only=True,data_only=False)
    out={s.title:list(s.values) for s in w}; w.close(); return out
def day(x):
    if isinstance(x,dt.datetime): return x.date().isoformat()
    return dt.date(*map(int,str(x)[:10].split('-'))).isoformat()
def hh(m): return f'{m//60:02d}:{m%60:02d}'
def run(repo, delivery):
    raw=repo/'data/raw'; templates=repo/'data/templates'
    scans=[]
    for path in sorted(raw.glob('*.xlsx'))+sorted(templates.glob('*.xlsx')):
        sheets=rows(path)
        scans.append({'path':str(path.relative_to(repo)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'sheets':[
            {'name':n,'rows':len(rr),'columns':max(map(len,rr)),
             'nonempty':sum(x is not None and x!='' for r in rr for x in r),
             'nonfinite':sum(isinstance(x,(int,float)) and not math.isfinite(x) for r in rr for x in r)} for n,rr in sheets.items()]})
    p=np.array([r[1] for r in next(iter(rows(raw/'附件1.xlsx').values()))[1:]],float)
    actual=rows(raw/'附件2.xlsx')
    L=np.array([r[1:] for r in actual['小区负载'][1:]],float)
    V=np.array([r[1:] for r in actual['光伏发电实际功率'][1:]],float)
    wb=rows(delivery/'result3.xlsx')
    assert list(wb)==['计划购电量','调整购电量','充放电量','紧急购电量']
    expected=[(dt.date(2025,2,1)+dt.timedelta(days=i)).isoformat() for i in range(334)]
    headers=[hh(k*10)+'-'+hh((k+1)*10) for k in range(144)]
    for name in ['计划购电量','调整购电量']:
        rr=wb[name]; assert len(rr)==335 and all(len(r)==147 for r in rr)
        assert [day(r[0]) for r in rr[1:]]==expected
        assert list(rr[0][1:145])==headers
    g=np.array([r[1:145] for r in wb['计划购电量'][1:]],float)
    a=np.array([r[1:145] for r in wb['调整购电量'][1:]],float)
    fees=np.array([r[146] for r in wb['调整购电量'][1:]],float)
    pg=g@p; adj=np.maximum(a-g,0)@(1.5*p)+np.maximum(g-a,0)@(.5*p)
    checks={
      'min_contract':float(min(g.min(),a.min())), 'max_decrease_kwh':float(np.maximum(g-a,0).max()),
      'first_six_hours_max_change':float(abs(a[:,:36]-g[:,:36]).max()),
      'max_plan_fee_error_yuan':float(abs(pg-np.array([r[146] for r in wb['计划购电量'][1:]])).max()),
      'max_g_total_error':float(abs(g.sum(1)-np.array([r[145] for r in wb['计划购电量'][1:]])).max()),
      'max_a_total_error':float(abs(a.sum(1)-np.array([r[145] for r in wb['调整购电量'][1:]])).max())}
    assert len(wb['充放电量'])==2005
    sr=wb['充放电量'][1:]; c=np.array([r[2] for r in sr],float).reshape(334,6); d=np.array([r[3] for r in sr],float).reshape(334,6)
    starts=np.array([sr[i*6][5] for i in range(334)],float)
    ends=np.array([sr[i*6+1][5] for i in range(334)],float)
    assert [day(sr[i*6][0]) for i in range(334)]==expected
    checks.update(max_daily_SOC_residual_kwh=float(abs(ends-starts-.9*c.sum(1)+d.sum(1)/.9).max()),
        max_cross_day_SOC_residual_kwh=float(abs(starts[1:]-ends[:-1]).max()),
        min_endpoint_SOC_kwh=float(min(starts.min(),ends.min())),max_endpoint_SOC_kwh=float(max(starts.max(),ends.max())),
        max_four_hour_charge_kwh=float(c.max()),max_four_hour_discharge_kwh=float(d.max()))
    e=np.zeros(334); lo=np.zeros(334); hi=np.zeros(334); occupied=np.zeros((334,144),bool); event_count=0
    cur=None
    for date,interval,quantity in wb['紧急购电量'][1:]:
        if date is not None: cur=day(date)
        ix=expected.index(cur); q=float(quantity)
        if q==0: continue
        nums=list(map(int,re.findall(r'\d+',interval))); assert len(nums)==4
        left,right=nums[0]*6+nums[1]//10,nums[2]*6+nums[3]//10
        assert 0<=left<right<=144 and not occupied[ix,left:right].any() and q>0
        occupied[ix,left:right]=True; e[ix]+=q; event_count+=1
        lo[ix]+=5*p[left:right].min()*q; hi[ix]+=5*p[left:right].max()*q
    inferred_emergency=fees-pg-adj
    checks['emergency_fee_within_event_price_bounds']=bool(np.all(inferred_emergency>=lo-1e-6) and np.all(inferred_emergency<=hi+1e-6))
    spill=a.sum(1)+e+V[31:].sum(1)/6+d.sum(1)-L[31:].sum(1)/6-c.sum(1)
    checks['min_inferred_daily_spill_kwh']=float(spill.min())
    totals={'total_cost_yuan':float(fees.sum()),'planned_cost_yuan':float(pg.sum()),'adjustment_cost_yuan':float(adj.sum()),
      'emergency_cost_yuan_inferred_from_total':float(inferred_emergency.sum()),'emergency_kwh':float(e.sum()),
      'g0_kwh':float(g.sum()),'effective_contract_kwh':float(a.sum()),'increase_kwh':float(np.maximum(a-g,0).sum()),
      'charge_kwh':float(c.sum()),'discharge_kwh':float(d.sum()),'spill_kwh_inferred':float(spill.sum()),
      'SOC_start':float(starts[0]),'SOC_end':float(ends[-1]),'events':event_count}
    # Independent reconstruction of forecast curves at right-end labels.
    fr=next(iter(rows(raw/'附件3.xlsx').values()))[1:]
    curves={}; cur=None
    for rr in fr:
        if rr[0] not in (None,''): cur=day(rr[0])
        tau=rr[1].hour if hasattr(rr[1],'hour') else int(str(rr[1]).split(':')[0])
        di=(dt.date.fromisoformat(cur)-dt.date(2025,1,1)).days
        anchor=V[di,6*tau-1] if tau else (V[di-1,-1] if di else float(rr[2]))
        cc=np.interp(np.arange(1,145)/6,np.arange(25),np.r_[anchor,np.array(rr[2:26],float)])
        curves[(di,tau)]=cc
    rmse={}; mean_daily_rmse={}
    for left,right in [(36,72),(72,108),(108,144)]:
        label=f'{left//6:02d}-{right//6:02d}'
        rmse[label]={'persistence_lag1':float(np.sqrt(np.mean((V[30:364,left:right]-V[31:,left:right])**2)))}
        mean_daily_rmse[label]={'persistence_lag1':float(np.sqrt(np.mean((V[30:364,left:right]-V[31:,left:right])**2,axis=1)).mean())}
        for tau in (0,6,12,18):
            if 6*tau>left: continue
            err=np.stack([curves[(di,tau)][left-6*tau:right-6*tau]-V[di,left:right] for di in range(31,365)])
            rmse[label]['vintage_'+str(tau)]=float(np.sqrt(np.mean(err**2)))
            mean_daily_rmse[label]['vintage_'+str(tau)]=float(np.sqrt(np.mean(err**2,axis=1)).mean())
    claimed=json.loads((delivery/'forecast_vintage_errors.json').read_text(encoding='utf-8'))['block_rmse_kw']
    rmse_error=max(abs(v-claimed[b][k]) for b,m in rmse.items() for k,v in m.items())
    return {'scope':'Independent raw-cell scan and workbook aggregation; NOT a full ledger/causality acceptance.',
      'workbook_sha256':hashlib.sha256((delivery/'result3.xlsx').read_bytes()).hexdigest(),
      'raw_scan':scans,'checks':checks,'totals':totals,'forecast_rmse_kw':rmse,'mean_daily_forecast_rmse_kw':mean_daily_rmse,'max_forecast_report_difference':rmse_error,
      'PV_after_18_kwh_submission':float(V[31:,108:].sum()/6),'PV_after_18_max_kw':float(V[31:,108:].max()),
      'specified_day_total_costs':{x:float(fees[expected.index(x)]) for x in ['2025-03-20','2025-06-21','2025-09-23','2025-12-21']},
      'unverified':['per-slot SOC, modes and emergency cost','ledger-to-input exact binding','January continuation','policy/contract snapshots and guard scores','run/source provenance beyond supplied manifest']}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--delivery',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    result=run(a.repo,a.delivery);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='raw_scan'},ensure_ascii=False,indent=2))
