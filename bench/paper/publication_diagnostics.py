"""Matched historical Opus subset and fixed-protocol Qwen3.5 model-size curve."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator
from publication_data import C, ORDER, REGISTRY, summaries, COLORS
import plot_style as S
S.apply()
HERE = Path(__file__).resolve().parent

def main():
    cases = [c for c in C.cases() if C.get_row(REGISTRY['opus'], c) is not None]
    assert len(cases) == 45
    matched = summaries(['opus', *ORDER], cases)
    table = [r'\begin{tabular}{@{}lrrrr@{}}', r'\toprule',
             r'& & \multicolumn{2}{c}{Mean relative quality} & \\',
             r'\cmidrule(lr){3-4}',
             r'configuration & \shortstack{Overall\\score} & \shortstack{Published\\frontiers (15)} & \shortstack{Construction\\baselines (30)} & \shortstack{Valid\\fraction} \\', r'\midrule']
    for sid, r in matched.items():
        table.append(f"{r['label']} & {r['overall']['score']:.2f} & {r['p1']['mean']:.2f} & {r['p2']['mean']:.2f} & {r['valid']:.2f}" + r' \\')
    (HERE/'tables/opus_matched.tex').write_text('\n'.join(table+[r'\bottomrule',r'\end{tabular}'])+'\n')
    data = summaries();ids = ['qwen4','qwen9','qwen35'];xs = [4,9,27]
    fig, axes = plt.subplots(1,2,figsize=(S.WIDTH,2.55))
    for panel, label, color, fmt in [('p1','Published frontiers',S.METRICS['published'],'o-'),('p2','Construction baselines',S.METRICS['stand_in'],'s--')]:
        ys = [data[s][panel]['mean'] for s in ids]
        lo = [data[s][panel]['ci'][0] for s in ids];hi = [data[s][panel]['ci'][1] for s in ids]
        axes[0].errorbar(xs,ys,yerr=[[y-l for y,l in zip(ys,lo)],[h-y for h,y in zip(hi,ys)]],fmt=fmt,color=color,label=label,ms=S.MARKER,lw=S.LINE,capsize=S.CAP)
    axes[0].set_ylabel('Mean relative quality');axes[0].set_title('Construction quality')
    axes[1].plot(xs,[data[s]['valid'] for s in ids],'o-',color=S.METRICS['valid'],ms=S.MARKER,lw=S.LINE)
    axes[1].set_ylabel('Valid fraction');axes[1].set_ylim(0,1);axes[1].set_title('Valid responses')
    for ax in axes:
        ax.set_xscale('log');ax.set_xticks(xs,labels=['4B','9B','27B']);ax.xaxis.set_minor_locator(NullLocator());ax.set_xlabel('Qwen3.5 parameter count')
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y')
    S.legend(fig,*axes[0].get_legend_handles_labels(),ncol=2)
    fig.tight_layout(rect=[0,.18,1,1],pad=.85,w_pad=1.4)
    S.save(fig,'fig7_model_size')
    (HERE/'tables/opus_matched.json').write_text(json.dumps({'calls':45,'systems':matched},indent=2)+'\n')
    print('matched Opus subset',matched['opus']['p1']['n'],matched['opus']['p2']['n'])

if __name__ == '__main__':main()
