(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const data = JSON.parse($("report-data").textContent);
  const eventSelect = $("chart-event"), marketSelect = $("chart-market"), cursor = $("chart-cursor");
  const state = {archive:null, plots:[], selected:null, metric:null, market:null};
  const valid = value => typeof value === "number" && Number.isFinite(value);
  const iso = time => new Date(time).toISOString().slice(0,10);
  const day = 86400000;
  const pretty = value => valid(value) ? value.toLocaleString("en-US",{maximumFractionDigits:4}) : "Unavailable";
  const signed = value => valid(value) ? (value >= 0 ? "+" : "−") + Math.abs(value).toFixed(2) + "σ" : "σ unavailable";
  const colours = {metric:"#386b5c", mean:"#836044", sd1:"#738a77", sd2:"#6c7d94", entry:"#a25d46", cursor:"#554b70"};
  let archiveRequest;

  function archive() {
    if (!archiveRequest) {
      archiveRequest = fetch(data.analytics).then(response => {
        if (!response.ok) throw new Error("Frozen history returned " + response.status);
        return response.json();
      }).then(payload => {
        if (!Array.isArray(payload.datasets)) throw new Error("Frozen archive is incomplete");
        return new Map(payload.datasets.map(entry => [entry.id,entry]));
      }).catch(error => {
        archiveRequest = null;
        throw error;
      });
    }
    return archiveRequest;
  }

  function getRows(entry) {
    const metric = entry.metrics.find(m => m.field === entry.default_field);
    return {metric, rows:FredSigma.analyze(entry.default_series.points,{
      years:5, transform:metric.transform || "level", frequency:entry.frequency, excludeDates:entry.quality_dates || []
    })};
  }

  function band(row, multiple) {
    return row.n >= 12 && valid(row.mean) && valid(row.sd) && row.sd > 0 ? row.mean + multiple * row.sd : null;
  }

  function makePlot(container, label, rows, entry, guides) {
    const canvas = document.createElement("canvas");
    canvas.setAttribute("role","img");
    canvas.setAttribute("aria-label",label + ". Use the date slider for exact values.");
    container.replaceChildren(canvas);
    const plot = {canvas, rows, entry, guides, start: Date.parse(rows[0].date),end:Date.parse(rows.at(-1).date)};
    canvas.addEventListener("pointerdown", event => {
      if (plot !== state.plots[0]) return;
      const box = canvas.getBoundingClientRect();
      const fraction = Math.min(1, Math.max(0, (event.clientX - box.left - 57) / Math.max(1, box.width - 72)));
      const target = plot.start + fraction * (plot.end - plot.start);
      const index = rows.reduce((best,row,i) => Math.abs(Date.parse(row.date)-target) < Math.abs(Date.parse(rows[best].date)-target) ? i : best,0);
      cursor.value = String(index);
      drawAll();
    });
    return plot;
  }

  function draw(plot, selectedDate) {
    const {canvas, rows, start, end, guides} = plot;
    const width = canvas.clientWidth, height = canvas.clientHeight;
    if (!width || !height) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width*dpr); canvas.height = Math.round(height*dpr);
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr,dpr);
    const left=57, right=width-15, top=15, bottom=height-27;
    const values = rows.flatMap(row => guides ? [row.value,band(row,-2),band(row,2)] : [row.value]).filter(valid);
    if (!values.length) {
      ctx.fillStyle="#50676a";ctx.font="13px system-ui";
      ctx.fillText("No saved values in this window",12,25);
      return;
    }
    const low = Math.min(...values), high = Math.max(...values), range = high-low || 1;
    const x = date => left + (Date.parse(date)-start) / (end-start || 1) * (right-left);
    const y = value => bottom - (value-low+range*.07) / (range*1.14) * (bottom-top);
    ctx.font="11px system-ui";
    for (let i=0;i<=3;i++) {
      const value=low+i*range/3, yy=y(value);
      ctx.strokeStyle="#e1e9e3"; ctx.setLineDash([]); ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(right,yy);ctx.stroke();
      ctx.fillStyle="#50676a";ctx.textAlign="right";ctx.fillText(pretty(value),left-6,yy+4);
    }
    ctx.fillStyle="#50676a";ctx.textAlign="left";ctx.fillText(iso(start),left,height-8);
    ctx.textAlign="right";ctx.fillText(iso(end),right,height-8);
    function trace(get, colour, dash, weight) {
      ctx.strokeStyle=colour;ctx.setLineDash(dash);ctx.lineWidth=weight;ctx.beginPath();
      let hasPoint=false;
      for (const row of rows) {
        const value=get(row);
        if (!valid(value)) {hasPoint=false;continue;}
        if (hasPoint) ctx.lineTo(x(row.date),y(value));
        else ctx.moveTo(x(row.date),y(value));
        hasPoint=true;
      }
      ctx.stroke();
    }
    if (guides) {
      trace(row=>band(row,-2),colours.sd2,[5,4],1);
      trace(row=>band(row,2),colours.sd2,[5,4],1);
      trace(row=>band(row,-1),colours.sd1,[2,3],1);
      trace(row=>band(row,1),colours.sd1,[2,3],1);
      trace(row=>band(row,0),colours.mean,[8,3],1);
    }
    trace(row=>row.value,colours.metric,[],2);
    for (const [date,colour,dash] of [[plot.entry,colours.entry,[4,3]],[selectedDate,colours.cursor,[1,3]]]) {
      const xx=x(date);
      if (!(xx>=left && xx<=right)) continue;
      ctx.strokeStyle=colour;ctx.lineWidth=1;ctx.setLineDash(dash);ctx.beginPath();ctx.moveTo(xx,top);ctx.lineTo(xx,bottom);ctx.stroke();
    }
  }

  function drawAll() {
    if (!state.plots.length) return;
    const signal = state.plots[0].rows[Number(cursor.value)];
    for (const plot of state.plots) draw(plot, signal.date);
    const marketPlot = state.plots[1];
    const market = marketPlot?.rows.filter(row => row.date <= signal.date && valid(row.value)).at(-1);
    const marketText = market ? ` · ${state.market.name} ${pretty(market.value)} on ${market.date}` : "";
    cursor.setAttribute("aria-valuetext",signal.date);
    $("cursor-reading").textContent = `${signal.date} · ${state.selected.name} ${pretty(signal.value)} · ${signed(signal.z)}${marketText}`;
  }

  async function render() {
    const token = eventSelect.value + ":" + marketSelect.value;
    const selected = data.events[Number(eventSelect.value)];
    const market = data.markets.find(m => m.id === marketSelect.value);
    const {event} = selected;
    $("chart-status").textContent="Loading the saved comparison…";
    $("event-prices").innerHTML=selected.comparison;
    $("chart-replay").href="https://notwins.github.io/market-intelligence-hub/fred/cross-market-replay.html?event="+encodeURIComponent(event.key)+"&years=5#event-replay";
    try {
      const values=await archive();
      if (token !== eventSelect.value + ":" + marketSelect.value) return;
      const entry=values.get(selected.id), marketEntry=values.get(market.id);
      const {metric,rows}=getRows(entry);
      const eventTime=Date.parse(event.date);
      const vicinity=rows.filter(row=>Math.abs(Date.parse(row.date)-eventTime) <= day*(event.period.days>30?460:event.period.days>1?350:75));
      const marketStart=Date.parse(event.period.start)-day*(event.period.days>1?0:10);
      const marketEnd=Math.min(Date.parse(data.snapshot),Date.parse(event.period.end)+day*(event.period.days>1?0:10));
      const quoted=marketEntry.default_series.points.filter(([date])=>Date.parse(date)>=marketStart&&Date.parse(date)<=marketEnd).map(([date,value])=>({date,value}));
      state.selected=selected;state.market=market;state.metric=metric;
      state.plots=[makePlot($("signal-plot"),selected.name,vicinity,event.date,true)];
      if (quoted.some(row=>valid(row.value))) state.plots.push(makePlot($("market-plot"),market.name,quoted,event.period.end,false));
      else $("market-plot").textContent="No saved quotes for this instrument in the selected market window.";
      const unit=metric.transform==="yoy"?"year-over-year percent change":metric.unit||entry.unit;
      $("signal-caption").textContent=`${selected.name} · ${unit} · rolling prior mean and ±1/±2 SD`;
      $("market-caption").textContent=`${market.name} · ${market.unit} · ${iso(marketStart)} to ${iso(marketEnd)}`;
      $("chart-status").textContent=`${event.period.label} · ${event.threshold}σ entry · ${signed(event.z)}. Vertical terracotta line marks the FRED entry or period end on the market chart.`;
      cursor.max=String(vicinity.length-1);cursor.value=String(vicinity.findIndex(row=>row.date===event.date));
      cursor.closest("label").hidden=false;
      drawAll();
    } catch {
      $("chart-status").textContent="The frozen chart history could not load. The dated comparison values and market replay remain available below.";
      $("signal-plot").textContent="";
      $("market-plot").textContent="";
      cursor.closest("label").hidden=true;
      state.plots=[];
    }
  }

  eventSelect.addEventListener("change",render);
  marketSelect.addEventListener("change",render);
  cursor.addEventListener("input",drawAll);
  window.addEventListener("resize",drawAll);
  document.querySelectorAll("[data-event]").forEach(button=>button.addEventListener("click",()=>{
    eventSelect.value=button.dataset.event;render();eventSelect.focus({preventScroll:true});
    $("chart-explorer").scrollIntoView({block:"start"});
  }));
  render();
})();
