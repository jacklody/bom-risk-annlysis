(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var orange = style.getPropertyValue('--orange').trim();
  var yellow = style.getPropertyValue('--yellow').trim();
  var green = style.getPropertyValue('--green').trim();
  var red = style.getPropertyValue('--red').trim();

  // --- Chart 1: Risk Overview Comparison ---
  var chart1 = echarts.init(document.getElementById('chart-risk-overview'), null, { renderer: 'svg' });
  chart1.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      appendToBody: true
    },
    legend: {
      data: ['GC-WPFB001', 'GC-WPIB0015'],
      top: 0,
      textStyle: { color: ink, fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: ['选型Orange', '选型Yellow', '交付Yellow', '高容MLCC', 'MLCC总数'],
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: muted, fontSize: 11, interval: 0, rotate: 15 }
    },
    yAxis: {
      type: 'value',
      name: '数量',
      nameTextStyle: { color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: muted },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    series: [
      {
        name: 'GC-WPFB001',
        type: 'bar',
        data: [0, 4, 3, 0, 0],
        itemStyle: { color: accent2, borderRadius: [4, 4, 0, 0] },
        barWidth: '30%'
      },
      {
        name: 'GC-WPIB0015',
        type: 'bar',
        data: [2, 14, 20, 1, 12],
        itemStyle: { color: accent, borderRadius: [4, 4, 0, 0] },
        barWidth: '30%'
      }
    ]
  });
  window.addEventListener('resize', function() { chart1.resize(); });

  // --- Chart 2: Delivery Risk Category Distribution (GC-WPIB0015) ---
  var chart2 = echarts.init(document.getElementById('chart-delivery-category'), null, { renderer: 'svg' });
  chart2.setOption({
    animation: false,
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}项 ({d}%)',
      appendToBody: true
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      textStyle: { color: ink, fontSize: 12 },
      itemWidth: 12,
      itemHeight: 12
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['38%', '50%'],
      avoidLabelOverlap: true,
      label: {
        show: true,
        formatter: '{b}\n{c}项',
        color: ink,
        fontSize: 11
      },
      labelLine: { length: 10, length2: 8 },
      data: [
        { value: 8, name: 'analog_ic (运放/逻辑/光耦/接口)', itemStyle: { color: accent } },
        { value: 4, name: 'power_ic (LDO/驱动IC)', itemStyle: { color: accent2 } },
        { value: 1, name: 'power_module (PIM模块)', itemStyle: { color: orange } },
        { value: 1, name: 'high_cap_mlcc (高容MLCC)', itemStyle: { color: red } },
        { value: 1, name: 'memory (EEPROM)', itemStyle: { color: yellow } },
        { value: 1, name: 'mcu (主控MCU)', itemStyle: { color: green } },
        { value: 2, name: 'connector/inductor (单一来源)', itemStyle: { color: muted } },
        { value: 2, name: 'analog_ic (偏门品牌)', itemStyle: { color: accent + '99' } }
      ]
    }]
  });
  window.addEventListener('resize', function() { chart2.resize(); });
})();
