from __future__ import annotations

from textwrap import dedent
from .store import uid

TEMPLATES = [
    {"id": "quality", "name": "数据质量体检", "category": "数据准备", "tag": "无需 AI",
     "description": "缺失、重复、类型、数值分布；导出质量表、分布图与检查说明。", "parameters": []},
    {"id": "group", "name": "两组独立样本比较", "category": "统计分析", "tag": "Welch / U 检验",
     "description": "明确两组样本量、效应方向、实际检验方法和适用前提。", "parameters": ["group", "value"]},
    {"id": "correlation", "name": "相关性分析", "category": "统计分析", "tag": "Spearman + FDR",
     "description": "逐对完整观测、相关系数、样本数及 BH 校正结果。", "parameters": []},
    {"id": "regression", "name": "多元线性回归", "category": "统计建模", "tag": "OLS",
     "description": "显式选择结局和数值自变量，输出系数、区间与残差图。", "parameters": ["target", "predictors"]},
]

PREAMBLE = """
from pathlib import Path
import json, sys, platform, importlib.metadata
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats
root = Path.cwd()
source = root / INPUT_PATH
out = root / OUTPUT_PATH
out.mkdir(parents=True, exist_ok=False)
if source.suffix.lower() in ['.xlsx', '.xls']:
    df = pd.read_excel(source, sheet_name=SHEET if SHEET else 0)
elif source.suffix.lower() == '.parquet':
    df = pd.read_parquet(source)
else:
    try:
        df = pd.read_csv(source, sep='\\t' if source.suffix.lower()=='.tsv' else ',', encoding='utf-8-sig')
    except UnicodeDecodeError:
        df = pd.read_csv(source, sep='\\t' if source.suffix.lower()=='.tsv' else ',', encoding='gb18030')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                    'axes.spines.right':False,'figure.dpi':140,'savefig.bbox':'tight'})
summary = {'source':INPUT_PATH,'rows':len(df),'columns':len(df.columns),'workflow':WORKFLOW_ID}
notes = []
"""

QUALITY = """
quality = pd.DataFrame({'column':df.columns.astype(str),'dtype':df.dtypes.astype(str).values,
    'missing':df.isna().sum().values,'missing_percent':(df.isna().mean()*100).round(3).values,
    'unique':df.nunique().values})
quality.to_csv(out/'data_quality.csv',index=False,encoding='utf-8-sig')
numeric = df.select_dtypes(include=np.number).replace([np.inf,-np.inf],np.nan)
numeric.describe().to_csv(out/'numeric_summary.csv',encoding='utf-8-sig') if len(numeric.columns) else None
summary.update({'duplicate_rows':int(df.duplicated().sum()),'missing_cells':int(df.isna().sum().sum()),
                'numeric_columns':list(numeric.columns.astype(str))})
fig,ax = plt.subplots(figsize=(8,4))
missing = quality.sort_values('missing_percent',ascending=False).head(16)
ax.barh(missing['column'].astype(str),missing['missing_percent'],color='#25847e')
ax.set_xlabel('Missing observations (%)');ax.invert_yaxis()
fig.savefig(out/'missingness.png');plt.close(fig)
if len(numeric.columns):
    numeric.iloc[:,:9].hist(figsize=(10,7),bins=18,color='#5386bd',edgecolor='white')
    plt.tight_layout();plt.savefig(out/'distributions.png');plt.close('all')
notes += ['缺失值仅统计，未填补；重复行仅标记，未删除。','分布图最多展示前9个数值变量。']
"""

GROUP = """
group_column, value_column = PARAMETERS['group'], PARAMETERS['value']
if group_column not in df or value_column not in df:
    raise ValueError('分组列或数值列不存在')
work = df[[group_column,value_column]].copy()
work[value_column] = pd.to_numeric(work[value_column],errors='coerce').replace([np.inf,-np.inf],np.nan)
work = work.dropna()
groups = list(work[group_column].unique())
if len(groups)!=2:
    raise ValueError('此流程仅适用于两组独立样本；当前有效分组数为 '+str(len(groups)))
a,b = [work.loc[work[group_column]==g,value_column].to_numpy(dtype=float) for g in groups]
if min(len(a),len(b))<3:
    raise ValueError('每组至少需要3个有效观测')
if PARAMETERS.get('method')=='mannwhitney':
    test = stats.mannwhitneyu(a,b,alternative='two-sided')
    method = 'Mann-Whitney U, two-sided'
else:
    test = stats.ttest_ind(a,b,equal_var=False)
    method = 'Welch independent t-test, two-sided'
if not np.isfinite(test.pvalue):
    raise ValueError('无法得到有效p值，请检查常数列或数据分布')
result = {'method':method,'group_a':str(groups[0]),'group_b':str(groups[1]),
    'n_a':len(a),'n_b':len(b),'mean_a':float(a.mean()),'mean_b':float(b.mean()),
    'mean_difference_a_minus_b':float(a.mean()-b.mean()),
    'statistic':float(test.statistic),'p_value':float(test.pvalue),'excluded_rows':int(len(df)-len(work))}
pd.DataFrame([result]).to_csv(out/'group_comparison.csv',index=False,encoding='utf-8-sig')
fig,ax = plt.subplots(figsize=(6,4))
rng = np.random.default_rng(2026)
for i,(g,values) in enumerate(zip(groups,[a,b])):
    ax.scatter(i+rng.uniform(-.12,.12,len(values)),values,s=17,alpha=.65,color=['#25847e','#697fb5'][i])
    ax.plot([i-.16,i+.16],[np.median(values)]*2,color='#233344',lw=2)
ax.set_xticks([0,1],[str(g) for g in groups]);ax.set_ylabel(value_column)
fig.savefig(out/'group_comparison.png');plt.close(fig)
summary.update(result)
notes += ['适用前提：两组观测相互独立；配对、重复测量或聚类设计需另行建模。',
          '完整观测分析；未自动控制混杂因素。仅执行一次指定检验，未按显著性挑选方法。']
"""

CORRELATION = """
columns = df.select_dtypes(include=np.number).columns.tolist()
if len(columns)<2:
    raise ValueError('相关性分析至少需要两个数值变量')
columns = columns[:30]
rows = []
for i,x in enumerate(columns):
    for y in columns[i+1:]:
        pair=df[[x,y]].replace([np.inf,-np.inf],np.nan).dropna()
        if len(pair)<4 or pair[x].nunique()<2 or pair[y].nunique()<2:
            rows.append({'x':x,'y':y,'n':len(pair),'rho':None,'p_value':None,'status':'insufficient'})
            continue
        result=stats.spearmanr(pair[x],pair[y])
        rows.append({'x':x,'y':y,'n':len(pair),'rho':float(result.statistic),
                     'p_value':float(result.pvalue),'status':'ok'})
table=pd.DataFrame(rows)
valid=table['p_value'].notna()
p=table.loc[valid,'p_value'].to_numpy()
order=np.argsort(p)
adjusted=np.minimum.accumulate((p[order]*len(p)/np.arange(1,len(p)+1))[::-1])[::-1] if len(p) else np.array([])
restored=np.empty(len(p));restored[order]=np.minimum(adjusted,1)
table.loc[valid,'q_value_bh']=restored
table.to_csv(out/'correlations.csv',index=False,encoding='utf-8-sig')
matrix=df[columns].replace([np.inf,-np.inf],np.nan).corr(method='spearman')
fig,ax=plt.subplots(figsize=(max(6,len(columns)*.45),max(5,len(columns)*.4)))
im=ax.imshow(matrix,vmin=-1,vmax=1,cmap='RdBu_r')
ax.set_xticks(range(len(columns)),columns,rotation=60,ha='right')
ax.set_yticks(range(len(columns)),columns);fig.colorbar(im,ax=ax,label='Spearman rho')
fig.savefig(out/'correlation_matrix.png');plt.close(fig)
summary.update({'variables':columns,'tested_pairs':int(valid.sum()),'pairs_q_below_005':int((restored<.05).sum())})
notes += ['每对变量使用各自完整观测，样本量见结果表。','BH校正覆盖本次所有有效变量对。',
          '相关关系不能直接解释为因果；热图最多显示前30个数值变量。']
"""

REGRESSION = """
target=PARAMETERS['target']; predictors=PARAMETERS['predictors']
if not predictors or target in predictors or len(set(predictors))!=len(predictors):
    raise ValueError('请选择不重复且不包含结局的自变量')
for name in [target]+predictors:
    if name not in df or not pd.api.types.is_numeric_dtype(df[name]):
        raise ValueError('此流程要求明确的数值列；分类变量需先指定编码方式：'+str(name))
work=df[[target]+predictors].replace([np.inf,-np.inf],np.nan).dropna()
y=work[target].to_numpy(dtype=float)
X=np.column_stack([np.ones(len(work)),work[predictors].to_numpy(dtype=float)])
beta,residuals,rank,s=np.linalg.lstsq(X,y,rcond=None)
dof=len(y)-X.shape[1]
if dof<3 or rank<X.shape[1]:
    raise ValueError('有效样本不足或设计矩阵不满秩，请减少变量并检查共线性')
fitted=X@beta;error=y-fitted
sigma2=float(error@error/dof)
cov=sigma2*np.linalg.inv(X.T@X);se=np.sqrt(np.diag(cov))
tvalues=np.divide(beta,se,out=np.full_like(beta,np.nan),where=se>0)
pvalues=2*stats.t.sf(np.abs(tvalues),dof)
critical=stats.t.ppf(.975,dof)
result=pd.DataFrame({'term':['intercept']+predictors,'coefficient':beta,'std_error':se,
    'ci_lower':beta-critical*se,'ci_upper':beta+critical*se,'p_value':pvalues})
result.to_csv(out/'regression_coefficients.csv',index=False,encoding='utf-8-sig')
sst=float(((y-y.mean())**2).sum())
summary.update({'n_complete':len(y),'excluded_rows':int(len(df)-len(y)),
                'target':target,'predictors':predictors,'r_squared':1-float(error@error)/sst if sst else None,
                'residual_degrees_of_freedom':dof,'method':'ordinary least squares'})
pd.DataFrame({'observed':y,'fitted':fitted,'residual':error}).to_csv(out/'regression_predictions.csv',index=False)
fig,ax=plt.subplots(figsize=(6,4));ax.scatter(fitted,error,s=18,alpha=.7,color='#25847e')
ax.axhline(0,color='#697383',lw=1);ax.set_xlabel('Fitted value');ax.set_ylabel('Residual')
fig.savefig(out/'regression_diagnostics.png');plt.close(fig)
notes += ['普通最小二乘及经典标准误；未使用稳健、聚类或重复测量方差估计。',
          '完整观测分析；未自动选择自变量，需结合研究设计判断适用性。']
"""

ENDING = """
summary['notes']=notes
(out/'analysis_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
report='# 分析记录\\n\\n输入：'+INPUT_PATH+'\\n\\n流程：'+WORKFLOW_ID+'\\n\\n'
report+='## 实际计算摘要\\n\\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\\n\\n'
report+='## 输出文件\\n\\n'+'\\n'.join('- '+p.name for p in sorted(out.iterdir()) if p.is_file())+'\\n'
(out/'analysis_report.md').write_text(report,encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False))
print('结果目录：'+OUTPUT_PATH)
plt.close('all')
"""


def build_workflow(template_id, input_path, parameters=None, sheet=None):
    bodies = {"quality": QUALITY, "group": GROUP, "correlation": CORRELATION, "regression": REGRESSION}
    if template_id not in bodies:
        raise ValueError("未知分析流程")
    parameters = parameters or {}
    if template_id == "group" and not all(parameters.get(k) for k in ("group", "value")):
        raise ValueError("请选择分组列和数值列")
    if template_id == "regression" and (not parameters.get("target") or not isinstance(parameters.get("predictors"), list)):
        raise ValueError("请选择结局列和自变量")
    header = "\n".join(["# LUMEN Science: self-contained workflow",
                        "INPUT_PATH = " + repr(input_path),
                        "OUTPUT_PATH = " + repr("outputs/" + template_id + "-" + uid()),
                        "WORKFLOW_ID = " + repr(template_id),
                        "PARAMETERS = " + repr(parameters), "SHEET = " + repr(sheet)]) + "\n"
    return header + dedent(PREAMBLE) + dedent(bodies[template_id]) + dedent(ENDING)
