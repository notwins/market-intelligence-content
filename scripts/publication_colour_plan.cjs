/* Private stdin -> deterministic JSON plan; never writes public files. */
'use strict';
const fs=require('node:fs'),C=require('../site/publication-colour-core.js');
const c=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',x=>input+=x);
process.stdin.on('end',()=>{
 try{
  const r=JSON.parse(input),tags=C.index(c),ids=C.infer(r.text,c,r.existing||[]);
  const segments=(r.segments||[]).map(text=>C.matches(text,c).filter(m=>ids.includes(m.id)).map(m=>({...m,start:[...text.slice(0,m.start)].length,end:[...text.slice(0,m.end)].length,href:C.link(tags[m.id],m.text,c)})));
  process.stdout.write(JSON.stringify({ids,segments,labels:ids.map(id=>tags[id].label)}));
 }catch(e){process.stderr.write(e.message);process.exitCode=1;}
});
