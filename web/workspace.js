import {state,$,esc,icon,api,button,heading,empty,on,toast,refreshFiles,bytes,dialog,showPanel,status,fmtDate,fileURL,markdown,outputs,readSession} from './core.js';

export async function overview(){
  await refreshFiles();
  const runs=await api('runs.list',{project_id:state.project.id});
  const data=state.files.filter(f=>['.csv','.xlsx','.tsv','.parquet'].includes(f.extension));
  const artifacts=state.files.filter(f=>f.path.startsWith('outputs/'));
  const successful=runs.filter(r=>r.status==='success').length;
  return '<div class="overview-intro"><div><div class="eyebrow">YOUR RESEARCH, CONNECTED</div><h1>让每一步研究，<br><span>都有据可查。</span></h1><p>从一个问题，到一份可核对的结果。<br>数据、计算、证据与成果，在同一处接续。</p><div class="hero-actions">'+
    button('开始一次分析','nav','primary','data-view="workflows"','arrow')+button('与 AI 讨论','nav','secondary','data-view="chat"','spark')+'</div></div>'+
    '<div class="research-map" aria-label="研究流程"><div class="map-top"><span class="map-label">RESEARCH GRAPH</span><span class="tag">本地项目</span></div><div class="map-row"><div class="map-node">'+icon('database',23)+'<strong>研究数据</strong><small>'+data.length+' 份表格</small></div><span class="map-line"></span><div class="map-node map-central">'+icon('spark',25)+'<strong>分析与计算</strong><small>'+successful+' 次成功运行</small></div><span class="map-line"></span><div class="map-node">'+icon('image',23)+'<strong>研究成果</strong><small>'+artifacts.length+' 份输出文件</small></div></div><div class="map-bottom">'+icon('link',14)+' 代码 · 输入指纹 · 环境 · 结果快照</div></div></div>'+
    '<div class="metric-grid">'+[
      ['项目文件',state.files.length,'本地组织，随时查看','folder'],
      ['研究数据',data.length,'支持 CSV / Excel / Parquet','database'],
      ['计算运行',runs.length,'含成功、失败与取消记录','terminal'],
      ['已完成',successful,'实际运行完成的任务','check']
    ].map(([label,n,sub,ic])=>'<div class="panel metric-card"><div class="row"><span>'+label+'</span>'+icon(ic)+'</div><strong>'+n+'</strong><small>'+sub+'</small></div>').join('')+'</div>'+
    '<div class="overview-grid"><section class="panel"><div class="panel-title">最近运行<button class="text-button" data-action="nav" data-view="artifacts">全部记录 '+icon('arrow',15)+'</button></div>'+
    (runs.length?runs.slice(0,5).map(run=>'<button class="list-row list-button" data-action="run-detail" data-id="'+run.id+'"><span class="file-icon">'+icon(run.kind==='workflow'?'workflow':'terminal')+'</span><span><strong>'+esc(run.title)+'</strong><small>'+fmtDate(run.created)+' · '+esc(run.language)+'</small></span><span class="push"></span>'+status(run.status)+'</button>').join(''):
      empty('从第一次运行开始','选择数据质量体检，体验一次完整的本地分析。',button('运行数据体检','quick-quality','secondary','','play')))+'</section>'+
    '<section class="panel project-card"><div class="panel-title">当前研究项目</div><span class="project-symbol">'+icon('folder',28)+'</span><h2>'+esc(state.project.name)+'</h2><p>'+esc(state.project.description||'为这个项目补充研究目标，从清晰的问题开始。')+'</p><div class="path-box">'+esc(state.project.path)+'</div><div class="row">'+button('导入文件','import-data','secondary','','upload')+button('整理交付','nav','secondary','data-view="reports"','download')+'</div></section></div>'+
    '<div class="local-footer">'+icon('info',16)+'示例项目使用合成数据。项目与计算在本机组织；使用在线 AI 时，对话及所调用工具结果会发送至你配置的模型服务。</div>';
}
on('quick-quality',()=>document.dispatchEvent(new CustomEvent('navigate',{detail:'workflows'})));

function messageHTML(message){
  const c=message.content;
  if(message.role==='notice')return '<div class="chat-notice">'+icon('info',15)+esc(c.text||'')+'</div>';
  if(message.role==='tool'){
    let result;try{result=JSON.parse(c.content);}catch{result={text:c.content};}
    return '<details class="tool-message"><summary>'+icon(result.error?'info':'check',15)+' 工具回执'+
      (result.run_id?' · '+esc(result.status):result.error?' · 未完成':'')+'</summary><pre>'+esc(JSON.stringify(result,null,2))+'</pre></details>';
  }
  if(message.role==='assistant'&&!c.content&&c.tool_calls?.length){
    return '<div class="tool-announcement">'+icon('workflow',15)+'准备调用：'+esc(c.tool_calls.map(t=>t.function.name).join('、'))+'</div>';
  }
  return '<article class="chat-message '+(message.role==='user'?'user':'assistant')+'"><div class="chat-avatar">'+(message.role==='user'?'你':icon('spark',18))+'</div><div class="message-main"><div class="message-author">'+(message.role==='user'?'你':'LUMEN')+'<span>'+fmtDate(message.created)+'</span></div><div class="markdown">'+markdown(c.content||'')+'</div></div></article>';
}
export async function chat(){
  await readSession();
  const draft=sessionStorage.getItem('lumen.draft.'+state.session.id)||'';
  return heading('AI / COLLABORATION','和研究助手，一起推进','先讨论方法，再核对计算。每次工具调用都有实际回执。',
    '<span class="connection-badge '+(state.boot.config.api_base?'':'offline')+'"><i></i>'+esc(state.boot.config.model||'模型待连接')+'</span>')+
    '<div class="chat-layout"><section class="panel chat-panel"><div id="transcript">'+
    (state.messages.length?state.messages.map(messageHTML).join(''):
      '<div class="chat-welcome"><span class="assistant-emblem">'+icon('spark',34)+'</span><h2>你的下一个研究问题是什么？</h2><p>可以讨论方法、检查脚本，也可以让助手读取项目数据。<br>本地分析流程无需配置 AI；协作对话需要连接模型服务。</p><div class="prompt-grid">'+
      ['先查看项目文件，说明这份数据可以怎样分析。','帮我梳理研究问题和分析方案，先不要运行代码。','检查现有分析脚本，找出可能影响复现的问题。'].map(t=>'<button class="prompt-card" data-action="prompt" data-text="'+esc(t)+'">'+esc(t)+icon('arrow',16)+'</button>').join('')+'</div></div>')+
    '</div><div id="agent-pending"></div><div class="chat-composer"><textarea id="chat-input" aria-label="发送给科研助手的消息" placeholder="描述你的研究问题，或说明你希望执行的分析…">'+esc(draft)+'</textarea><div class="composer-bottom"><select id="chat-mode" aria-label="协作模式"><option value="review">协作 · 运行前核对</option><option value="discuss">讨论 · 只读取</option></select><label class="checkbox-label"><input type="checkbox" id="chat-auto">本轮自动执行</label><span class="push"></span>'+button('发送','send-chat','primary','','arrow')+button('停止','stop-chat','secondary','','stop')+'</div></div></section>'+
    '<aside class="chat-aside"><div class="panel"><div class="panel-title">本次协作环境</div><div class="context-item">'+icon('folder')+'<span>'+esc(state.project.name)+'</span></div><div class="context-item">'+icon('terminal')+'<span>R / Python 持续内核</span></div><div class="context-item">'+icon('link')+'<span>代码与结果保留运行记录</span></div></div><div class="panel"><div class="panel-title">把主动权留在你手中</div><p>“讨论”模式只提供读取工具；“协作”模式允许生成计算和文件操作，默认先展示内容供你核对。</p><p>代码使用当前账户权限运行。自动执行只对本轮消息生效。</p></div>'+
    (!state.boot.config.api_base?'<div class="setup-note"><strong>还没有连接模型</strong><p>填写自己的接口地址、模型 ID 和密钥，即可开始 AI 协作。</p>'+button('连接模型','nav','secondary','data-view="settings"','settings')+'</div>':'')+'</aside></div>';
}
on('prompt',b=>{$('#chat-input').value=b.dataset.text;$('#chat-input').focus();});
document.addEventListener('input',e=>{if(e.target.id==='chat-input'&&state.session)sessionStorage.setItem('lumen.draft.'+state.session.id,e.target.value);});
on('send-chat',async b=>{
  const input=$('#chat-input'),text=input.value.trim();if(!text)return;
  const originSession=state.session.id,originProject=state.project.id;
  b.disabled=true;
  try{
    const job=await api('chat.start',{project_id:originProject,session_id:originSession,text,
      mode:$('#chat-mode').value,auto:$('#chat-auto').checked});
    state.chatJob=job.id;input.value='';sessionStorage.removeItem('lumen.draft.'+state.session.id);
    for(;;){
      const current=await api('chat.status',{job_id:job.id});
      const history=await api('session.read',{project_id:originProject,session_id:originSession});
      const visible=state.session.id===originSession&&state.project.id===originProject;
      if(visible)state.messages=history.messages;
      const transcript=visible?$('#transcript'):null;
      if(transcript){const nearBottom=transcript.scrollHeight-transcript.scrollTop-transcript.clientHeight<180;transcript.innerHTML=state.messages.map(messageHTML).join('');if(nearBottom)transcript.scrollTop=transcript.scrollHeight;}
      const pending=visible?$('#agent-pending'):null;
      if(pending){
        pending.innerHTML=current.pending?'<div class="approval-card"><div class="row">'+icon('info')+'<strong>核对即将执行的操作</strong><span class="tag">'+esc(current.pending.name)+'</span></div><pre>'+esc(current.pending.arguments.code||JSON.stringify(current.pending.arguments,null,2))+'</pre><div class="row">'+button('同意执行','approve-chat','primary','data-approved="true"','check')+button('不执行','approve-chat','secondary','data-approved="false"')+'</div></div>':
        current.status==='running'?'<div class="thinking"><span class="status-dot pulse"></span>正在处理，工具结果会保存在会话与运行记录中…</div>':'';
      }
      if(['success','failed','cancelled'].includes(current.status)){if(current.error)toast(current.error,true);break;}
      await new Promise(r=>setTimeout(r,800));
    }
  }finally{b.disabled=false;state.chatJob=null;}
});
on('approve-chat',b=>api('chat.approve',{job_id:state.chatJob,approved:b.dataset.approved==='true'}));
on('stop-chat',async()=>{if(state.chatJob){await api('chat.cancel',{job_id:state.chatJob});toast('已请求停止本轮任务');}});

export async function artifacts(){
  const [assets,runs]=await Promise.all([api('artifacts.list',{project_id:state.project.id}),api('runs.list',{project_id:state.project.id})]);
  return heading('RESULTS / PROVENANCE','结果看得见，来源查得到','当前文件、确切留存版本和每次运行分别记录。',button('刷新','nav','secondary','data-view="artifacts"','refresh'))+
    '<div class="section-label">成果文件 <span>'+assets.files.length+' 份 · 按修改时间排列</span></div>'+
    (assets.files.length?'<div class="artifact-grid">'+assets.files.slice(0,60).map(f=>'<article class="panel artifact-card"><button class="artifact-preview" data-action="preview" data-path="'+esc(f.path)+'">'+
      (/\.(png|jpg|jpeg|webp)$/i.test(f.path)?'<img loading="lazy" src="'+fileURL(f.path)+'" alt="'+esc(f.name)+'">':icon(f.extension==='.md'?'file':f.extension==='.csv'?'database':'file',38))+
      '</button><div class="artifact-info"><strong title="'+esc(f.path)+'">'+esc(f.name)+'</strong><small>'+bytes(f.bytes)+' · '+new Date(f.modified*1000).toLocaleDateString('zh-CN')+'</small><div class="row">'+button('预览','preview','secondary','data-path="'+esc(f.path)+'"')+button('保留版本','retain','secondary','data-path="'+esc(f.path)+'"')+'</div></div></article>').join('')+'</div>':
      '<div class="panel">'+empty('成果会在这里汇集','运行一次分析，生成的图表、数据表和报告会显示在这里。')+'</div>')+
    '<div class="section-label">运行账本 <span>保留成功、错误、取消及独立重跑</span></div><div class="panel"><div class="table-scroll"><table><thead><tr><th>任务</th><th>类型</th><th>状态</th><th>耗时</th><th>时间</th><th>检查</th></tr></thead><tbody>'+
    (runs.length?runs.map(r=>'<tr><td><strong>'+esc(r.title)+'</strong><small class="mono table-sub">'+r.id+'</small></td><td>'+esc(r.kind)+' / '+r.language+'</td><td>'+status(r.status)+'</td><td>'+esc(r.duration===null||r.duration===undefined?'—':r.duration+' s')+'</td><td>'+fmtDate(r.created)+'</td><td>'+button('查看来源','run-detail','secondary','data-id="'+r.id+'"')+'</td></tr>').join(''):'<tr><td colspan="6" class="muted">暂无运行记录</td></tr>')+
    '</tbody></table></div></div><div class="section-label">已保留版本 <span>当前文件变化后仍可比较身份与表格结构</span></div><div class="panel">'+
    (assets.versions.length?assets.versions.map(v=>'<div class="list-row">'+icon('layers')+'<div><strong>'+esc(v.path)+'</strong><small class="mono">'+v.sha256.slice(0,20)+'… · '+fmtDate(v.created)+'</small></div><span class="push"></span>'+button('与当前比较','compare-version','secondary','data-id="'+v.id+'"')+'</div>').join(''):empty('还没有留存版本','在成果卡片点击“保留版本”，保存当前文件的确切内容。'))+'</div>';
}
on('compare-version',async b=>{
  const value=await api('artifact.compare',{project_id:state.project.id,version_id:b.dataset.id});
  showPanel('版本比较','<div class="note-inline">'+icon(value.same?'check':'info')+(value.same?'当前内容与留存版本完全一致':value.current_missing?'当前文件已不存在，留存版本仍在':'当前内容与留存版本不同')+'</div><pre class="file-source">'+esc(JSON.stringify(value,null,2))+'</pre>');
});
on('run-detail',async b=>{
  const run=await api('run.read',{project_id:state.project.id,run_id:b.dataset.id});
  const inputs=run.detail.inputs||[],assets=run.detail.artifacts||[];
  showPanel('运行来源 · '+run.title,
    '<div class="row">'+status(run.status)+'<span class="mono muted">'+run.id+'</span><span class="push"></span>'+button('独立重跑','reproduce','secondary','data-id="'+run.id+'"','refresh')+'</div>'+
    '<div class="lineage"><div><small>声明输入</small>'+(inputs.length?inputs.map(i=>'<p>'+esc(i.path)+'<span class="hash">'+i.sha256.slice(0,12)+'…</span></p>').join(''):'<p>未声明输入文件</p>')+'</div><span>→</span><div><small>执行</small><p>'+esc(run.language)+' · '+esc(run.detail.execution_mode||'未开始')+'</p><p>'+esc(run.detail.duration||'—')+' 秒</p></div><span>→</span><div><small>观测到的输出</small>'+(assets.length?assets.map(i=>'<p>'+esc(i.path)+'</p>').join(''):'<p>没有新增或变化文件</p>')+'</div></div>'+
    '<p class="muted">'+esc(run.detail.provenance_scope||'')+'。输出归属反映运行期间观测到的文件变化，不证明已捕获全部外部依赖。</p>'+
    '<details open><summary>实际执行代码</summary><pre class="file-source">'+esc(run.code)+'</pre></details><details><summary>执行环境</summary><pre>'+esc(JSON.stringify(run.detail.environment,null,2))+'</pre></details>'+
    '<details><summary>实际输出</summary>'+outputs(run)+'</details>');
});
on('reproduce',async b=>{
  b.disabled=true;
  try{
    const result=await api('run.reproduce',{project_id:state.project.id,run_id:b.dataset.id});
    $('#modal').close();toast('已创建独立验证项目：新目录、新进程，仅复制已声明输入。');
    document.dispatchEvent(new CustomEvent('switch-project',{detail:{id:result.project.id,view:'artifacts'}}));
  }finally{b.disabled=false;}
});

let reportPath='';
export async function reports(){
  reportPath='';
  await refreshFiles();
  const files=state.files.filter(f=>f.path.startsWith('reports/')&&f.extension==='.md');
  return heading('REPORT / DELIVERY','让结果，成为可交接的研究记录','整理实际运行、编辑说明，导出包含脚本与结果快照的项目交付包。',
    button('生成分析记录','generate-report','primary','','file')+button('导出项目','export-project','secondary','','download'))+
    '<div class="report-layout"><section class="panel"><div class="panel-title">项目报告 <span class="count">'+files.length+'</span></div>'+
    (files.length?files.map(f=>'<button class="list-row list-button" data-action="edit-report" data-path="'+esc(f.path)+'">'+icon('file')+'<div><strong>'+esc(f.name)+'</strong><small>'+bytes(f.bytes)+'</small></div></button>').join(''):empty('还没有报告','可以根据真实运行记录生成初稿。'))+'</section>'+
    '<section class="panel report-editor"><div class="panel-title"><span id="report-name">Markdown 报告编辑器</span><span class="push"></span>'+button('保存','save-report','secondary','','check')+'</div><textarea id="report-content" placeholder="选择左侧报告，或点击“生成分析记录”。" aria-label="报告正文"></textarea><div class="note-inline">'+icon('info')+'自动整理的是实际执行记录；研究目标、结果解释和科学结论需要结合研究设计补充。</div></section></div>';
}
on('edit-report',async b=>{const file=await api('files.read',{project_id:state.project.id,path:b.dataset.path});reportPath=file.path;$('#report-name').textContent=file.path;$('#report-content').value=file.text;});
on('generate-report',async()=>{
  const result=await api('report.generate',{project_id:state.project.id});
  reportPath=result.path;$('#report-name').textContent=result.path;$('#report-content').value=result.text;toast('已根据实际运行生成分析记录');
});
on('save-report',async()=>{
  if(!reportPath)throw Error('请先打开或生成一份报告');
  await api('files.save',{project_id:state.project.id,path:reportPath,text:$('#report-content').value,overwrite:true});toast('报告已保存');
});
on('export-project',async()=>{
  const form=await dialog('导出项目交付包','<p>包含项目脚本、当前成果、运行代码、环境与结果快照。密钥和应用设置不会加入交付包。</p><label class="checkbox-label"><input type="checkbox" name="include_data" value="yes">同时包含 data 目录中的输入数据</label><p class="muted">默认不复制原始数据；单文件上限32 MiB，项目文件合计上限150 MiB，跳过项会列入清单。</p>','生成交付包');
  if(!form)return;
  const result=await api('project.export',{project_id:state.project.id,include_data:form.include_data==='yes'});
  window.open(fileURL(result.path,true),'_blank','noopener');toast('项目交付包已生成'+(result.skipped.length?'，有'+result.skipped.length+'项因大小限制跳过':''));
});

export async function settings(){
  const config=await api('settings.get');
  return heading('SETTINGS / CONNECTIONS','连接你的模型与计算环境','模型服务与本地计算分别配置。未连接 AI 时，本地分析仍可使用。')+
    '<div class="settings-layout"><section class="panel settings-card"><div class="panel-title">'+icon('spark')+' AI 模型服务 <span class="badge '+(config.api_base?'success':'neutral')+'">'+(config.api_base?'已保存配置':'尚未连接')+'</span></div><form id="settings-form">'+
    '<label>接口基础地址<input name="api_base" value="'+esc(config.api_base||'')+'" placeholder="https://服务商提供的地址/v1"></label><div class="form-grid"><label>接口协议<select name="protocol"><option value="chat" '+(config.protocol!=='responses'?'selected':'')+'>Chat Completions 兼容协议</option><option value="responses" '+(config.protocol==='responses'?'selected':'')+'>Responses 协议</option></select></label><label>模型 ID<input name="model" value="'+esc(config.model||'')+'" placeholder="服务商提供的模型ID"></label></div><label>API Key<input name="api_key" type="password" autocomplete="off" placeholder="'+(config.has_key?'已加密保存；留空保留原密钥':'填写你自己的 API Key；本机服务可留空')+'"></label>'+
    '<div class="note-inline">'+icon('info')+esc(config.environment.credential_storage)+'。使用在线模型时，消息和工具返回内容会通过所填接口传输。</div><div class="row">'+button('测试连接','test-model','secondary','','link')+button('保存配置','save-settings','primary','','check')+'</div><div id="model-test-result"></div>'+
    '<div class="panel-divider"></div><div class="panel-title">'+icon('terminal')+' 本地计算环境</div><label>Python 可执行文件<input name="python_path" value="'+esc(config.python_path||config.environment.python)+'"></label><label>Rscript 可执行文件（可选）<input name="rscript_path" value="'+esc(config.rscript_path||'')+'" placeholder="例如 C:\\Program Files\\R\\R-4.x.x\\bin\\Rscript.exe"></label><label>R 内核名称（可选）<input name="r_kernel" value="'+esc(config.r_kernel||'')+'" placeholder="已注册 IRkernel 的 kernelspec 名称，例如 ir"></label><p class="muted">配置 Rscript 时使用独立进程；使用 IRkernel 时支持持续变量。解释器变更在新内核生效，已有内核不会自动替换。</p>'+
    '<div class="panel-divider"></div><div class="panel-title">多语言工具路径</div><p class="muted">留空时自动检测。C/C++ 优先使用系统 GCC/Clang，未安装时可使用随项目安装的 Zig 编译器。</p>'+
    [['cc','C 编译器'],['cxx','C++ 编译器'],['java','Java 运行环境'],['javac','Java 编译器'],['node','Node.js'],['go','Go'],['rustc','Rust'],['pwsh','PowerShell'],['bash','Bash']].map(([key,label])=>'<label>'+label+'<input name="runner_'+key+'" value="'+esc(config.runner_paths?.[key]||'')+'" placeholder="自动检测；也可填写可执行文件完整路径"></label>').join('')+'</form></section>'+
    '<aside><section class="panel"><div class="panel-title">本机环境检查</div><div class="environment-head">'+icon('check',22)+'<div><strong>Python '+esc(config.environment.version)+'</strong><small>'+esc(config.environment.platform)+'</small></div></div>'+
    Object.entries(config.environment.packages).map(([n,v])=>'<div class="environment-row"><code>'+n+'</code><span class="'+(v?'success-text':'warning-text')+'">'+esc(v||'未安装')+'</span></div>').join('')+
    '<div class="environment-row"><span>R</span><span class="'+(config.environment.rscript||config.environment.kernels.includes('ir')?'success-text':'warning-text')+'">'+(config.environment.rscript||config.environment.kernels.includes('ir')?'已检测到':'尚未配置')+'</span></div></section>'+
    '<section class="panel"><div class="panel-title">语言工具检测</div>'+config.environment.languages.map(l=>'<div class="environment-row"><span>'+esc(l.label)+'</span><span class="'+(l.ready?'success-text':'warning-text')+'">'+(l.ready?'检测到工具':'待配置')+'</span></div>').join('')+'</section>'+
    '<section class="panel settings-help"><div class="panel-title">当前版本的能力范围</div><p>十二种语言执行适配、SSH/SFTP 服务器接入、本地项目、AI 工具调用、数据检查、分析流程、文献检索、版本留存、独立重跑和交付导出。</p><p>SSH 功能面向 Linux/Unix 服务器。当前尚未实现多人协作、远程持续 Notebook、跨机环境自动重建及完整依赖捕获。</p><p>自动执行代码使用当前账户权限，本版本未提供操作系统级隔离。</p><small>LUMEN Science '+esc(state.boot.version)+' · 本地工作台</small></section></aside></div>';
}
function settingsValues(){return Object.fromEntries(new FormData($('#settings-form')));}
on('save-settings',async()=>{
  const values=settingsValues();await api('settings.save',values);state.boot.config={...values,has_key:!!values.api_key||state.boot.config.has_key};delete state.boot.config.api_key;
  $('[name=api_key]').value='';toast('模型与计算环境配置已保存');
});
on('test-model',async b=>{
  b.disabled=true;$('#model-test-result').innerHTML='<p class="muted">正在测试连接…</p>';
  try{
    const result=await api('settings.test',settingsValues());
    $('#model-test-result').innerHTML='<div class="test-result success-text">'+icon('check')+'连接成功：'+esc(result.reply)+'</div>';
  }catch(error){$('#model-test-result').innerHTML='<p class="output-error">'+esc(error.message)+'</p>';}finally{b.disabled=false;}
});
