export const state = {view:'overview',boot:null,project:null,session:null,files:[],messages:[],cells:[],chatJob:null,runDetails:null};
const token = document.querySelector('meta[name=lumen-token]').content;
export const $ = (selector,root=document)=>root.querySelector(selector);
export const $$ = (selector,root=document)=>[...root.querySelectorAll(selector)];
export const esc = value => String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const fmtDate = value => value ? new Date(value).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}) : '—';
export const bytes = n => n<1024 ? n+' B' : n<1048576 ? (n/1024).toFixed(1)+' KB' : (n/1048576).toFixed(1)+' MB';
export const statusNames = {queued:'排队中',running:'运行中',success:'已完成',failed:'运行失败',cancelled:'已取消',interrupted:'中断待核查',needs_approval:'等待核对'};
export const status = value => '<span class="badge '+esc(value)+'">'+esc(statusNames[value]||value)+'</span>';
export function icon(name,size=18){return '<svg class="icon" width="'+size+'" height="'+size+'" aria-hidden="true"><use href="/icons.svg#'+name+'"></use></svg>';}
export function fileURL(path,download=false,projectId=state.project.id){return '/file?project='+encodeURIComponent(projectId)+'&path='+encodeURIComponent(path)+(download?'&download=1':'');}
export async function api(action,params={}){
  const response=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json','X-Lumen-Token':token},
    body:JSON.stringify({action,params})});
  let result;
  try{result=await response.json();}catch{throw Error('工作台连接已断开，请重新启动。');}
  if(!result.ok)throw Error(result.error||'操作未完成');
  return result.data;
}
export function toast(message,error=false){
  const box=$('#toast');box.textContent=message;box.className='show'+(error?' error':'');
  clearTimeout(toast.timer);toast.timer=setTimeout(()=>box.className='',6000);
}
export const actionHandlers={};
export function on(name,handler){actionHandlers[name]=handler;}
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-action]');
  if(!button||button.disabled)return;
  const handler=actionHandlers[button.dataset.action];
  if(!handler)return;
  event.preventDefault();
  try{await handler(button,event);}catch(error){toast(error.message,true);}
});
export function empty(title,description,button=''){
  return '<div class="empty">'+icon('layers',36)+'<h3>'+esc(title)+'</h3><p>'+esc(description)+'</p>'+button+'</div>';
}
export function heading(eyebrow,title,description,actions=''){
  return '<div class="page-heading"><div><div class="eyebrow">'+esc(eyebrow)+'</div><h1>'+esc(title)+'</h1><p>'+esc(description)+'</p></div><div class="heading-actions">'+actions+'</div></div>';
}
export function button(text,action,kind='secondary',extra='',ic=''){
  return '<button type="button" class="btn '+kind+'" data-action="'+action+'" '+extra+'>'+(ic?icon(ic):'')+esc(text)+'</button>';
}
export function dialog(title,body,submit='保存',wide=false){
  return new Promise(resolve=>{
    const modal=$('#modal');modal.className=wide?'wide':'';
    modal.innerHTML='<form method="dialog"><div class="modal-heading"><h2>'+esc(title)+'</h2><button class="icon-button" value="cancel" aria-label="关闭">'+icon('close')+'</button></div><div class="modal-body">'+body+'</div><div class="modal-footer"><button class="btn secondary" value="cancel">取消</button><button class="btn primary" value="save">'+esc(submit)+'</button></div></form>';
    const form=$('form',modal);
    const onClose=()=>{
      if(modal.open)return;
      modal.removeEventListener('close',onClose);
      resolve(null);
    };
    modal.returnValue='';
    modal.addEventListener('close',onClose);
    form.addEventListener('submit',event=>{
      event.preventDefault();
      const value=event.submitter?.value||'';
      const result=value==='save'?Object.fromEntries(new FormData(form)):null;
      modal.removeEventListener('close',onClose);
      modal.close(value);
      resolve(result);
    });
    modal.showModal();
  });
}
export function showPanel(title,body){
  const modal=$('#modal');modal.className='wide';
  modal.innerHTML='<form method="dialog"><div class="modal-heading"><h2>'+esc(title)+'</h2><button class="icon-button" aria-label="关闭">'+icon('close')+'</button></div><div class="modal-body">'+body+'</div><div class="modal-footer"><button class="btn primary">关闭</button></div></form>';modal.showModal();
}
export function markdown(text){
  const chunks=String(text).split(/(\x60\x60\x60[\s\S]*?\x60\x60\x60)/g);
  return chunks.map(chunk=>{
    if(chunk.startsWith('\x60\x60\x60'))return '<pre class="code-block"><code>'+esc(chunk.replace(/^\x60\x60\x60[^\n]*\n?/,'').replace(/\x60\x60\x60$/,''))+'</code></pre>';
    return esc(chunk).split('\n').map(line=>{
      line=line.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/\x60([^\x60]+)\x60/g,'<code>$1</code>');
      if(/^### /.test(line))return '<h4>'+line.slice(4)+'</h4>';
      if(/^## /.test(line))return '<h3>'+line.slice(3)+'</h3>';
      if(/^# /.test(line))return '<h2>'+line.slice(2)+'</h2>';
      if(/^- /.test(line))return '<div class="md-bullet">• '+line.slice(2)+'</div>';
      return line?'<p>'+line+'</p>':'';
    }).join('');
  }).join('');
}
export function outputs(run){
  if(!run)return '';
  const items=run.detail?.outputs||[];
  const html=items.map(o=>{
    if(o.type==='image')return '<a href="'+fileURL(o.path,false,run.project_id)+'" target="_blank" rel="noopener"><img class="output-image" src="'+fileURL(o.path,false,run.project_id)+'" alt="计算生成的图表"></a>';
    return '<pre class="output-text '+(o.type==='error'?'output-error':'')+'">'+esc(String(o.text||'').replace(/\u001b\[[0-9;]*m/g,''))+'</pre>';
  }).join('');
  return '<div class="output-head">'+status(run.status)+'<span>'+esc(run.detail?.duration?run.detail.duration+' 秒':'等待计算结果')+'</span></div>'+html+
    (run.detail?.error&&!items.some(o=>o.type==='error')?'<pre class="output-text output-error">'+esc(run.detail.error)+'</pre>':'')+
    (!html&&run.status==='success'?'<p class="muted">运行完成，没有产生可显示的输出。</p>':'');
}
const watchers=new Set();
export async function watchRun(runId,callback){
  if(watchers.has(runId))return;
  watchers.add(runId);
  const projectId=state.project.id;
  try{
    for(;;){
      const run=await api('run.read',{project_id:projectId,run_id:runId});
      callback?.(run);
      document.dispatchEvent(new CustomEvent('run-update',{detail:run}));
      if(!['queued','running'].includes(run.status)){
        document.dispatchEvent(new CustomEvent('run-finished',{detail:run}));return run;
      }
      await new Promise(r=>setTimeout(r,650));
    }
  }finally{watchers.delete(runId);}
}
export async function refreshFiles(){
  state.files=(await api('files.list',{project_id:state.project.id})).files;return state.files;
}
export async function readSession(){
  const data=await api('session.read',{project_id:state.project.id,session_id:state.session.id});
  state.messages=data.messages;state.cells=data.cells;return data;
}
export function dataOptions(selected=''){
  return state.files.filter(f=>['.csv','.tsv','.xlsx','.xls','.parquet'].includes(f.extension)).map(f=>'<option value="'+esc(f.path)+'" '+(selected===f.path?'selected':'')+'>'+esc(f.path)+'</option>').join('');
}
export async function previewFile(path){
  if(/\.(png|jpg|jpeg|webp|gif)$/i.test(path)){
    showPanel(path,'<img class="preview-image" src="'+fileURL(path)+'" alt="'+esc(path)+'">');return;
  }
  if(/\.(csv|tsv|xlsx|xls|parquet)$/i.test(path)){
    document.dispatchEvent(new CustomEvent('open-data',{detail:path}));return;
  }
  if(/\.pdf$/i.test(path)){window.open(fileURL(path),'_blank','noopener');return;}
  const data=await api('files.read',{project_id:state.project.id,path});
  showPanel(path,'<pre class="file-source">'+esc(data.text)+'</pre>'+(data.truncated?'<p class="muted">内容已截断。</p>':''));
}
on('preview',b=>previewFile(b.dataset.path));
on('download',b=>{window.open(fileURL(b.dataset.path,true),'_blank','noopener');});
on('retain',async b=>{await api('artifact.retain',{project_id:state.project.id,path:b.dataset.path});toast('已保存当前文件的确切版本');});
on('cancel-run',async b=>{await api('run.cancel',{project_id:state.project.id,run_id:b.dataset.id});toast('已请求停止');});
