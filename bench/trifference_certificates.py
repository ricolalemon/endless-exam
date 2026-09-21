"""Exact trifference certificates, independently checked without materialising all strings.

For rank-k G and nonzero z, restrict G to columns on z^perp. The code is
m-trifferent iff its distance is >=m and every such restriction has rank k-1
and distance >=m. We check projective z only. For m<=3, RREF distance testing
needs only combinations supported on at most m-1 pivot positions.

Concatenation uses an actually checked inner code and a Reed-Solomon [N,K]
outer code: three outer words have at least N-3K+3 all-distinct coordinates.
This certifies at least inner_m*(N-3K+3) separating positions and q**K words.
"""
from itertools import product

MAX_RANK = 12
MAX_INPUT_ROWS = 16
MAX_LENGTH = 1024

HINT = ('Certified forms allowed in addition to literal lists and the legacy linear form: '
        '{"linear_code": [g1,...,gs]} supplies 1..16 ternary generator rows of the required length. '
        'Actual rank must be at most 12; the exact number of words is 3^rank. '
        'The full three-word property is checked algebraically without expanding all strings; '
        'this form supports separation multiplicity m=1,2,3. '
        '{"rs_concat": {"inner": X, "inner_n": a, "inner_m": b, "field": [c0,...,cr], '
        '"length": N, "dimension": K}} describes a checked inner ternary code X of length a '
        'and multiplicity b, with exactly q=3^r words. X may be a literal list, legacy linear, '
        'or linear_code, but not another rs_concat. The field polynomial has coefficients '
        '0,1,2 in increasing degree order, is monic, irreducible over F3, and has degree r<=12. '
        'The outer code evaluates every polynomial of degree less than K at the first N distinct '
        'field elements (base-3 coefficient order); map each field symbol to the corresponding '
        'inner word in lexicographic order. Require 1<=K<=N<=q, a*N<=n, and '
        'b*(N-3*K+3)>=m. Pad final words with zeroes to length n. Its exact size is q^K; '
        'there is no 6561-word limit on certified forms. All parameters, inner properties and '
        'field irreducibility are verified. No claimed counts or arbitrary programs are accepted.')


def add(a,b):
    a1,a2=a;b1,b2=b
    az=~(a1|a2);bz=~(b1|b2)
    return ((a1&bz)|(b1&az)|(a2&b2), (a2&bz)|(b2&az)|(a1&b1))


def rref(rows):
    """Incremental GF3 elimination using disjoint bit planes."""
    basis={}
    for a,b in rows:
        for pivot,(c,d) in sorted(basis.items()):
            if (a>>pivot)&1:a,b=add((a,b),(d,c))
            elif (b>>pivot)&1:a,b=add((a,b),(c,d))
        nz=a|b
        if not nz:continue
        pivot=(nz&-nz).bit_length()-1
        if (b>>pivot)&1:a,b=b,a
        for j,(c,d) in list(basis.items()):
            if (c>>pivot)&1:basis[j]=add((c,d),(b,a))
            elif (d>>pivot)&1:basis[j]=add((c,d),(a,b))
        basis[pivot]=(a,b)
    return [v for _,v in sorted(basis.items())]


def distance_at_least(basis,m):
    if m==1:return True
    if any((a|b).bit_count()<m for a,b in basis):return False
    if m==3:
        for i,a in enumerate(basis):
            for b in basis[i+1:]:
                if (lambda v:(v[0]|v[1]).bit_count())(add(a,b))<3:return False
                if (lambda v:(v[0]|v[1]).bit_count())(add(a,b[::-1]))<3:return False
    return True


def _rows(p,ans):
    if set(ans)!={'linear_code'}:raise ValueError('expected linear_code')
    rows=ans['linear_code'];n=p['n']
    if not isinstance(rows,list) or not 1<=len(rows)<=MAX_INPUT_ROWS:raise ValueError('expected 1..16 generator rows')
    if any(not isinstance(w,str) or len(w)!=n or set(w)-set('012') for w in rows):raise ValueError('generator row has wrong length or alphabet')
    return rows


def linear_verify(p,ans):
    try:rows=_rows(p,ans)
    except (ValueError,TypeError,KeyError) as e:return False,0,str(e)
    if p['m'] not in (1,2,3):return False,0,'linear_code supports m=1,2,3'
    basis=rref([(sum((c=='1')<<i for i,c in enumerate(w)),sum((c=='2')<<i for i,c in enumerate(w))) for w in rows])
    k=len(basis);m=p['m']
    if k>MAX_RANK:return False,0,'linear rank exceeds certified algebraic budget (12)'
    if not distance_at_least(basis,m):return False,0,'linear code has a word of weight below m'
    full=(1<<p['n'])-1
    def tails(i,a):
        if i==k:
            yield a;return
        yield from tails(i+1,a)
        yield from tails(i+1,add(a,basis[i]))
        yield from tails(i+1,add(a,basis[i][::-1]))
    for first in range(k):
        for a,b in tails(first+1,basis[first]):
            zero=full^(a|b)
            restricted=rref([(c&zero,d&zero) for c,d in basis])
            if len(restricted)!=k-1:return False,0,'a hyperplane restriction has deficient rank'
            if not distance_at_least(restricted,m):return False,0,'a hyperplane restriction has distance below m'
    return True,3**k,''


# Polynomial arithmetic is over F3, low coefficient first.
def trim(a):
    a=list(a)
    while a and not a[-1]:a.pop()
    return a


def remainder(a,b):
    a=trim(a);b=trim(b)
    if not b:raise ValueError('division by zero polynomial')
    while len(a)>=len(b):
        t=a[-1]*b[-1]%3;offset=len(a)-len(b)
        for j,v in enumerate(b):a[offset+j]=(a[offset+j]-t*v)%3
        a=trim(a)
    return a


def mulmod(a,b,f):
    c=[0]*(len(a)+len(b))
    for i,x in enumerate(a):
        for j,y in enumerate(b):c[i+j]=(c[i+j]+x*y)%3
    return remainder(c,f)


def sub(a,b):
    return trim([((a[i] if i<len(a) else 0)-(b[i] if i<len(b) else 0))%3 for i in range(max(len(a),len(b)))])


def irreducible(f):
    """Rabin criterion using Frobenius powers and polynomial gcds."""
    r=len(f)-1;x=remainder([0,1],f);h=x
    divisors={r//p for p in range(2,r+1) if r%p==0 and all(p%d for d in range(2,int(p**.5)+1))}
    for i in range(1,r+1):
        h=mulmod(mulmod(h,h,f),h,f)
        if i in divisors:
            a,b=f,sub(h,x)
            while b:a,b=b,remainder(a,b)
            if len(a)>1:return False
    return h==x


def verify(p,ans,inner_check):
    n,m=p.get('n'),p.get('m')
    if type(n)is not int or type(m)is not int or not 1<=m<=n<=MAX_LENGTH:return False,0,'unsupported certified parameters'
    if not isinstance(ans,dict):return False,0,'expected certificate'
    if set(ans)=={'linear_code'}:return linear_verify(p,ans)
    if set(ans)!={'rs_concat'}:return False,0,'unknown certificate'
    spec=ans['rs_concat']
    if not isinstance(spec,dict) or set(spec)!={'inner','inner_n','inner_m','field','length','dimension'}:return False,0,'malformed concatenation certificate'
    a,b,N,K=(spec[x] for x in ('inner_n','inner_m','length','dimension'))
    if any(type(v)is not int for v in (a,b,N,K)) or not 1<=b<=a<=n or not 1<=K<=N or a*N>n:return False,0,'invalid concatenation dimensions'
    if b*(N-3*K+3)<m:return False,0,'outer distance does not certify the requested separation'
    f=spec['field']
    if not isinstance(f,list) or not 2<=len(f)<=13 or any(type(c)is not int or c not in (0,1,2) for c in f) or f[-1]!=1:return False,0,'invalid field polynomial'
    inner=spec['inner']
    if isinstance(inner,dict) and (len(inner)!=1 or next(iter(inner)) not in ('linear','linear_code')):return False,0,'inner certificate nesting is not admitted'
    ok,q,msg=inner_check({'n':a,'m':b,'representation':'certified'},inner)
    if not ok:return False,0,'inner code: '+msg
    if q!=3**(len(f)-1) or N>q:return False,0,'inner cardinality or outer length does not match the field'
    if not irreducible(f):return False,0,'reducible field polynomial'
    return True,q**K,''


# Independent checker: interleaved two-bit field elements, conventional Gauss-Jordan,
# and monic trial division (not the primary Frobenius/gcd irreducibility check).
def second_linear(p,answer):
    if not isinstance(answer,dict) or list(answer)!=['linear_code']:return False,0
    strings=answer['linear_code'];n=p['n'];m=p['m']
    if m not in (1,2,3) or not isinstance(strings,list) or not 1<=len(strings)<=16:return False,0
    if any(not isinstance(w,str) or len(w)!=n or any(c not in '012' for c in w) for w in strings):return False,0
    low=sum(1<<(2*i) for i in range(n));full=low|(low<<1)
    def plus(x,y):
        a=x&low;b=(x>>1)&low;c=y&low;d=(y>>1)&low
        az=low^(a|b);bz=low^(c|d)
        return ((a&bz)|(c&az)|(b&d)) | (((b&bz)|(d&az)|(a&c))<<1)
    def neg(x):return ((x&low)<<1)|((x>>1)&low)
    def echelon(vectors):
        vectors=[v for v in vectors if v];row=0
        while row<len(vectors):
            positions=0
            for v in vectors[row:]:positions|=v|(v>>1)
            positions&=low
            if not positions:break
            pivot=(positions&-positions).bit_length()-1
            chosen=next(i for i in range(row,len(vectors)) if (vectors[i]>>pivot)&3)
            vectors[row],vectors[chosen]=vectors[chosen],vectors[row]
            if ((vectors[row]>>pivot)&3)==2:vectors[row]=neg(vectors[row])
            for j in range(len(vectors)):
                if j==row:continue
                val=(vectors[j]>>pivot)&3
                if val:vectors[j]=plus(vectors[j],neg(vectors[row]) if val==1 else vectors[row])
            row+=1
            vectors=vectors[:row]+[v for v in vectors[row:] if v]
        return vectors[:row]
    def weight(x):return ((x|(x>>1))&low).bit_count()
    def distance_ok(vectors):
        if any(weight(v)<m for v in vectors):return False
        if m==3:
            for i,u in enumerate(vectors):
                for v in vectors[:i]:
                    if weight(plus(u,v))<3 or weight(plus(u,neg(v)))<3:return False
        return True
    base=echelon([sum(int(c)<<(2*i) for i,c in enumerate(w)) for w in strings]);rank=len(base)
    if rank>12 or not distance_ok(base):return False,0
    tail=[0]
    for i in range(rank-1,-1,-1):
        for t in tail:
            word=plus(base[i],t);occupied=(word|(word>>1))&low
            keep=full^(occupied|(occupied<<1))
            restricted=echelon([v&keep for v in base])
            if len(restricted)!=rank-1 or not distance_ok(restricted):return False,0
        if i:tail += [plus(t,base[i]) for t in tail]+[plus(t,neg(base[i])) for t in tail]
    return True,3**rank


def second_irreducible(f):
    degree=len(f)-1
    for d in range(1,degree//2+1):
        for low in product(range(3),repeat=d):
            divisor=[*low,1];work=f[:]
            for i in range(degree,d-1,-1):
                c=work[i]
                for j in range(d+1):work[i-d+j]=(work[i-d+j]-c*divisor[j])%3
            if not any(work):return False
    return True


def verify_second(p,ans,inner_check):
    n,m=p.get('n'),p.get('m')
    if type(n)is not int or type(m)is not int or not 1<=m<=n<=1024:return False,0
    if not isinstance(ans,dict):return False,0
    if list(ans)==['linear_code']:return second_linear(p,ans)
    if list(ans)!=['rs_concat'] or not isinstance(ans['rs_concat'],dict):return False,0
    c=ans['rs_concat']
    if sorted(c)!=['dimension','field','inner','inner_m','inner_n','length']:return False,0
    dims=[c[k] for k in ('inner_n','inner_m','length','dimension')]
    if any(type(x)is not int for x in dims):return False,0
    length,separation,N,K=dims
    if not 1<=separation<=length<=n or K<1 or N<K or N*length>n:return False,0
    if (N-3*K+3)*separation<m:return False,0
    f=c['field']
    if not isinstance(f,list) or not 2<=len(f)<=13 or f[-1]!=1 or any(type(x)is not int or x<0 or x>2 for x in f):return False,0
    if isinstance(c['inner'],dict) and (len(c['inner'])!=1 or next(iter(c['inner'])) not in ('linear','linear_code')):return False,0
    ok,size=inner_check({'n':length,'m':separation,'representation':'certified'},c['inner'])
    if not ok or size!=3**(len(f)-1) or N>size:return False,0
    if not second_irreducible(f):return False,0
    return True,size**K
