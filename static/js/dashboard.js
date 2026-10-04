(() => {
  const node = document.getElementById('dashboard-data');
  if (!node || typeof echarts === 'undefined') return;
  const data = JSON.parse(node.textContent);
  const baseText = '#55635f';
  const axisLine = '#dfe8e3';
  const charts = [];
  const init = (id) => { const el = document.getElementById(id); if (!el) return null; const chart = echarts.init(el); charts.push(chart); return chart; };
  const sensor = init('sensor-chart');
  if (sensor) sensor.setOption({tooltip:{trigger:'axis'},legend:{data:['温度 °C','湿度 %','墒情 %'],textStyle:{color:baseText}},grid:{left:44,right:18,top:45,bottom:35},xAxis:{type:'category',data:data.labels,axisLine:{lineStyle:{color:axisLine}},axisLabel:{color:baseText}},yAxis:{type:'value',axisLine:{show:false},splitLine:{lineStyle:{color:'#edf2ef'}},axisLabel:{color:baseText}},series:[{name:'温度 °C',type:'line',smooth:true,data:data.temperature,symbol:'circle',symbolSize:6,lineStyle:{width:3,color:'#16856f'},itemStyle:{color:'#16856f'},areaStyle:{color:'rgba(22,133,111,.08)'}},{name:'湿度 %',type:'line',smooth:true,data:data.humidity,lineStyle:{width:3,color:'#3b82c4'},itemStyle:{color:'#3b82c4'}},{name:'墒情 %',type:'line',smooth:true,data:data.soil,lineStyle:{width:3,color:'#8b6db7'},itemStyle:{color:'#8b6db7'}}]});
  const device = init('device-chart');
  if (device) device.setOption({tooltip:{trigger:'item'},legend:{bottom:0,textStyle:{color:baseText}},series:[{type:'pie',radius:['48%','72%'],center:['50%','43%'],label:{show:false},data:data.device_distribution.map((x,i)=>({name:x.status,value:x.count,itemStyle:{color:['#16856f','#aab5b1','#d99427','#d4534c'][i%4]}}))}]});
  const sensitive = init('sensitive-chart');
  if (sensitive) sensitive.setOption({tooltip:{trigger:'axis'},grid:{left:42,right:16,top:20,bottom:38},xAxis:{type:'category',data:data.sensitive_distribution.map(x=>x.sensitivity_level),axisLabel:{color:baseText,rotate:20},axisLine:{lineStyle:{color:axisLine}}},yAxis:{type:'value',splitLine:{lineStyle:{color:'#edf2ef'}},axisLabel:{color:baseText}},series:[{type:'bar',barWidth:28,data:data.sensitive_distribution.map((x,i)=>({value:x.count,itemStyle:{color:['#69a78f','#5d91bc','#d99427','#c84f4a'][i%4],borderRadius:[5,5,0,0]}}))}]});
  const security = init('security-chart');
  if (security) { const labels=[...new Set([...data.risk_trend.map(x=>x.date),...data.alert_trend.map(x=>x.date)])].sort(); const map=(items)=>{const d=Object.fromEntries(items.map(x=>[x.date,x.count]));return labels.map(x=>d[x]||0)}; security.setOption({tooltip:{trigger:'axis'},legend:{data:['风险事件','安全告警'],textStyle:{color:baseText}},grid:{left:42,right:18,top:42,bottom:35},xAxis:{type:'category',data:labels,axisLine:{lineStyle:{color:axisLine}},axisLabel:{color:baseText}},yAxis:{type:'value',splitLine:{lineStyle:{color:'#edf2ef'}},axisLabel:{color:baseText}},series:[{name:'风险事件',type:'bar',barMaxWidth:28,data:map(data.risk_trend),itemStyle:{color:'#d99427',borderRadius:[5,5,0,0]}},{name:'安全告警',type:'line',smooth:true,data:map(data.alert_trend),lineStyle:{width:3,color:'#c84f4a'},itemStyle:{color:'#c84f4a'}}]}); }
  window.addEventListener('resize', () => charts.forEach(chart => chart.resize()));
})();
