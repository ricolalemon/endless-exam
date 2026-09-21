"""Generate appendix catalogue, verified illustrations, cases and clean parameter tables."""
from pathlib import Path
from collections import defaultdict
from itertools import combinations, product
import hashlib
import json
import math
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent)]
import appendix_gen as A
import publication_data as P
from family_catalog import CORE_GROUPS, group_for
from run_ladder import extract_json
from report import load
from openceiling import FAMILIES, textbook_zero, effective_frontier, anchor

import plot_style as S
import visual_theme as T
S.apply()
OUT=HERE/'tables'; FIG=HERE/'figs/appendix'; FIG.mkdir(parents=True,exist_ok=True)
PRIMARY=T.PRIMARY; GOLD=T.OCHRE; GREY=T.NEUTRAL; INK=T.INK
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'text.color':INK,
                     'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
PAIRS=[('capset','corners'),('schur','apfree_q'),('spherical_code','labs'),
       ('heilbronn','degdiam'),('lineq','covering'),('matmul','mols'),('shannon','trifference')]
TITLES={'capset':'Cap sets','corners':'Corner-free sets','schur':'Schur colourings',
 'apfree_q':'Progression-free sets over finite fields','spherical_code':'Spherical codes',
 'labs':'Low-autocorrelation binary sequences','heilbronn':'Heilbronn triangles',
 'degdiam':'Degree--diameter graphs','lineq':'Linear-equation-free sets',
 'covering':'Covering designs','matmul':'Matrix multiplication',
 'mols':'Mutually orthogonal Latin squares','shannon':'Shannon codes','trifference':'Trifference codes'}
PARAM_NAMES={'capset':'Cap sets','corners':'Corners','schur':'Schur','apfree_q':r'$\mathbb F_q^n$ AP-free',
 'kissing':r'Spherical ($60^\circ$)','kissing_theta':'Spherical (variable)',
 'labs':'LABS','heilbronn':'Heilbronn (square)','heilbronn_shape':'Heilbronn (triangle)',
 'degdiam':'Degree--diameter','lineq':'Linear-equation-free','covering':'Covering designs',
 'matmul':'Matrix multiplication','mols':'MOLS','shannon':'Shannon','trifference':'Trifference'}
CONTEXT={
 'capset':'A large set must avoid every three-point arithmetic progression.',
 'corners':'A dense grid set must avoid a prescribed three-point pattern.',
 'schur':'No solution to $x+y=z$ may lie entirely within one colour class.',
 'apfree_q':'The ambient field changes which additive patterns a set must avoid.',
 'spherical_code':'Directions must remain separated while as many vectors as possible are packed.',
 'labs':'A binary sequence should have low autocorrelation at nonzero shifts.',
 'heilbronn':'Place the points so that the smallest triangle area is as large as possible.',
 'degdiam':'A sparse graph must keep all vertices close to one another.',
 'lineq':'A large integer set must avoid a specified linear relation.',
 'covering':'A small collection of blocks must cover every required subset.',
 'matmul':'A bilinear construction reduces the number of scalar multiplications.',
 'mols':'When any two squares are superimposed, every ordered pair of symbols must occur exactly once.',
 'shannon':'In the cycle model, adjacent symbols can be confused; every pair of codewords must have a coordinate that distinguishes them.',
 'trifference':'Every triple of distinct codewords must display all three symbols in at least $m$ coordinates.'}
SCALING={
 'capset':r'Increasing $d$ enlarges the ambient space to $3^d$ points. Products lift finite caps to higher dimensions.',
 'corners':r'Increasing $n$ enlarges the grid. Progression-free difference sets supply constructions at many sizes.',
 'schur':r'Increasing the number of colours $k$ gives new extremal targets. Recursive templates extend smaller colourings.',
 'apfree_q':r'Varying $q$ or $n$ changes the task. Products and algebraic constructions give candidates across dimensions.',
 'spherical_code':r'Dimension $d$ and the angle threshold control the packing problem. Lattices, orbits and signed supports supply constructions.',
 'labs':r'Increasing $N$ tests whether a construction retains a high merit factor at longer lengths.',
 'heilbronn':r'Increasing $n$ introduces more triangle constraints. The square and triangular domains are evaluated separately.',
 'degdiam':r'Varying degree $d$ and diameter $k$ generates new graph problems. Larger diameters test the growth of a construction.',
 'lineq':r'The coefficients $a,b$ select the relation; $n$ sets the interval size. Digit constructions can extend to larger intervals.',
 'covering':r'The parameters $(v,k,t)$ control the universe, block size and subsets to cover. Larger settings test covering efficiency.',
 'matmul':r'Changing the matrix dimensions $(n,m,p)$ defines new multiplication problems. Block composition extends schemes to larger products.',
 'mols':r'Changing the order $n$ changes the design problem. Algebraic constructions and combinations of smaller designs supply candidates.',
 'shannon':r'The cycle size $q$ and codeword length $d$ define the task. Finite factors give short certificates for very large products.',
 'trifference':r'Length $n$ and separation multiplicity $m$ define the task. Linear and concatenated codes admit compact certificates.'}
SOURCES={'capset':r'\citep{edel2004capset,karapetyan2023caps}',
 'corners':r'\citep{behrend1946}', 'schur':r'\citep{rowley2021templates,bengone2026schur}',
 'apfree_q':r'\citep{edel_caps,ellenberg2017capset}', 'spherical_code':r'\citep{zinoviev1999contact,ganzhinov2025lines,cohn2003kissing}',
 'labs':r'\citep{packebusch2016labs}', 'heilbronn':r'(definitions and references in Appendix~\ref{app:lit})',
 'degdiam':r'\citep{miller2013degdiam,comellas_degdiam}', 'lineq':r'\citep{behrend1946,ruzsa1993lineq}',
 'covering':r'\citep{gordon1995covering,ljcr}', 'matmul':r'\citep{strassen1969,fawzi2022alphatensor}',
 'mols':r'\citep{miller2024mols,abel2015mols}', 'shannon':r'\citep{lovasz1979shannon,polak2019shannon}',
 'trifference':r'\citep{bishnoi2024trifferent,bishnoi2025generalized}'}

def save(fig,name):
    for ext in ['pdf','png']:
        kw={'metadata':{'CreationDate':None}} if ext=='pdf' else {}
        fig.savefig(FIG/f'{name}.{ext}',dpi=180,facecolor='white',bbox_inches='tight',pad_inches=.04,**kw)
    plt.close(fig)

def canvas():
    f,a=plt.subplots(figsize=(1.5,1.15));a.set_aspect('equal');a.axis('off');return f,a

def grid(a,n,points):
    a.scatter(*zip(*product(range(n),repeat=2)),s=11,color=GREY,zorder=1)
    a.scatter(*zip(*points),s=33,color=PRIMARY,zorder=2)
    a.set(xlim=(-.5,n-.5),ylim=(-.5,n-.5))

def no_ap(S,q):
    points=set(map(tuple,S))
    return all(tuple((2*b-a)%q for a,b in zip(x,y)) not in points
               for x,y in product(points,repeat=2) if x!=y)

def illustrations():
    evidence={}
    for key,n in [('capset',3),('apfree_q',5)]:
        pts=list(product([0,1],repeat=2));assert no_ap(pts,n)
        f,a=canvas();grid(a,n,pts);save(f,key);evidence[key]={'q':n,'points':pts}
    pts=[(x,y) for x,y in product(range(5),repeat=2) if x-y in [0,1]]
    assert all(not ((x+t,y) in pts and (x,y+t) in pts) for x,y in pts for t in range(-5,6) if t)
    f,a=canvas();grid(a,5,pts);save(f,'corners');evidence['corners']={'n':5,'points':pts}
    colors=[0,1,1,0];assert all(colors[x-1]!=colors[y-1] or colors[x-1]!=colors[x+y-1]
                             for x in range(1,5) for y in range(1,5) if x+y<=4)
    f,a=canvas();a.set_aspect('auto')
    for i,c in enumerate(colors):
        a.add_patch(Rectangle((i,0),.9,.7,facecolor=[PRIMARY,GOLD][c]));a.text(i+.45,.35,str(i+1),ha='center',va='center',color='white',fontsize=10)
    a.set(xlim=(-.15,4),ylim=(-.4,1));save(f,'schur');evidence['schur']={'N':4,'colors':colors}
    f,a=canvas();a.add_patch(Circle((0,0),1,fill=False,edgecolor=GREY))
    for x,y in [(1,0),(0,1),(-1,0),(0,-1)]:a.annotate('',(x,y),(0,0),arrowprops={'arrowstyle':'->','color':PRIMARY,'lw':1.4})
    a.set(xlim=(-1.2,1.2),ylim=(-1.2,1.2));save(f,'spherical_code');evidence['spherical_code']={'vectors':[[1,0],[0,1],[-1,0],[0,-1]]}
    s=np.array([1,1,1,-1,-1,1,-1]);corr=[int(s[:-k]@s[k:]) for k in range(1,7)]
    f,a=plt.subplots(figsize=(1.5,1.15));a.bar(range(1,7),corr,color=PRIMARY);a.axhline(0,color=GREY,lw=.7);a.set(xticks=[1,3,6],yticks=[-1,0],ylim=(-1.25,.3));a.tick_params(labelsize=6);a.set_xlabel('shift',fontsize=7);save(f,'labs')
    evidence['labs']={'sequence':s.tolist(),'autocorrelations':corr,'merit_factor':49/(2*sum(x*x for x in corr))}
    pts=[(0,0),(1,0),(1,1),(0,1)];areas=[abs(np.linalg.det(np.array([np.subtract(b,a),np.subtract(c,a)])))/2 for a,b,c in combinations(pts,3)]
    assert min(areas)==.5
    f,a=canvas();a.add_patch(Rectangle((0,0),1,1,fill=False,edgecolor=GREY));a.fill([0,1,0],[0,0,1],color=PRIMARY,alpha=.12);a.scatter(*zip(*pts),s=25,color=PRIMARY);a.set(xlim=(-.15,1.15),ylim=(-.15,1.15));save(f,'heilbronn');evidence['heilbronn']={'points':pts,'min_area':.5}
    f,a=canvas();p=np.array([(math.cos(t),math.sin(t)) for t in np.linspace(math.pi/2,math.pi/2+2*math.pi,6)[:-1]])
    a.plot(*np.vstack([p,p[0]]).T,color=PRIMARY,lw=1.4);a.scatter(*p.T,color=PRIMARY,s=25);a.set(xlim=(-1.2,1.2),ylim=(-1.2,1.2));save(f,'degdiam')
    assert max(min(abs(i-j),5-abs(i-j)) for i,j in product(range(5),repeat=2))==2
    evidence['degdiam']={'graph':'cycle','vertices':5,'degree':2,'diameter':2}
    S=[1,2,4,8];assert all(x+y!=2*z for x,y,z in product(S,repeat=3) if len({x,y,z})>1)
    f,a=canvas();a.set_aspect('auto');a.plot([1,9],[0,0],color=GREY);a.scatter(range(1,10),[0]*9,color=GREY,s=10);a.scatter(S,[0]*4,color=PRIMARY,s=27)
    for x in S:a.text(x,-.18,str(x),ha='center',fontsize=7)
    a.set(xlim=(.5,9.5),ylim=(-.5,.5));save(f,'lineq');evidence['lineq']={'n':9,'a':1,'b':1,'set':S}
    blocks=[{0,1,2},{0,1,3},{0,2,3}];pairs=list(combinations(range(4),2));inc=np.array([[set(p)<=b for p in pairs] for b in blocks],int)
    assert inc.any(axis=0).all()
    f,a=plt.subplots(figsize=(1.5,1.15));a.imshow(inc,cmap=matplotlib.colors.ListedColormap(['white',PRIMARY]),vmin=0,vmax=1);a.set(xticks=range(6),xticklabels=['12','13','14','23','24','34'],yticks=range(3),yticklabels=['B1','B2','B3']);a.tick_params(length=0,labelsize=6);save(f,'covering');evidence['covering']={'v':4,'k':3,'t':2,'blocks':[sorted(b) for b in blocks]}
    def strassen(A,B):
        a,b,c,d=A.flat;e,f,g,h=B.flat
        m=[(a+d)*(e+h),(c+d)*e,a*(f-h),d*(g-e),(a+b)*h,(c-a)*(e+f),(b-d)*(g+h)]
        return np.array([[m[0]+m[3]-m[4]+m[6],m[2]+m[4]],[m[1]+m[3],m[0]-m[1]+m[2]+m[5]]])
    basis=[np.eye(4,dtype=int)[i].reshape(2,2) for i in range(4)]
    assert all(np.array_equal(strassen(a,b),a@b) for a,b in product(basis,repeat=2))
    f,a=canvas();a.set_aspect('auto');a.text(.15,.7,'2 × 2',ha='center',fontsize=10);a.text(.85,.7,'2 × 2',ha='center',fontsize=10);a.text(.5,.7,'×',ha='center',fontsize=12)
    a.annotate('7 products',(.5,.1),(.5,.55),ha='center',color=PRIMARY,fontsize=10,arrowprops={'arrowstyle':'->','color':PRIMARY});a.set(xlim=(-.2,1.2),ylim=(-.15,1));save(f,'matmul');evidence['matmul']={'dimensions':[2,2,2],'rank':7,'basis_pairs_verified':16}
    ls=[np.array([[(i+c*j)%3 for j in range(3)] for i in range(3)]) for c in [1,2]]
    assert len(set(zip(ls[0].flat,ls[1].flat)))==9
    f,axes=plt.subplots(1,2,figsize=(1.7,1.1))
    for a,L in zip(axes,ls):
        a.imshow(L,cmap=matplotlib.colors.ListedColormap(T.MOLS))
        for i,j in product(range(3),repeat=2):a.text(j,i,str(L[i,j]),ha='center',va='center',fontsize=7)
        a.axis('off')
    save(f,'mols');evidence['mols']={'squares':[L.tolist() for L in ls]}
    words=[(i,2*i%5) for i in range(5)]
    assert all(any(min((a-b)%5,(b-a)%5)>=2 for a,b in zip(x,y)) for x,y in combinations(words,2))
    f,a=canvas();grid(a,5,words);save(f,'shannon');evidence['shannon']={'q':5,'d':2,'words':words}
    words=[[0,0],[1,1],[2,2]];assert all(len(set(c))==3 for c in zip(*words))
    f,a=plt.subplots(figsize=(1.35,1.05));a.imshow(words,cmap=matplotlib.colors.ListedColormap([GREY,PRIMARY,GOLD]),vmin=0,vmax=2)
    for i,j in product(range(3),range(2)):a.text(j,i,str(words[i][j]),ha='center',va='center',color='white' if i==1 else INK,fontsize=9)
    a.axis('off');save(f,'trifference');evidence['trifference']={'n':2,'m':2,'words':words}
    return evidence

TOYCAP={'capset':r'$d=2$: four points','corners':r'$n=5$: nine points','schur':r'$k=2,\ N=4$',
 'apfree_q':r'$q=5,\ n=2$','spherical_code':r'$d=2$: four directions','labs':r'$N=7$: autocorrelation',
 'heilbronn':r'$n=4$: minimum area $1/2$','degdiam':r'$d=2,\ k=2,\ N=5$','lineq':r'$a=b=1,\ n=9$',
 'covering':r'Three blocks cover six pairs','matmul':r'Strassen: seven products','mols':r'Two squares of order three',
 'shannon':r'$C_5^2$: five codewords','trifference':r'$n=2,\ m=2$: three words'}

def reference(task):
    tier='T1' if task=='trifference' else 'A3';_,p=A.inst(tier,task,0);r=A.ref10(task,0,tier)
    F=FAMILIES[task];search=r['search'] if r else None;z=textbook_zero(F,p,search)
    baseline=z[0] if z else r['naive']
    if search is not None:baseline=(max if F.sense=='max' else min)(baseline,search)
    h,published=effective_frontier(F,p,r['naive'] if r else None,search);b,kind=anchor(F,p)
    ratio=baseline/h if F.sense=='max' else h/baseline
    return {'task':task,'params':p,'baseline':baseline,'search':search,'reference':h,'published':published,'anchor':b,'anchor_kind':kind,'baseline_ratio':ratio}

def catalogue():
    lines=[];records=[]
    for pair in PAIRS:
        lines.append(r'\appendixpage')
        for group in pair:
            lines += [r'\begin{minipage}{\linewidth}',rf'\catalogueheading{{{group}}}{{{TITLES[group]}}}',
                      CONTEXT[group]+r' '+SOURCES[group]+r'\par\smallskip',
                      r'\begin{minipage}[c]{.25\linewidth}\centering',
                      rf'\includegraphics[width=.92\linewidth,height=73pt,keepaspectratio]{{figs/appendix/{group}.pdf}}',
                      r'\par{\scriptsize '+TOYCAP[group]+r'}\end{minipage}\hfill',
                      r'\begin{minipage}[c]{.71\linewidth}']
            for task in CORE_GROUPS[group]:
                variant={'kissing':r'\textbf{Fixed angle.} ','kissing_theta':r'\textbf{Variable angle.} ',
                         'heilbronn':r'\textbf{Square.} ','heilbronn_shape':r'\textbf{Triangle.} '}.get(task,'')
                lines.append(variant+A.DEFINITIONS[task]+r'\par\smallskip')
            lines += [r'\end{minipage}\par\smallskip',r'\textbf{Parameters and scaling.} '+SCALING[group],
                      r'\begin{resultbox}[top=4pt,bottom=4pt]\small']
            for task in CORE_GROUPS[group]:
                d=reference(task);records.append(d)
                params=A.math_params(d['params'])
                if task=='heilbronn_shape':params=rf"$n={d['params']['n']}$, triangular domain (Table~\ref{{tab:triangle_domains}})"
                kind={'bound':'proven bound','trivial':'trivial bound','conjecture':'conjectured target'}.get(d['anchor_kind'],d['anchor_kind'])
                lines += [rf'\textbf{{Evaluated example:}} {params}.\par',
                          r'\begin{tabularx}{\linewidth}{@{}XXXXX@{}}',
                          r'Baseline & 10 s search & Reference & Bound or target & Baseline\textquotesingle s relative quality \\',
                          ' & '.join(A.math_number(d[k]) for k in ['baseline','search','reference','anchor'])+f" & {d['baseline_ratio']:.3f}"+r' \\',
                          r'\end{tabularx}\par{\scriptsize Reference: '+('published frontier' if d['published'] else 'construction baseline')+'; '+kind+r'.}\par\smallskip']
            lines += [r'\end{resultbox}\end{minipage}',r'\par\vfill']
    (OUT/'family_catalogue.tex').write_text('\n'.join(lines)+'\n')
    return records

def table_start(cols,header,caption,label):
    return [rf'\begin{{longtable}}{{{cols}}}',rf'\caption{{{caption}}}\label{{{label}}}\\',
            r'\toprule',header+r' \\',r'\midrule\endfirsthead',r'\toprule',header+r' \\',r'\midrule\endhead',
            r'\bottomrule\endfoot']

def parameters():
    grouped=defaultdict(list)
    for c in P.C.cases():grouped[(c['family'],json.dumps(c['params'],sort_keys=True))].append(c)
    assert len(grouped)==69 and all(len(rows)==1 for rows in grouped.values())
    triangles={};triangle_rows=[];records=[]
    lines=table_start(r'@{}P{.30\linewidth}P{.67\linewidth}@{}','Family & Parameters',
                      'The 69 instances in the main evaluation. Each configuration contributes one response per instance.','tab:tiers')
    for pair in PAIRS:
        for g in pair:
            for (task,key),calls in grouped.items():
                if task not in CORE_GROUPS[g]:continue
                p=json.loads(key);display=dict(p)
                if 'T' in display:
                    ident=len(triangles)+1;triangles[key]=ident
                    triangle_rows.append((ident,p['T']));display.pop('T')
                params=A.math_params(display)
                if 'T' in p:params+=rf', $T_{{{triangles[key]}}}$'
                name=PARAM_NAMES[task]
                lines.append(f'{name} & {params}'+r' \\')
                records.append({'task':task,'params':p,'calls':len(calls),'source_cases':[{k:c[k] for k in ['tier','seed']} for c in calls]})
            lines.append(r'\addlinespace[4pt]')
    lines += [r'\end{longtable}'];(OUT/'formal_parameters.tex').write_text('\n'.join(lines)+'\n')
    tri=table_start(r'@{}lP{.27\linewidth}P{.27\linewidth}P{.27\linewidth}@{}',r'Domain & Vertex 1 & Vertex 2 & Vertex 3',
                    'Triangular domains used in the main evaluation. Coordinates are integers.','tab:triangle_domains')
    for i,vertices in triangle_rows:tri.append(f'$T_{{{i}}}$ & '+' & '.join(f'$({x},{y})$' for x,y in vertices)+r' \\')
    tri += [r'\end{longtable}'];(OUT/'triangle_domains.tex').write_text('\n'.join(tri)+'\n')
    aux=table_start(r'@{}P{.30\linewidth}lP{.56\linewidth}@{}','Family & Tier & Representative parameters',
                    'Three representative smaller-instance draws per tier, in seed order 0, 1, 2. Trifference uses the lengths listed in the main evaluation table.','tab:aux_parameters')
    auxrecords=[]
    for pair in PAIRS:
        for g in pair:
            for task in CORE_GROUPS[g]:
                if task=='trifference':continue
                for tier in ['A1','A2']:
                    ps=[A.inst(tier,task,s)[1] for s in range(3)]
                    shown=[]
                    for p in ps:
                        d={k:v for k,v in p.items() if k!='T'};shown.append(A.math_params(d))
                    variant={'kissing':r' (60$^\circ$)','kissing_theta':' (variable angle)','heilbronn':' (square)','heilbronn_shape':' (triangle)'}.get(task,'')
                    aux.append(f'{TITLES[g]+variant if tier=="A1" else ""} & {tier} & '+r'; '.join(shown)+r' \\')
                    auxrecords.append({'task':task,'tier':tier,'draws':ps})
                aux.append(r'\addlinespace[4pt]')
    aux += [r'\end{longtable}'];(OUT/'auxiliary_parameters.tex').write_text('\n'.join(aux)+'\n')
    return {'formal':records,'auxiliary':auxrecords,'triangle_domains':triangle_rows}

def rank3(G):
    G=np.array(G,dtype=int)%3;r=0
    for j in range(G.shape[1]):
        piv=next((i for i in range(r,len(G)) if G[i,j]),None)
        if piv is None:continue
        G[[r,piv]]=G[[piv,r]];G[r]=G[r]*pow(int(G[r,j]),-1,3)%3
        for i in range(len(G)):
            if i!=r:G[i]=(G[i]-G[i,j]*G[r])%3
        r+=1
        if r==len(G):break
    return r

def chain_plot(name,boxes,footer,value_fontsize=11):
    fig,ax=plt.subplots(figsize=(5.5,1.35));ax.set_position([0,0,1,1]);ax.axis('off')
    n=len(boxes)
    for i,(title,value) in enumerate(boxes):
        x=i/n+.02;w=.96/n-.02
        ax.add_patch(Rectangle((x,.34),w,.52,facecolor=T.PAPER,edgecolor=PRIMARY,lw=.7))
        ax.text(x+w/2,.71,title,ha='center',va='center',fontsize=8)
        ax.text(x+w/2,.49,value,ha='center',va='center',fontsize=value_fontsize,fontweight='bold',color=PRIMARY)
        if i<n-1:ax.text((x+w+(i+1)/n+.02)/2,.6,'×' if i==0 else '=',ha='center',va='center',fontsize=12)
    ax.text(.5,.12,footer,ha='center',fontsize=8,color=INK);save(fig,name)

def cases():
    from candidate_families import shannon_second
    s=P.REGISTRY['astra_high'];refs,rows=load('L4');row=rows[s[1],s[3]+'#L4']['capset',0]
    cap=extract_json(row['content']);factors=[tuple(tuple(map(int,w)) for w in f) for f in cap['product']]
    assert row['feasible'] and len(factors)==2 and factors[0]==factors[1]
    assert all(len(f)==112 and len(f[0])==6 and no_ap(f,3) for f in factors)
    assert row['objective']==112**2==12544
    rr=refs['capset',0]
    cap_reference=effective_frontier(FAMILIES['capset'],row['params'],rr['naive'],rr['objective'])[0]
    assert cap_reference==12928
    chain_plot('case_capset',[('First cap','112 points'),('Second cap','112 points'),('Product','12,544 points')],
               '6 dimensions + 6 dimensions = 12 dimensions')
    case=next(c for c in P.C.cases() if (c['family'],c['tier'],c['seed'])==('shannon','A3',0))
    qrow=P.C.get_row(P.REGISTRY['qwen38'],case);qans=extract_json(qrow['content'])
    qs=[(len(f['words']),len(f['words'][0]),f['power']) for f in qans['factors']]
    assert qs==[(343,5,4),(10,2,2)] and qrow['feasible']
    ok,obj=shannon_second(case['params'],qans);assert ok and obj==qrow['objective']==343**4*10**2
    arow=P.C.get_row(P.REGISTRY['astra_medium'],case);assert arow['objective']==10**12
    drow=P.C.get_row(P.REGISTRY['deepseek_low'],case)
    assert drow['feasible'] and drow['objective']==arow['objective']
    chain_plot('case_shannon',[('Four length-5 factors',r'$343^4$ codewords'),('Two length-2 factors',r'$10^2$ codewords'),('Product',r'$343^4\,10^2$ codewords')],
               'Codeword length: 4 × 5 + 2 × 2 = 24; each factor is checked separately',value_fontsize=10)
    case=next(c for c in P.C.cases() if (c['family'],c['tier'],c['seed'])==('trifference','T1',0))
    trow=P.C.get_row(P.REGISTRY['astra_high'],case);tans=extract_json(trow['content']);G=np.array([list(map(int,s)) for s in tans['linear_code']])
    assert trow['feasible'] and G.shape==(10,64) and rank3(G)==10 and trow['objective']==3**10==59049
    fig,ax=plt.subplots(figsize=(5.5,1.55));ax.imshow(G,cmap=matplotlib.colors.ListedColormap([T.MATRIX_ZERO,PRIMARY,GOLD]),vmin=0,vmax=2,aspect='auto',interpolation='nearest')
    ax.set(xticks=[0,15,31,47,63],xticklabels=[1,16,32,48,64],yticks=[0,4,9],yticklabels=[1,5,10],xlabel='Coordinate',ylabel='Generator row')
    ax.tick_params(labelsize=7);ax.set_title('The submitted 10 × 64 generator matrix',fontsize=9)
    for i,col in enumerate([T.MATRIX_ZERO,PRIMARY,GOLD]):ax.plot([],[],marker='s',linestyle='',color=col,label=str(i))
    ax.legend(ncol=3,loc='upper center',bbox_to_anchor=(.5,-.3),frameon=False,fontsize=7);save(fig,'case_trifference')
    history=json.loads((OUT/'historical_progress.json').read_text())
    fig,axes=plt.subplots(1,2,figsize=(5.5,1.6),gridspec_kw={'width_ratios':[2.2,1]})
    rs=history['rows'];xs=list(range(3));ys=[r['ratio'] for r in rs]
    axes[0].plot(xs,ys,'o-',color=GOLD);axes[0].axhline(1,color=T.MUTED,ls='--',lw=.8)
    for x,y,r in zip(xs,ys,rs):axes[0].annotate(f"{r['value']:,}",(x,y),xytext=(0,8),textcoords='offset points',ha='center',fontsize=8)
    axes[0].set(xticks=xs,xticklabels=['Extension','Template','Shifted'],ylim=(.99,1.09),ylabel='Relative quality')
    axes[1].bar(xs,[r['breakthrough'] for r in rs],color=[GREY,PRIMARY,PRIMARY]);axes[1].set(xticks=xs,xticklabels=['E','T','S'],yticks=[0,1],ylim=(0,1.25),ylabel='Binary breakthrough')
    for ax in axes:ax.tick_params(labelsize=7);ax.spines[['top','right']].set_visible(False)
    fig.tight_layout();save(fig,'case_schur')
    nums=[r'\newcommand{\CaseCapRatio}{'+f'{12544/12928:.3f}'+'}',
          r'\newcommand{\CaseShannonReference}{'+f"{case_ref('shannon','A3',0):,}"+'}',
          r'\newcommand{\CaseShannonRatio}{'+f"{qrow['objective']/case_ref('shannon','A3',0):.3f}"+'}',
          r'\newcommand{\CaseShannonGain}{'+f"{100*(qrow['objective']/arow['objective']-1):.1f}"+'}']
    (OUT/'appendix_case_numbers.tex').write_text('\n'.join(nums)+'\n')
    def source(sid,tier,family,block):
        return P.selected_source(sid,tier,family,0,block)
    return {'capset':{'params':row['params'],'factor_sizes':[112,112],'objective':12544,'reference':cap_reference,'source':source('astra_high','L4','capset','core')},
            'shannon':{'params':qrow['params'],'factors':qs,'objective':qrow['objective'],'reference':case_ref('shannon','A3',0),'comparison_objective':arow['objective'],
                       'source':source('qwen38','A3','shannon','codes'),'comparison_sources':[source('astra_medium','A3','shannon','codes'),source('deepseek_low','A3','shannon','codes')]},
            'trifference':{'params':trow['params'],'generator':G.tolist(),'rank':10,'objective':59049,'reference':case_ref('trifference','T1',0),'source':source('astra_high','T1','trifference','codes')},'schur':history}

def case_ref(family,tier,seed):
    c=next(c for c in P.C.cases() if (c['family'],c['tier'],c['seed'])==(family,tier,seed))
    r=json.loads((P.ROOT/c['reference_path']).read_text())
    return effective_frontier(FAMILIES[family],c['params'],r['naive'],r['search'])[0]

def ladder_tables():
    old=(OUT/'ladder_table.tex').read_text().splitlines()
    rows=[s for s in old if ' & ' in s and not s.startswith('family')]
    parsed=[[c.strip() for c in s.removesuffix(r'\\').split('&')] for s in rows]
    assert len(parsed)==28 and all(len(r)==9 for r in parsed)
    title={'kissing':r'spherical codes ($60^\circ$)','AP-free (control)':'integer AP-free sets'}
    a=table_start(r'@{}P{.29\linewidth}P{.38\linewidth}rr@{}','Family & Parameters & Reference & Baseline',
                  'Problem-size experiments: instances and references. An asterisk marks a construction baseline.','tab:ladder_parameters')
    for r in parsed:a.append(' & '.join([title.get(r[0],r[0]),*r[2:5]])+r' \\')
    a.append(r'\end{longtable}');(OUT/'ladder_parameters.tex').write_text('\n'.join(a)+'\n')
    b=table_start(r'@{}P{.23\linewidth}lrrrr@{}',r'Family & Size & \shortstack{Qwen3.8-27B\\high} & \shortstack{GPT-5.6 Luna\\high} & \shortstack{DeepSeek V4.1\\Flash low} & \shortstack{GPT-6 Astra\\high}',
                  'Mean relative quality at each problem size. Parentheses give valid responses out of the total; means include zero scores.','tab:ladder')
    for r in parsed:
        key='d' if r[0] in ('cap set','kissing') else 'k' if r[0]=='Schur' or 'graphs' in r[0] else 'v' if r[0]=='covering' else 'n'
        size=next(part.strip() for part in r[2].split(',') if part.strip().startswith(key+'='))
        b.append(' & '.join([title.get(r[0],r[0]),'$'+size+'$',*r[5:]])+r' \\')
    b.append(r'\end{longtable}');(OUT/'ladder_scores.tex').write_text('\n'.join(b)+'\n')
    return parsed

def code_details():
    cases,rows=P.code_data()
    for family in ['shannon','trifference']:
        selected=[c for c in cases if c['family']==family]
        headers=[rf"$({c['params']['q']},{c['params']['d']})$" if family=='shannon' else str(c['params']['n']) for c in selected]
        lines=[r'\begin{tabularx}{\linewidth}{@{}Xrrrr@{}}',r'\toprule','Model / effort & '+' & '.join(headers)+r' \\',r'\midrule']
        for sid in P.ORDER:
            cells=[]
            for c in selected:
                r=next(r for r in rows if r['system']==sid and (r['tier'],r['family'],r['seed'])==(c['tier'],c['family'],c['seed']))
                value='$<0.001$' if 0<r['ratio']<.001 else f"{r['ratio']:.3f}"
                cells.append(value+('' if r['valid'] else r'$^{\dagger}$'))
            lines.append(P.REGISTRY[sid][2]+' & '+' & '.join(cells)+r' \\')
        lines += [r'\bottomrule',r'\end{tabularx}']
        (OUT/f'code_detail_{family}.tex').write_text('\n'.join(lines)+'\n')

def main():
    data={'illustrations':illustrations(),'catalogue_examples':catalogue(),'parameters':parameters(),'cases':cases(),'ladder_rows':ladder_tables()}
    (OUT/'appendix_catalogue_data.json').write_text(json.dumps(data,indent=2)+'\n')
    code_details()
    import fig_ladder as L
    all_fams=list(L.FAMS)
    L.main([f for f in all_fams if f[0] in ['schur','covering','apfree']], 'appendix/ladder_designs')
    L.main([f for f in all_fams if f[0]=='degdiam:M'], 'appendix/ladder_quartic')
    print('Generated 14 checked illustrations, four cases, 16 catalogue examples and 69 formal parameter rows.')

if __name__=='__main__':main()
