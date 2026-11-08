import {state,$,esc,icon,api,on,toast,dialog,readSession,refreshFiles,button} from './core.js';
import {notebook} from './notebook.js';
import {dataView,workflows,library} from './research.js';
import {overview,chat,artifacts,reports,settings} from './workspace.js';
import {servers} from './servers.js';

const navigation=[
  ['overview','研究总览','grid'],['chat','AI 协作','spark'],['notebook','多语言 Notebook','terminal'],
  ['data','数据资源','database'],['workflows','分析流程','workflow'],['library','文献与证据','book'],
  ['artifacts','成果与溯源','image'],['reports','报告与交付','file'],['servers','服务器','layers']
];
const views={overview,chat,notebook,data:dataView,workflows,library,artifacts,reports,settings,servers};
let renderVersion=0;

function shell(){
  $('#app').innerHTML='<aside class="sidebar"><a class="brand" href="#" data-action="nav" data-view="overview"><span class="brand-logo">L<span>✦</span></span><span>LUMEN<small>SCIENCE WORKBENCH</small></span></a>'+
    '<div class="sidebar-project-label">当前研究项目</div><select id="project-select" aria-label="当前项目">'+state.boot.projects.map(p=>'<option value="'+p.id+'" '+(p.id===state.project.id?'selected':'')+'>'+esc(p.name)+'</option>').join('')+'</select>'+
    '<button class="new-project-button" data-action="new-project">'+icon('plus',16)+' 新建 / 连接项目</button><div class="nav-label">工作空间</div><nav>'+navigation.map(([id,label,ic])=>'<button class="nav-item '+(state.view===id?'active':'')+'" data-action="nav" data-view="'+id+'">'+icon(ic)+'<span>'+label+'</span>'+(id==='servers'?'<small>SSH</small>':'')+'</button>').join('')+'</nav>'+
    '<div class="sidebar-bottom"><div class="local-card"><span class="status-dot"></span><strong>本地优先</strong><small>项目与计算，在你手中</small></div><button class="nav-item" data-action="nav" data-view="settings">'+icon('settings')+'<span>设置与环境</span></button><div class="sidebar-version">LUMEN Science <span>'+esc(state.boot.version)+'</span></div></div></aside>'+
    '<div class="main-shell"><header class="topbar"><div class="breadcrumb">'+icon('folder',16)+'<span>'+esc(state.project.name)+'</span><span class="crumb-slash">/</span><strong id="breadcrumb-view">研究总览</strong></div><div class="topbar-right"><select id="session-select" aria-label="当前会话">'+state.boot.sessions.map(s=>'<option value="'+s.id+'" '+(s.id===state.session.id?'selected':'')+'>'+esc(s.title)+'</option>').join('')+'</select><button class="icon-button" data-action="new-session" aria-label="新建会话" title="新建会话">'+icon('plus')+'</button><span class="topbar-divider"></span><span class="connection-badge"><i></i>本地服务就绪</span><button class="avatar" data-action="nav" data-view="settings" title="设置">研</button></div></header><main id="main-content"></main><footer class="app-footer"><span>'+icon('link',13)+' PROJECT-BOUND RESEARCH</span><span id="footer-environment">本机计算 · '+state.boot.environment.languages.filter(x=>x.ready).length+' 种语言可用</span></footer></div>';
}
async function stashEditors(){
  if(state.view!=='notebook')return;
  for(const cell of document.querySelectorAll('[data-cell]')){
    const old=state.cells.find(c=>c.id===cell.dataset.cell);
    const code=$('.code-editor',cell)?.value,language=$('.cell-language',cell)?.value;
    if(old&&(old.code!==code||old.language!==language)){
      await api('cell.save',{project_id:state.project.id,session_id:state.session.id,cell_id:old.id,code,language});
      old.code=code;old.language=language;
    }
  }
}
async function navigate(view){
  if(!views[view])return;
  await stashEditors();
  state.view=view;localStorage.setItem('lumen.view',view);
  const version=++renderVersion;
  document.querySelectorAll('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
  $('#breadcrumb-view').textContent=view==='settings'?'设置与环境':navigation.find(n=>n[0]===view)?.[1]||view;
  const main=$('#main-content');main.innerHTML='<div class="loading">正在打开工作空间…</div>';
  try{
    const content=await views[view]();
    if(version===renderVersion){main.innerHTML=content;main.scrollTop=0;}
  }catch(error){if(version===renderVersion)main.innerHTML='<div class="panel error-panel"><h2>此页面暂时未能打开</h2><p>'+esc(error.message)+'</p>'+button('重新打开','nav','secondary','data-view="'+view+'"','refresh')+'</div>';toast(error.message,true);}
}
async function load(projectId,view){
  await stashEditors();
  state.boot=await api('bootstrap',{project_id:projectId});
  state.project=state.boot.projects.find(p=>p.id===state.boot.project_id);
  state.session=state.boot.sessions[0];
  const remembered=localStorage.getItem('lumen.session.'+state.project.id);
  state.session=state.boot.sessions.find(s=>s.id===remembered)||state.session;
  localStorage.setItem('lumen.project',state.project.id);
  await refreshFiles();shell();await navigate(view||state.view);
}
on('nav',b=>navigate(b.dataset.view));
document.addEventListener('navigate',e=>navigate(e.detail));
document.addEventListener('switch-project',e=>load(e.detail.id,e.detail.view));
document.addEventListener('change',async e=>{
  try{
    if(e.target.id==='project-select')await load(e.target.value,'overview');
    if(e.target.id==='session-select'){
      await stashEditors();state.session=state.boot.sessions.find(s=>s.id===e.target.value);
      localStorage.setItem('lumen.session.'+state.project.id,state.session.id);await navigate(state.view);
    }
  }catch(error){toast(error.message,true);}
});
on('new-project',async()=>{
  const values=await dialog('新建或连接研究项目','<label>项目名称<input name="name" required placeholder="例如：我的实验数据研究"></label><label>研究目标<textarea name="description" placeholder="简要说明你希望回答的问题"></textarea></label><label>已有文件夹路径（可选）<input name="path" placeholder="留空则创建一个独立的新项目目录"></label><p class="muted">连接已有目录时会新增 data、scripts、outputs、reports 和 .lumen 目录，不移动原文件。</p>','打开项目');
  if(!values)return;const project=await api('project.create',values);await load(project.id,'overview');toast('研究项目已打开');
});
on('new-session',async()=>{
  const values=await dialog('新建研究会话','<label>会话名称<input name="title" required placeholder="例如：模型结果核查"></label>','创建会话');if(!values)return;
  const session=await api('session.create',{project_id:state.project.id,title:values.title});
  localStorage.setItem('lumen.session.'+state.project.id,session.id);await load(state.project.id,'chat');
});
document.addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){
    e.preventDefault();navigate('data');
  }
});
window.addEventListener('unhandledrejection',e=>{toast(e.reason?.message||'操作未完成',true);e.preventDefault();});
state.view=localStorage.getItem('lumen.view')||'overview';
load(localStorage.getItem('lumen.project'),state.view).catch(error=>{
  $('#app').innerHTML='<div class="startup-error"><h1>LUMEN Science</h1><p>'+esc(error.message)+'</p><p>请关闭页面并重新运行启动程序。</p></div>';
});
