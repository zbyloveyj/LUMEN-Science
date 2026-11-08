import {state,$,esc,icon,api,button,heading,empty,on,toast,dialog,showPanel,outputs,watchRun,refreshFiles,bytes} from './core.js';
let selectedServer='',remoteDirectory='';
export async function servers(){
  const data=await api('remote.list');await refreshFiles();
  if(!data.profiles.some(p=>p.id===selectedServer))selectedServer=data.profiles[0]?.id||'';
  const current=data.profiles.find(p=>p.id===selectedServer);
  return heading('REMOTE / SERVERS','把计算，连接到更大的环境','SSH 连接 Linux / Unix 服务器，执行远程命令并通过 SFTP 传输文件。',
    button('添加服务器','new-server','primary','','plus'))+
    (!data.available?'<div class="note-inline warning-text">'+icon('info')+'SSH 组件尚未安装，请按安装说明安装 paramiko。</div>':'')+
    '<div class="server-layout"><aside class="panel"><div class="panel-title">服务器连接 <span class="count">'+data.profiles.length+'</span></div>'+
    (data.profiles.length?data.profiles.map(p=>'<button class="data-file '+(p.id===selectedServer?'selected':'')+'" data-action="select-server" data-id="'+p.id+'">'+icon('layers')+'<span><strong>'+esc(p.name)+'</strong><small>'+esc(p.username+'@'+p.host+':'+p.port)+'</small></span></button>').join(''):empty('连接你的计算资源','使用自己的 SSH 账号、密钥或密码。'))+'</aside>'+
    '<section>'+(current?'<div class="panel server-profile"><div class="row"><span class="workflow-icon">'+icon('layers',24)+'</span><div><h2>'+esc(current.name)+'</h2><p class="muted">'+esc(current.username+'@'+current.host+':'+current.port)+'</p></div><span class="push"></span>'+button('测试连接','test-server','secondary','data-id="'+current.id+'"','link')+'</div><div class="path-box">'+esc(current.root)+'</div><small class="mono">主机指纹 '+esc(current.fingerprint)+'</small><div id="server-status"></div></div>'+
    '<div class="panel remote-terminal"><div class="panel-title">'+icon('terminal')+'远程命令 <span class="tag">SSH</span></div><textarea id="remote-command" class="code-editor" aria-label="远程命令" placeholder="例如：hostname; pwd; python3 --version"></textarea><div class="row"><small class="muted">在已配置的远程工作目录执行。每次命令为独立 Shell。</small><span class="push"></span>'+button('执行命令','run-remote','primary','data-id="'+current.id+'"','play')+'</div><div id="remote-output"></div></div>'+
    '<div class="panel"><div class="panel-title">远程文件 <span class="muted">SFTP · 目录内访问</span>'+button('刷新目录','list-remote','secondary','data-id="'+current.id+'" data-path="'+esc(remoteDirectory)+'"','refresh')+'</div><div class="row remote-path"><input id="remote-path" value="'+esc(remoteDirectory)+'" placeholder="相对服务器工作目录的路径" aria-label="远程相对目录">'+button('打开目录','open-remote-dir','secondary','data-id="'+current.id+'"')+button('上传本地文件','upload-remote','secondary','data-id="'+current.id+'"','upload')+'</div><div id="remote-files">'+empty('读取服务器目录','点击“打开目录”查看真实远程文件，不会自动连接。')+'</div></div>':
      '<div class="panel">'+empty('本地与远程，各自清晰','先添加服务器。首次连接需要核对主机指纹，密码使用 Windows 本机凭证加密保存。')+'</div>')+
    '<div class="note-inline">'+icon('info')+'远程命令会在服务器上实际执行。停止等待或连接断开不保证远端进程结束；请核查服务器进程。文件传输上限为32 MiB，不覆盖同名文件。</div></section></div>';
}
on('new-server',async()=>{
  const values=await dialog('添加 SSH 服务器','<div class="form-grid"><label>显示名称<input name="name" placeholder="实验室计算节点"></label><label>SSH 端口<input name="port" type="number" min="1" max="65535" value="22" required></label></div><label>主机名或 IP<input name="host" required placeholder="服务器地址"></label><label>用户名<input name="username" required></label><label>服务器工作目录<input name="root" value="." required placeholder="/home/user/research"></label><label>私钥完整路径（可选）<input name="key_file" placeholder="本机私钥路径，不会上传到服务器"></label><div class="form-grid"><label>登录密码（可选）<input name="password" type="password" autocomplete="off"></label><label>私钥口令（可选）<input name="passphrase" type="password" autocomplete="off"></label></div><label class="checkbox-label"><input type="checkbox" name="use_agent" value="yes">使用本机 SSH Agent</label><p class="muted">下一步只连接并读取服务器主机公钥；核对指纹后才保存配置和认证信息。</p>','检测服务器指纹',true);
  if(!values)return;
  toast('正在读取服务器主机指纹…');
  const probe=await api('remote.probe',{host:values.host,port:Number(values.port)});
  const trusted=await dialog('核对服务器身份','<p>请通过服务器管理员或可信渠道核对下面的主机指纹：</p><div class="path-box mono">'+esc(probe.fingerprint)+'</div><p>'+esc(values.host)+':'+esc(values.port)+' · '+esc(probe.key_type)+'</p><p class="muted">确认后会固定此指纹。后续指纹变化将拒绝连接。</p>','指纹一致，保存连接');
  if(!trusted)return;
  await api('remote.save',{...values,port:Number(values.port),use_agent:values.use_agent==='yes',probe_id:probe.probe_id});
  toast('服务器连接已保存');document.dispatchEvent(new CustomEvent('navigate',{detail:'servers'}));
});
on('select-server',b=>{selectedServer=b.dataset.id;remoteDirectory='';document.dispatchEvent(new CustomEvent('navigate',{detail:'servers'}));});
on('test-server',async b=>{
  b.disabled=true;
  try{const result=await api('remote.test',{profile_id:b.dataset.id});$('#server-status').innerHTML='<div class="test-result success-text">'+icon('check')+esc(result.message)+' · '+esc(result.root)+'</div>';}
  finally{b.disabled=false;}
});
on('run-remote',async b=>{
  const command=$('#remote-command').value.trim();if(!command)throw Error('请输入远程命令');
  b.disabled=true;
  try{
    const run=await api('remote.execute',{project_id:state.project.id,profile_id:b.dataset.id,command});
    await watchRun(run.id,r=>{const box=$('#remote-output');if(box)box.innerHTML=outputs(r)+(['queued','running'].includes(r.status)?button('停止等待','cancel-run','secondary','data-id="'+r.id+'"','stop'):'');});
  }finally{b.disabled=false;}
});
async function listRemote(profileId,path=''){
  remoteDirectory=path;
  const result=await api('remote.files',{profile_id:profileId,path});
  const box=$('#remote-files');if(!box)return;
  $('#remote-path').value=path;
  box.innerHTML=(path?'<button class="list-row list-button" data-action="list-remote" data-id="'+profileId+'" data-path="'+esc(path.split('/').slice(0,-1).join('/'))+'">'+icon('folder')+'返回上级目录</button>':'')+
    result.files.map(f=>'<div class="list-row">'+icon(f.directory?'folder':'file')+'<span><strong>'+esc(f.name)+(f.symlink?' ↗':'')+'</strong><small>'+bytes(f.bytes)+'</small></span><span class="push"></span>'+
      (f.directory?button('打开','list-remote','secondary','data-id="'+profileId+'" data-path="'+esc(f.path)+'"'):
        button('下载到项目','download-remote','secondary','data-id="'+profileId+'" data-path="'+esc(f.path)+'"','download'))+'</div>').join('')+
    (result.truncated?'<p class="muted">当前只显示前300项。</p>':'')+(result.files.length?'':empty('目录为空','可以上传项目内的文件。'));
}
on('list-remote',b=>listRemote(b.dataset.id,b.dataset.path||''));
on('open-remote-dir',b=>listRemote(b.dataset.id,$('#remote-path').value.trim()));
on('download-remote',async b=>{
  b.disabled=true;try{
    const result=await api('remote.transfer',{project_id:state.project.id,profile_id:b.dataset.id,direction:'download',remote:b.dataset.path});
    toast('已下载到 '+result.path);await refreshFiles();
  }finally{b.disabled=false;}
});
on('upload-remote',async b=>{
  const options=state.files.filter(f=>f.bytes<=32*1024*1024).map(f=>'<option value="'+esc(f.path)+'">'+esc(f.path)+'</option>').join('');
  const values=await dialog('上传项目文件','<label>本地文件<select name="local">'+options+'</select></label><label>远程相对文件路径<input name="remote" value="'+esc(remoteDirectory?remoteDirectory+'/':'')+'" required></label><p class="muted">上传到服务器工作目录内，不覆盖已有同名文件。</p>','上传文件');
  if(!values)return;
  await api('remote.transfer',{project_id:state.project.id,profile_id:b.dataset.id,direction:'upload',...values});
  toast('文件已上传');await listRemote(b.dataset.id,remoteDirectory);
});
