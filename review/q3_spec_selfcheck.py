"""Check the hand-calculated specification examples, without a production Q3 model."""
import datetime as dt
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    path = root / 'review/q3_contract_cases.json'
    examples = json.loads(path.read_text(encoding='utf-8'))
    n = 0
    for c in examples['cases']:
        total = c['p']*(c['g']+1.5*max(c['a']-c['g'],0)+c['kappa']*max(c['g']-c['a'],0)+5*c['e'])
        assert abs(total-c['expected_cost']) < 1e-10, c['name']
        n += 1
    for name in ['revision_case','freeze_case']:
        c=examples[name]
        versions=[v for v in c['versions'] if v['issue_hour']<=c['delivery_hour']]
        effective=versions[-1]['a'] if versions else c['g']
        assert effective==c['expected_effective_a']
        cost=c['p']*(c['g']+1.5*max(effective-c['g'],0)+c['kappa']*max(c['g']-effective,0)+5*c['e'])
        assert abs(cost-c['expected_cost'])<1e-10
        n+=1
    for c in examples['timestamps']:
        target=dt.datetime.fromisoformat(c['issued_at'])+dt.timedelta(hours=c['lead_hour'])
        assert target.isoformat()==c['expected_valid_at']
        n+=1
    for hour,slot in examples['first_adjustable_slots_1based'].items():
        assert int(hour)*6+1==slot
        n+=1
    c=examples['interpolation_case']
    power=c['anchor_kw']+(c['next_hour_kw']-c['anchor_kw'])*c['minutes_after_issue']/60
    assert abs(power-c['expected_power_kw'])<1e-10
    assert abs(power/6-c['expected_energy_kwh'])<1e-10
    n+=1
    report=dict(status='passed',checks=n,scope='Specification arithmetic/time examples only; Q3 production implementation does not yet exist.',
                cases_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    out=root/'reports/q3/spec_selfcheck.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
