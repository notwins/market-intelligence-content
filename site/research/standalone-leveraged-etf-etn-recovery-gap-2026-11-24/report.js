'use strict';
(() => {
  const paths = JSON.parse(document.getElementById('scenario-data').textContent);
  const chart = document.getElementById('path-chart');
  const ns = 'http://www.w3.org/2000/svg';
  const textNode = (tag, text, attrs = {}) => {
    const node = document.createElementNS(ns, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    if (text !== null) node.textContent = text;
    return node;
  };
  // All labels come from the precomputed exact decimal strings. Numbers below
  // are used only for geometry, never for displayed financial calculations.
  const usd = (s) => {
    const [whole, fraction = ''] = String(s).split('.');
    return '$' + whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '.' + fraction.padEnd(2, '0');
  };
  const pct = (s) => (String(s).startsWith('-') ? '−' + String(s).slice(1) : Number(s) > 0 ? '+' + s : s) + '%';
  const draw = (index) => {
    const path = paths[index];
    const count = path.days.length;
    const width = window.innerWidth < 600 ? 340 : 700;
    document.getElementById('path-svg').setAttribute('viewBox', '0 0 '+width+' 330');
    const max = Math.max(...path.chart.benchmark_values_usd, ...path.chart.ideal_3x_values_usd, 110);
    const ceiling = Math.ceil(max / 25) * 25;
    const x = day => 45 + day * (width-95) / (count - 1);
    const y = value => 265 - value * 230 / ceiling;
    chart.replaceChildren();
    for (let i=0;i<=5;i++) {
      const val = ceiling * i/5;
      chart.append(textNode('line', null, {x1:45,y1:y(val),x2:width-50,y2:y(val),stroke:'#DBE0E4','stroke-width':1}));
      chart.append(textNode('text',String(val),{x:35,y:y(val)+4,'text-anchor':'end','font-size':12}));
    }
    path.days.forEach((d,i)=>chart.append(textNode('text',i===0?'Start':'Day '+i,{x:x(i),y:292,'text-anchor':'middle','font-size':12})));
    const series = [
      {field:'benchmark_value_usd',color:'#12354E',dash:null},
      {field:'ideal_3x_value_usd',color:'#A62C37',dash:'7 5'}
    ];
    series.forEach((s,si)=> {
      const attrs={points:path.days.map((d,i)=>x(i)+','+y(Number(d[s.field]))).join(' '),fill:'none',stroke:s.color,'stroke-width':3.5,'stroke-linejoin':'round'};
      if(s.dash) attrs['stroke-dasharray']=s.dash;
      chart.append(textNode('polyline',null,attrs));
      path.days.forEach((d,i)=> {
        const yy=y(Number(d[s.field]));
        chart.append(textNode(si?'rect':'circle',null,si?{x:x(i)-4,y:yy-4,width:8,height:8,fill:s.color}:{cx:x(i),cy:yy,r:4.5,fill:s.color}));
        const one=Number(d.benchmark_value_usd), three=Number(d.ideal_3x_value_usd);
        const above=si===0 ? one>=three : three>one;
        if(i>0) chart.append(textNode('text',usd(d[s.field]),{x:x(i),y:yy+(above?-12:20),'text-anchor':'middle','font-size':13,'font-weight':700,style:'fill:'+s.color}));
      });
    });
    document.getElementById('path-desc-svg').textContent = path.label+'. Benchmark values: '+path.days.map(d=>d.benchmark_value_usd).join(', ')+'. Daily 3× values: '+path.days.map(d=>d.ideal_3x_value_usd).join(', ')+'.';
    document.getElementById('path-title-svg').textContent = path.label+': benchmark and daily 3× illustration';
    const findings = [
      'A truly flat daily benchmark leaves both ideal products at $100 before costs. There is no volatility drag in this zero-volatility model.',
      'Two +10% benchmark days lift the benchmark to $121 and the daily 3× model to $169. Favourable compounding produces +69%, exceeding three times +21%.',
      'Two −10% benchmark days leave $81 in the benchmark and $49 in the daily 3× model. Repeated daily losses sharply reduce remaining capital.',
      'A +10%, −10% path leaves the benchmark at $99 and the daily 3× model at $91. Equal-sized percentage gains and losses do not cancel.',
      'A −20% day followed by +25% restores the benchmark to $100, but the daily 3× product ends at $70. Its rebound operates on a smaller capital base.',
      'Repeating the −20%, +25% round trip twice restores the benchmark to $100 while leaving the daily 3× model at $49.'
    ];
    document.getElementById('path-lab-finding').textContent=findings[index];
    document.getElementById('path-outcome').textContent = '1× benchmark: '+path.days.map(d=>usd(d.benchmark_value_usd)).join(' → ')+'. Daily 3×: '+path.days.map(d=>usd(d.ideal_3x_value_usd)).join(' → ')+'.';
    const table=document.createElement('table');
    const head=document.createElement('thead');const hr=document.createElement('tr');
    ['Point','Benchmark daily return','1× value','Daily 3× value'].forEach(t=>{const th=document.createElement('th');th.scope='col';th.textContent=t;hr.append(th);});
    head.append(hr);table.append(head);
    const body=document.createElement('tbody');
    path.days.forEach(d=>{const row=document.createElement('tr');[''+d.day,d.day===0?'Start':pct(d.benchmark_daily_return_pct),usd(d.benchmark_value_usd),usd(d.ideal_3x_value_usd)].forEach(t=>{const td=document.createElement('td');td.textContent=t;row.append(td);});body.append(row);});
    table.append(body);const wrap=document.createElement('div');wrap.className='table-wrap';wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Scrollable scenario values');wrap.append(table);document.getElementById('path-detail').replaceChildren(wrap);
  };
  const select=document.getElementById('path-preset');
  select.addEventListener('change',()=>draw(Number(select.value)));draw(Number(select.value));
  window.addEventListener('resize',()=>draw(Number(select.value)));
  document.querySelectorAll('[data-filter]').forEach(input=>{
    const kind=input.dataset.filter;const rows=[...document.querySelectorAll('[data-directory="'+kind+'"]')];
    input.addEventListener('input',()=>{
      const query=input.value.trim().toLowerCase();let shown=0;
      rows.forEach(row=>{const match=row.dataset.search.toLowerCase().includes(query);row.hidden=!match;if(match)shown++;});
      document.getElementById(kind.toLowerCase()+'-count').textContent=shown+' of 20 '+kind+'s shown';
      document.getElementById(kind.toLowerCase()+'-empty').hidden=shown!==0;
    });
  });
  document.getElementById('print-report').addEventListener('click',()=>window.print());
  let sourceWasOpen = false;
  const sourceRegister = document.querySelector('.source-register');
  window.addEventListener('beforeprint',()=>{
    sourceWasOpen = sourceRegister.open;
    sourceRegister.open = true;
  });
  window.addEventListener('afterprint',()=>{sourceRegister.open = sourceWasOpen;});
})();
