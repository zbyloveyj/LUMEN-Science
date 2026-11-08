import {state,$,$$,esc,icon,api,button,heading,empty,outputs,on,toast,readSession,watchRun,dialog,dataOptions} from './core.js';
function languageOptions(selected='python'){
  return state.boot.environment.languages.map(l=>'<option value="'+l.id+'" '+(l.id===selected?'selected':'')+'>'+esc(l.label)+(l.ready?'':' · 待配置')+'</option>').join('');
}
const examples={
  python:"print('Hello, research!')",
  R:"message('Hello, research!')",
  c:'#include <stdio.h>\nint main(void) {\n    printf("Hello, research!\\n");\n    return 0;\n}',
  cpp:'#include <iostream>\nint main() {\n    std::cout << "Hello, research!" << std::endl;\n    return 0;\n}',
  java:'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, research!");\n    }\n}',
  javascript:"console.log('Hello, research!');",
  typescript:"const result: number = 6 * 7;\nconsole.log(result);",
  go:'package main\nimport "fmt"\nfunc main() { fmt.Println("Hello, research!") }',
  rust:'fn main() { println!("Hello, research!"); }',
  powershell:"Write-Output 'Hello, research!'",
  bash:"printf 'Hello, research!\\n'",
  sql:"SELECT 6 * 7 AS result;"
};

export async function notebook(){
  await readSession();
  const history=await api('runs.list',{project_id:state.project.id});
  return heading('COMPUTE / NOTEBOOK','把想法，变成可检查的计算','支持十二种语言适配；编译、执行、输出和记录清楚衔接。',
    button('变量面板','variables','secondary','','database')+button('导出笔记本','export-notebook','secondary','','download')+button('保存为流程','save-pipeline','secondary','','workflow')+
    button('添加单元','add-cell','primary','','plus'))+
    '<div class="notebook-toolbar"><span class="status-dot"></span><span>多语言执行 · 按需启动</span><span class="toolbar-divider"></span><span>会话：'+esc(state.session.title)+'</span><span class="push"></span><span class="muted">Ctrl + Enter 运行当前单元</span></div>'+
    '<div class="note-inline">'+icon('info')+'Python / IRkernel 保留会话变量；C/C++、Java 等使用编译或独立进程。Java 入口类使用 Main。缺少语言工具时请在设置中配置。</div>'+
    '<div id="cells">'+state.cells.map((cell,i)=>{
      const latest=history.find(r=>r.cell_id===cell.id);
      return '<article class="cell" data-cell="'+cell.id+'"><div class="cell-gutter"><span>['+(i+1)+']</span><button class="run-circle" data-action="run-cell" data-id="'+cell.id+'" aria-label="运行第'+(i+1)+'个单元">'+icon('play',15)+'</button></div><div class="cell-body"><div class="cell-top"><select class="cell-language" aria-label="代码语言">'+languageOptions(cell.language)+'</select><span class="muted">可编辑代码单元</span><span class="push"></span><button class="text-button" data-action="save-cell" data-id="'+cell.id+'">保存</button></div><textarea class="code-editor" spellcheck="false" aria-label="第'+(i+1)+'个代码单元">'+esc(cell.code)+'</textarea><div class="cell-output" id="output-'+cell.id+'">'+(latest?'<button class="text-button" data-action="load-cell-output" data-run="'+latest.id+'" data-cell="'+cell.id+'">查看上次输出 · '+esc(latest.title)+'</button>':'')+'</div></div></article>';
    }).join('')+'</div>';
}

async function currentCell(id){
  const node=$('[data-cell="'+id+'"]');
  return {project_id:state.project.id,session_id:state.session.id,cell_id:id,
    language:$('.cell-language',node).value,code:$('.code-editor',node).value,
    inputs:state.files.filter(f=>f.path.startsWith('data/')&&f.bytes<32*1024*1024).map(f=>f.path).slice(0,30)};
}
on('add-cell',async()=>{
  const values=await dialog('添加代码单元','<label>执行语言<select name="language">'+languageOptions()+'</select></label>','添加单元');
  if(!values)return;
  await api('cell.save',{project_id:state.project.id,session_id:state.session.id,language:values.language,code:examples[values.language]||''});
  document.dispatchEvent(new CustomEvent('navigate',{detail:'notebook'}));
});
on('export-notebook',async()=>{
  const result=await api('notebook.export',{project_id:state.project.id,session_id:state.session.id});
  const {fileURL}=await import('./core.js');
  window.open(fileURL(result.path,true),'_blank','noopener');toast('Notebook 已导出；混合语言在元数据中标记。');
});
on('save-cell',async b=>{await api('cell.save',await currentCell(b.dataset.id));toast('代码单元已保存');});
on('run-cell',async b=>{
  b.disabled=true;
  try{
    const params=await currentCell(b.dataset.id);
    const run=await api('cell.run',params);
    const output=$('#output-'+b.dataset.id);
    output.innerHTML=outputs(run)+button('停止','cancel-run','secondary','data-id="'+run.id+'"','stop');
    await watchRun(run.id,r=>{
      if(output.isConnected)output.innerHTML=outputs(r)+(['queued','running'].includes(r.status)?button('停止','cancel-run','secondary','data-id="'+r.id+'"','stop'):'');
    });
  }finally{b.disabled=false;}
});
on('load-cell-output',async b=>{
  const run=await api('run.read',{project_id:state.project.id,run_id:b.dataset.run});
  $('#output-'+b.dataset.cell).innerHTML=outputs(run);
});
on('variables',async()=>{
  const result=await api('kernel.variables',{project_id:state.project.id,session_id:state.session.id});
  const {showPanel}=await import('./core.js');
  showPanel('当前会话变量',result.variables.length?'<table><thead><tr><th>变量</th><th>类型</th><th>形状</th><th>摘要</th></tr></thead><tbody>'+result.variables.map(v=>'<tr><td><code>'+esc(v.name)+'</code></td><td>'+esc(v.type)+'</td><td>'+esc(v.shape)+'</td><td>'+esc(v.preview)+'</td></tr>').join('')+'</tbody></table>':empty('暂时没有可显示的变量',result.state==='busy'?'内核正在计算，请稍后刷新。':'先运行一个 Python 代码单元。'));
});
on('save-pipeline',async()=>{
  const cells=$$('[data-cell]');
  if(!cells.length)throw Error('请先添加代码单元');
  const form=await dialog('将当前 Notebook 保存为分析流程','<label>流程名称<input name="name" required value="我的分析流程"></label><p class="muted">按单元顺序执行；某一步失败后停止，不会跳过错误继续。</p>','保存流程');
  if(!form)return;
  const steps=[];
  for(const cell of cells){const value=await currentCell(cell.dataset.cell);steps.push({title:'步骤 '+(steps.length+1),language:value.language,code:value.code,inputs:value.inputs});}
  await api('pipeline.save',{project_id:state.project.id,name:form.name,steps});toast('流程已保存，可在分析流程中运行');
});
document.addEventListener('keydown',event=>{
  if((event.ctrlKey||event.metaKey)&&event.key==='Enter'&&event.target.classList.contains('code-editor')){
    event.preventDefault();const id=event.target.closest('[data-cell]').dataset.cell;
    $('[data-action="run-cell"][data-id="'+id+'"]').click();
  }
  if(event.key==='Tab'&&event.target.classList.contains('code-editor')){
    event.preventDefault();const input=event.target;input.setRangeText('    ',input.selectionStart,input.selectionEnd,'end');
  }
});
