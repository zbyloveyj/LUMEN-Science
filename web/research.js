import {state,$,esc,icon,api,button,heading,empty,on,toast,refreshFiles,dataOptions,bytes,dialog,outputs,watchRun,showPanel,fmtDate,fileURL,status} from './core.js';

let selectedData='', literatureResults=null;

function table(columns,rows){
  return '<div class="table-scroll"><table><thead><tr>'+columns.map(c=>'<th>'+esc(c)+'</th>').join('')+'</tr></thead><tbody>'+
    rows.map(row=>'<tr>'+row.map(value=>'<td>'+esc(value===null||value===undefined?'—':value)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';
}
export async function dataView(){
  await refreshFiles();
  const files=state.files.filter(f=>['.csv','.tsv','.xlsx','.xls','.parquet'].includes(f.extension));
  if(!files.some(f=>f.path===selectedData))selectedData=files[0]?.path||'';
  return heading('DATA / EXPLORER','先认识数据，再开始分析','结构、缺失与分布一眼可查。导入操作只新增文件。',
      button('导入数据','import-data','primary','','upload'))+
    '<div class="data-layout"><aside class="panel data-files"><div class="panel-title">项目数据 <span class="count">'+files.length+'</span></div>'+
    (files.length?files.map(f=>'<button class="data-file '+(selectedData===f.path?'selected':'')+'" data-action="select-data" data-path="'+esc(f.path)+'">'+icon('database')+'<span><strong>'+esc(f.name)+'</strong><small>'+bytes(f.bytes)+'</small></span></button>').join(''):empty('还没有数据','导入 CSV、Excel 或 Parquet 文件。'))+
    '</aside><section id="data-detail">'+(selectedData?await dataDetail(selectedData):empty('准备好你的研究数据','支持不超过32 MiB的交互预览，大文件可在 Notebook 中分块处理。'))+'</section></div>';
}
async function dataDetail(path,sheet){
  const data=await api('data.preview',{project_id:state.project.id,path,sheet});
  const totalMissing=data.columns.reduce((s,c)=>s+c.missing,0);
  return '<div class="panel data-summary"><div class="row"><div><h2>'+esc(path.split('/').pop())+'</h2><p class="muted mono">'+esc(data.identity.sha256.slice(0,24))+'…</p></div><span class="push"></span>'+button('用此数据分析','data-workflow','primary','data-path="'+esc(path)+'"','workflow')+'</div><div class="stats-row"><div><strong>'+data.rows.toLocaleString()+'</strong><span>观测行</span></div><div><strong>'+data.columns.length+'</strong><span>变量</span></div><div><strong>'+totalMissing+'</strong><span>缺失单元格</span></div><div><strong>'+data.duplicate_rows+'</strong><span>重复行</span></div></div>'+
    (data.sheets.length?'<label class="inline-label">工作表<select id="sheet-select" data-path="'+esc(path)+'">'+data.sheets.map(s=>'<option '+(s===sheet?'selected':'')+'>'+esc(s)+'</option>').join('')+'</select></label>':'')+'</div>'+
    '<div class="panel"><div class="panel-title">变量质量概览 <span class="muted">缺失仅标记，未修改数据</span></div><div class="table-scroll"><table><thead><tr><th>变量</th><th>类型</th><th>缺失率</th><th>唯一值</th><th>数值范围</th></tr></thead><tbody>'+
    data.columns.map(c=>'<tr><td class="strong">'+esc(c.name)+'</td><td><code>'+esc(c.dtype)+'</code></td><td><span class="missing-bar"><i style="width:'+Math.max(2,c.missing_percent)+'%"></i></span><span class="'+(c.missing_percent>20?'warning-text':'')+'">'+c.missing_percent+'%</span></td><td>'+c.unique+'</td><td>'+esc(c.min!==undefined?String(c.min??'—')+' — '+String(c.max??'—'):'—')+'</td></tr>').join('')+
    '</tbody></table></div></div><div class="panel"><div class="panel-title">数据预览 <span class="muted">前 '+data.preview.length+' 行</span></div>'+
    table(data.columns.map(c=>c.name),data.preview.map(row=>data.columns.map(c=>row[c.name])))+'</div>';
}
on('select-data',async b=>{
  selectedData=b.dataset.path;$('#data-detail').innerHTML='<div class="loading">正在检查数据…</div>';
  $('#data-detail').innerHTML=await dataDetail(selectedData);
  document.querySelectorAll('.data-file').forEach(n=>n.classList.toggle('selected',n.dataset.path===selectedData));
});
document.addEventListener('change',async e=>{
  if(e.target.id==='sheet-select'){
    try{$('#data-detail').innerHTML=await dataDetail(e.target.dataset.path,e.target.value);}catch(error){toast(error.message,true);}
  }
});
document.addEventListener('open-data',e=>{
  selectedData=e.detail;document.dispatchEvent(new CustomEvent('navigate',{detail:'data'}));
});
on('data-workflow',b=>{selectedData=b.dataset.path;document.dispatchEvent(new CustomEvent('navigate',{detail:'workflows'}));});
on('import-data',()=>{
  const input=document.createElement('input');input.type='file';input.multiple=true;
  input.accept='.csv,.tsv,.xlsx,.xls,.parquet,.json,.txt,.md,.pdf,.py,.R,.r';
  input.addEventListener('change',async()=>{
    try{
      for(const file of input.files){
        if(file.size>32*1024*1024)throw Error(file.name+' 超过32 MiB，请在 Notebook 中处理。');
        const content=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});
        await api('files.import',{project_id:state.project.id,name:file.name,content});
      }
      toast('文件已导入项目 data 目录');await refreshFiles();
      document.dispatchEvent(new CustomEvent('navigate',{detail:state.view}));
    }catch(error){toast(error.message,true);}
  });input.click();
});

export async function workflows(){
  await refreshFiles();
  const pipelines=await api('pipeline.list',{project_id:state.project.id});
  return heading('WORKFLOWS / RESEARCH','让分析步骤，可以重复使用','四个本地分析流程可离线运行；Notebook 可保存为自定义多步流程。')+
    '<div class="section-label">内置分析流程 <span>独立进程 · 自包含脚本 · 明确输入输出</span></div><div class="workflow-grid">'+state.boot.templates.map((t,i)=>
    '<article class="panel workflow-card"><div class="row"><span class="workflow-icon tone-'+i+'">'+icon(['database','layers','link','workflow'][i],24)+'</span><span class="push"></span><span class="tag">'+esc(t.tag)+'</span></div><small class="eyebrow">'+esc(t.category)+'</small><h2>'+esc(t.name)+'</h2><p>'+esc(t.description)+'</p><button class="text-button" data-action="start-workflow" data-id="'+t.id+'">选择数据并运行 '+icon('arrow',16)+'</button></article>').join('')+
    '</div><div id="workflow-progress"></div><div class="section-label">我的分析流程 <span>按照单元顺序运行，遇到错误立即停止</span></div>'+
    (pipelines.length?'<div class="panel">'+pipelines.map(w=>'<div class="list-row"><span class="file-icon">'+icon('workflow')+'</span><div><strong>'+esc(w.name)+'</strong><small>'+JSON.parse(w.content).length+' 个步骤 · '+fmtDate(w.created)+'</small></div><span class="push"></span>'+button('运行流程','run-pipeline','secondary','data-id="'+w.id+'"','play')+'</div>').join('')+'</div>':
      '<div class="panel compact-empty">'+empty('把你的方法保存下来','在 Notebook 编辑好代码，点击“保存为流程”，以后可以再次执行。',button('前往 Notebook','nav','secondary','data-view="notebook"','terminal'))+'</div>');
}
on('start-workflow',async b=>{
  if(!dataOptions())throw Error('请先导入表格数据');
  const template=state.boot.templates.find(t=>t.id===b.dataset.id);
  let form=await dialog(template.name,'<label>输入表格<select name="path">'+dataOptions(selectedData)+'</select></label><p class="muted">会生成可复用脚本、结果文件与分析说明，保留原始数据。</p>','下一步');
  if(!form)return;
  let parameters={};
  if(template.parameters.length){
    const preview=await api('data.preview',{project_id:state.project.id,path:form.path});
    const all=preview.columns.map(c=>'<option value="'+esc(c.name)+'">'+esc(c.name)+'</option>').join('');
    const numeric=preview.columns.filter(c=>c.min!==undefined).map(c=>'<option value="'+esc(c.name)+'">'+esc(c.name)+'</option>').join('');
    if(template.id==='group'){
      const params=await dialog('两组独立样本比较','<label>分组变量<select name="group">'+all+'</select></label><label>数值变量<select name="value">'+numeric+'</select></label><label>检验方法<select name="method"><option value="welch">Welch 独立样本 t 检验</option><option value="mannwhitney">Mann–Whitney U 检验</option></select></label><p class="muted">仅适用于两组独立观测；配对、重复测量或聚类数据需另行建模。</p>','运行分析');
      if(!params)return;parameters=params;
    }else{
      const params=await dialog('多元线性回归','<label>数值结局<select name="target">'+numeric+'</select></label><label>数值自变量（英文逗号分隔）<input name="predictors" required placeholder="age,marker_a"></label><p class="muted">不自动编码分类变量；请按研究设计指定自变量。</p>','运行分析');
      if(!params)return;parameters={target:params.target,predictors:params.predictors.split(/[,，]/).map(s=>s.trim()).filter(Boolean)};
    }
  }
  const run=await api('workflow.run',{project_id:state.project.id,session_id:state.session.id,
    template_id:template.id,path:form.path,parameters});
  toast('已开始 '+template.name);
  await watchRun(run.id,r=>{
    const panel=$('#workflow-progress');if(panel)panel.innerHTML='<div class="panel"><div class="panel-title">'+esc(template.name)+(r.status==='running'?button('停止','cancel-run','secondary','data-id="'+r.id+'"','stop'):'')+'</div>'+outputs(r)+'</div>';
  });
  await refreshFiles();
});
on('run-pipeline',async b=>{
  const job=await api('pipeline.start',{project_id:state.project.id,session_id:state.session.id,workflow_id:b.dataset.id});
  b.disabled=true;
  try{
    for(;;){
      const current=await api('pipeline.status',{job_id:job.id});
      const panel=$('#workflow-progress');
      if(panel)panel.innerHTML='<div class="panel"><div class="panel-title">自定义流程 '+status(current.status)+'</div>'+
        current.steps.map((s,i)=>'<div class="list-row"><span class="step-number">'+(i+1)+'</span><strong>'+esc(s.title)+'</strong><span class="mono muted">'+s.run_id+'</span></div>').join('')+
        (current.error?'<p class="output-error">'+esc(current.error)+'</p>':'')+
        (current.status==='running'?button('停止流程','cancel-pipeline','secondary','data-id="'+job.id+'"','stop'):'')+'</div>';
      if(current.status!=='running'){toast(current.status==='success'?'流程全部执行完成':current.error||'流程已停止',current.status==='failed');break;}
      await new Promise(r=>setTimeout(r,850));
    }
  }finally{b.disabled=false;}
});
on('cancel-pipeline',async b=>{await api('pipeline.cancel',{job_id:b.dataset.id});toast('已请求停止流程');});

function referenceCard(record,index,saved=false){
  const href=/^https?:\/\//.test(record.url)?record.url:'#';
  return '<article class="reference-card"><div class="reference-number">'+String(index+1).padStart(2,'0')+'</div><div class="reference-main"><div class="row"><span class="tag">'+esc(record.source)+'</span><span class="muted">'+esc(record.year||'年份未提供')+'</span></div><h3><a href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">'+esc(record.title)+'</a></h3><p>'+esc((record.authors||[]).slice(0,4).join(', '))+'</p><small>'+esc(record.journal)+' · '+esc(record.doi)+'</small>'+(record.abstract?'<details><summary>查看返回的摘要</summary><p>'+esc(record.abstract)+'</p></details>':'')+'</div>'+
    (!saved?button('保存','save-reference','secondary','data-index="'+index+'"','plus'):'<span class="badge success">已入库</span>')+'</article>';
}
export async function library(){
  const saved=await api('literature.list',{project_id:state.project.id});
  return heading('LITERATURE / EVIDENCE','每一条引用，都有真实来源','检索 Crossref 与 PubMed 元数据，保存研究文献，导出 BibTeX。',
    button('导出文献','export-references','secondary','','download'))+
    '<section class="panel literature-search"><div class="search-input">'+icon('search',21)+'<input id="literature-query" placeholder="输入研究主题、论文标题或 DOI" aria-label="文献检索词"></div><select id="literature-source" aria-label="检索来源"><option value="crossref">Crossref</option><option value="pubmed">PubMed</option></select>'+button('检索文献','search-literature','primary')+'</section>'+
    '<div class="note-inline">'+icon('info')+'仅发送你输入的检索词。数据库元数据及摘要不等于已阅读或核验论文全文。</div><div id="literature-results"></div>'+
    '<div class="section-label">项目文献库 <span>'+saved.length+' 条已保存记录</span></div><div class="panel" id="saved-references">'+
    (saved.length?saved.map((r,i)=>referenceCard(r,i,true)).join(''):empty('建立你的证据库','检索后保存需要的文献，引用信息会随项目保留。'))+'</div>';
}
on('search-literature',async b=>{
  const query=$('#literature-query').value.trim();if(!query)throw Error('请输入检索词');
  b.disabled=true;const results=$('#literature-results');results.innerHTML='<div class="loading">正在查询真实文献来源…</div>';
  try{
    literatureResults=await api('literature.search',{project_id:state.project.id,query,source:$('#literature-source').value,limit:10});
    results.innerHTML='<div class="section-label">检索结果 <span>'+literatureResults.records.length+' 条</span></div><div class="panel">'+
      (literatureResults.records.length?literatureResults.records.map((r,i)=>referenceCard(r,i)).join(''):empty('没有匹配记录','尝试修改关键词或切换检索来源。'))+'</div>';
  }catch(error){results.innerHTML='<div class="panel">'+empty('本次检索未完成',error.message)+'</div>';throw error;}finally{b.disabled=false;}
});
on('save-reference',async b=>{
  await api('literature.save',{project_id:state.project.id,search_id:literatureResults.search_id,index:Number(b.dataset.index)});
  b.textContent='已保存';b.disabled=true;toast('文献已保存到当前项目');
});
on('export-references',async()=>{
  const file=await api('literature.export',{project_id:state.project.id});
  window.open(fileURL(file.path,true),'_blank','noopener');toast('BibTeX 文献文件已生成');
});
