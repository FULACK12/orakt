"""Additive monetary flows only. Ratios, EPS and balances cannot be subtracted."""
from datetime import date,timedelta
from decimal import Decimal
from hashlib import sha256

ALLOWED={'RevenueFromContractWithCustomerExcludingAssessedTax','OperatingIncomeLoss','NetIncomeLoss'}

def derive(annual,ytd,*,cutoff,issuer,reviewed_basis=False):
 if not reviewed_basis:raise ValueError('Cross-filing accounting basis must be reviewed')
 if issuer!=annual.get('issuer') or issuer!=ytd.get('issuer'):raise ValueError('Issuer mismatch')
 if annual['concept'] not in ALLOWED or annual['concept']!=ytd['concept'] or annual.get('dimensions') or ytd.get('dimensions'):raise ValueError('Only matching consolidated additive flows supported')
 if annual['unit']!=ytd['unit'] or annual['unit']!='USD':raise ValueError('Unit mismatch')
 if annual['period_start']!=ytd['period_start'] or max(annual['filed_at'],ytd['filed_at'])>cutoff:raise ValueError('Fiscal start or release cutoff mismatch')
 start=date.fromisoformat(annual['period_start']);end=date.fromisoformat(annual['period_end']);mid=date.fromisoformat(ytd['period_end'])
 if not (345<=(end-start).days+1<=385 and 250<=(mid-start).days+1<=295 and 70<=(end-mid).days<=110) or end>date.fromisoformat(cutoff):raise ValueError('Annual/YTD periods do not form one quarter')
 values=[Decimal(str(f['value'])) for f in [annual,ytd]]
 if not all(v.is_finite() for v in values):raise ValueError('Invalid number')
 identity='|'.join([issuer,annual['concept'],str(end),annual['source_url'],ytd['source_url']])
 return {'evidence_id':'DERIVED:'+sha256(identity.encode()).hexdigest()[:16],'concept':annual['concept'],'unit':'USD','value':str(values[0]-values[1]),'period_start':str(mid+timedelta(days=1)),'period_end':str(end),'filed_at':max(annual['filed_at'],ytd['filed_at']),'source_url':annual['source_url'],'derivation':{'method':'annual_minus_nine_months','accountingBasis':'reviewed_consolidated_US_GAAP','operands':[annual,ytd]},'issuer':issuer}
