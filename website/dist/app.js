const $ = (id) => document.getElementById(id);
const slider = $('ratio-slider');
const curve = Array.from({length:81}, (_, i) => {const r=i/40;return [30+r*211.5,202-86*r];});
const curvePath = curve.map((p,i)=>(i?'L':'M')+p.join(' ')).join(' ');
$('quality-curve').setAttribute('d',curvePath);
$('quality-area').setAttribute('d',curvePath+'L453 214H30Z');
function updateRatio() {
  const ratio = Number(slider.value);
  $('ratio-value').textContent = ratio.toFixed(2);
  slider.setAttribute('aria-valuetext', `${ratio.toFixed(2)} times the published reference`);
  const x = 30 + ratio * 211.5;
  const y = 202 - 86 * ratio;
  for (const id of ['score-point', 'point-halo']) { $(id).setAttribute('cx', x); $(id).setAttribute('cy', y); }
  $('point-guide').setAttribute('x1', x); $('point-guide').setAttribute('x2', x); $('point-guide').setAttribute('y1', y);
  $('ratio-explanation').textContent = ratio > 1 ? `${Math.round((ratio - 1) * 100)}% above the published reference (relative quality = ${ratio.toFixed(2)}).` : ratio === 1 ? 'Equal to the published reference (relative quality = 1.00).' : `${Math.round(ratio * 100)}% of the published reference objective (relative quality = ${ratio.toFixed(2)}).`;
}
slider.addEventListener('input', updateRatio); updateRatio();

fetch('results.json', {cache: 'no-store'}).then(r => { if (!r.ok) throw Error('Results unavailable'); return r.json(); }).then(data => {
  const body = $('leaderboard-body');
  const buttons = [...document.querySelectorAll('.track-switch button')];
  buttons.forEach(button => {
    button.querySelector('span').textContent = data.rows.filter(row => row.track === button.dataset.track).length;
  });
  function showTrack(track) {
    body.replaceChildren();
    const rows = data.rows.filter(row => row.track === track).sort((a, b) => b.score - a.score);
    buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.track === track)));
    $('leaderboard-scope').textContent = `${data.families} families · ${data.instances} instances · ${rows.length} configurations`;
    $('track-protocol').textContent = data.tracks[track].protocol;
    $('leaderboard-caption').textContent = `${data.tracks[track].label}: overall results on ${data.instances} distinct instances`;
    $('token-description').textContent = track === 'tool-assisted'
      ? 'Mean output tokens per instance, including reasoning across all model turns.'
      : 'Mean output tokens per instance, including reasoning.';
    $('token-unknown-note').hidden = !rows.some(row => row.token_usage_is_lower_bound);
    rows.forEach((row, i) => {
      const tr = document.createElement('tr'); tr.setAttribute('role', 'row'); if (i === 0) tr.className = 'leader-row';
      const tokens = Math.round(row.mean_output_tokens).toLocaleString('en-US');
      const cells = [[String(i + 1).padStart(2, '0'), 'rank'], [row.model, 'model'], [row.effort, 'effort'], [row.score.toFixed(2), 'numeric score-cell', 'Score'], [tokens, 'numeric token-col', 'Tokens / instance'], [`${row.valid.toFixed(1)}%`, 'numeric valid-col', 'Valid']];
      cells.forEach(([text, cls, mobileLabel]) => {
        const td = document.createElement('td'); td.className = cls; td.setAttribute('role', 'cell');
        const value = document.createElement('span'); value.className = 'cell-value'; value.textContent = text; td.append(value);
        if (mobileLabel) {
          const label = document.createElement('span'); label.className = 'mobile-cell-label';
          label.textContent = mobileLabel; label.setAttribute('aria-hidden', 'true'); td.append(label);
        }
        if (cls.includes('token-col')) {
          td.title = `${row.output_tokens.toLocaleString('en-US')} reported output tokens across ${data.instances} instances. Complete usage for ${row.token_usage_complete_instances}/${data.instances}.`;
          if (row.token_usage_is_lower_bound) {
            const star = document.createElement('sup'); star.className = 'usage-star'; star.textContent = '*'; star.setAttribute('aria-hidden', 'true'); value.append(star);
            td.setAttribute('aria-label', `${tokens} output tokens per instance, lower bound; some usage was not reported.`);
          }
        }
        tr.append(td);
      });
      body.append(tr);
    });
  }
  buttons.forEach(button => button.addEventListener('click', () => showTrack(button.dataset.track)));
  showTrack('tool-free');
  document.dispatchEvent(new Event('endless:results-ready'));
  // Resolve the illustration anchor after the asynchronous table has its height.
  if (location.hash === '#constructions' || location.hash === '#play') {
    requestAnimationFrame(() => window.scrollTo({top: $('constructions').offsetTop - 28, behavior: 'instant'}));
  }
}).catch(() => { const td = document.createElement('td'); td.colSpan = 6; td.className = 'error'; td.textContent = 'Results could not be loaded. The complete table is available in the paper.'; $('leaderboard-body').replaceChildren(Object.assign(document.createElement('tr'), {})); $('leaderboard-body').firstChild.append(td); });

$('copy-command').addEventListener('click',async()=>{const text='python bench/exam.py verify \\\n  --family capset \\\n  --params \'{"d":2}\' \\\n  --answer examples/capset.json';try{await navigator.clipboard.writeText(text);$('copy-command').textContent='Copied';$('copy-status').textContent='Verification command copied.';setTimeout(()=>{$('copy-command').textContent='Copy';},2200);}catch{$('copy-status').textContent='Copy unavailable. Select and copy the command above.';$('copy-command').textContent='Select code';const r=document.createRange();r.selectNodeContents(document.querySelector('.code-card pre'));const s=window.getSelection();s.removeAllRanges();s.addRange(r);}});
