(function(root){
const data = [
  {
    "id": "capset",
    "title": "Cap sets",
    "category": "FINITE GEOMETRY",
    "description": "Choose many points, without selecting a triple that sums to zero.",
    "rule": "x + y + z ≠ 0 for distinct selected points",
    "instance": "F₃³ · a 27-point space",
    "task": "capset",
    "params": {
      "d": 3
    },
    "answer": [
      "000",
      "011",
      "021",
      "101",
      "112",
      "122",
      "201",
      "212",
      "222"
    ],
    "objective": 9,
    "points": [
      [
        0,
        0,
        0
      ],
      [
        0,
        1,
        1
      ],
      [
        0,
        2,
        1
      ],
      [
        1,
        0,
        1
      ],
      [
        1,
        1,
        2
      ],
      [
        1,
        2,
        2
      ],
      [
        2,
        0,
        1
      ],
      [
        2,
        1,
        2
      ],
      [
        2,
        2,
        2
      ]
    ],
    "group": "Points and patterns",
    "task_text": "A cap set is a collection of points with no three distinct selected points summing to zero. Here the coordinates are 0, 1 and 2, and addition wraps around modulo three. The objective is to select as many points as possible while respecting that rule.",
    "example_text": "The grey lattice contains all 27 points in three dimensions. Nine gold points emerge from the rule z = x² + y², with arithmetic modulo three. The lattice rotates so you can see the depth of the construction; the faint lines are coordinate guides, not extra constraints.",
    "scale_text": "The evaluated instances use 9–11 dimensions: 19,683–177,147 candidate points instead of the 27 shown here.",
    "legend": "Gold: selected points",
    "layout": "intro"
  },
  {
    "id": "apfree_q",
    "title": "Progression-free sets",
    "category": "FINITE FIELDS",
    "description": "Select many points with no three-term arithmetic progression, using arithmetic modulo five.",
    "rule": "x + z ≠ 2y for distinct selected points",
    "instance": "6 points in F₅²",
    "task": "apfree_q",
    "params": {
      "q": 5,
      "n": 2
    },
    "answer": [
      "10",
      "21",
      "24",
      "31",
      "34",
      "40"
    ],
    "objective": 6,
    "points": [
      [
        1,
        0
      ],
      [
        2,
        1
      ],
      [
        2,
        4
      ],
      [
        3,
        1
      ],
      [
        3,
        4
      ],
      [
        4,
        0
      ]
    ],
    "group": "Points and patterns",
    "task_text": "An arithmetic progression consists of a starting point, a midpoint and an endpoint, with x + z = 2y. Over a finite field the same equation applies coordinate by coordinate, using modular arithmetic. A good construction contains many points and no such triple.",
    "example_text": "This example works modulo five. Six selected points satisfy x² + 2y² = 1. Late in the animation, two selected points determine where a third progression term would have to lie; that missing point is marked with a cross.",
    "scale_text": "The formal instances use F₅ in five or six dimensions and F₇ in four dimensions, rather than this two-dimensional picture.",
    "legend": "Gold: selected points",
    "layout": "compact"
  },
  {
    "id": "corners",
    "title": "Corner-free sets",
    "category": "FORBIDDEN PATTERNS",
    "description": "Select grid points without completing an axis-aligned corner with equal legs.",
    "rule": "Avoid (x,y), (x+d,y), (x,y+d)",
    "instance": "A 7 × 7 grid",
    "task": "corners",
    "params": {
      "n": 7
    },
    "answer": [
      [
        0,
        2
      ],
      [
        0,
        3
      ],
      [
        0,
        5
      ],
      [
        0,
        6
      ],
      [
        1,
        3
      ],
      [
        1,
        4
      ],
      [
        1,
        6
      ],
      [
        2,
        4
      ],
      [
        2,
        5
      ],
      [
        3,
        0
      ],
      [
        3,
        5
      ],
      [
        3,
        6
      ],
      [
        4,
        0
      ],
      [
        4,
        1
      ],
      [
        4,
        6
      ],
      [
        5,
        1
      ],
      [
        5,
        2
      ],
      [
        6,
        0
      ],
      [
        6,
        2
      ],
      [
        6,
        3
      ]
    ],
    "objective": 20,
    "missingCorner": [
      [
        0,
        3
      ],
      [
        1,
        3
      ],
      [
        0,
        4
      ]
    ],
    "group": "Points and patterns",
    "task_text": "A corner consists of three grid points: a right-angle vertex and two points the same horizontal and vertical distance away. The distance may be positive or negative. Select as many points as possible without completing such a corner.",
    "example_text": "This 7 × 7 grid contains twenty selected points. Two of them form the highlighted right angle, but the third point is missing. The condition must hold for every possible corner.",
    "scale_text": "The evaluated grids have side lengths 138–185, with up to 34,225 candidate points.",
    "legend": "Outline: an excluded point",
    "layout": "compact"
  },
  {
    "id": "lineq",
    "title": "Linear-equation-free sets",
    "category": "ADDITIVE COMBINATORICS",
    "description": "Choose integers without a nontrivial solution to a prescribed linear equation.",
    "rule": "x + 2y = 3z only when x = y = z",
    "instance": "Integers from 1 to 27",
    "task": "lineq",
    "params": {
      "n": 27,
      "a": 1,
      "b": 2
    },
    "answer": [
      1,
      2,
      3,
      6,
      9,
      10,
      11,
      17,
      19,
      22
    ],
    "objective": 10,
    "missingAverage": [
      1,
      10,
      7
    ],
    "group": "Points and patterns",
    "task_text": "Choose a subset of an integer interval that contains no nontrivial solution to a linear equation. In this example the equation is x + 2y = 3z. The solution x = y = z is harmless; every other solution using selected numbers is forbidden.",
    "example_text": "Ten integers are retained from 1 to 27. As the layout settles onto a number line, two selected values identify a weighted average. The marked average is outside the set, so that potential equation is not completed.",
    "scale_text": "Formal instances vary both the coefficients and the interval, with intervals containing 6,248–19,044 integers.",
    "legend": "Gold: retained integers",
    "layout": "compact"
  },
  {
    "id": "schur",
    "title": "Schur colourings",
    "category": "RAMSEY THEORY",
    "description": "Colour a long interval of integers without a same-colour sum x + y = z.",
    "rule": "No monochromatic x + y = z, including x = y",
    "instance": "A three-colouring of 1–13",
    "task": "schur",
    "params": {
      "k": 3
    },
    "answer": [
      0,
      1,
      1,
      0,
      2,
      2,
      2,
      2,
      2,
      0,
      1,
      1,
      0
    ],
    "objective": 13,
    "group": "Points and patterns",
    "task_text": "Colour every integer from 1 to N so that no colour class contains x, y and x + y, including x = y. With the number of colours held constant, a longer fully coloured interval is a better construction.",
    "example_text": "Here, thirteen integers separate into three sum-free classes. The example 1 + 1 = 2 crosses between classes; every sum of two members of a class must fall outside that class.",
    "scale_text": "The benchmark uses six, seven or eight colours and much longer intervals.",
    "legend": "Rows: sum-free colour classes",
    "layout": "compact"
  },
  {
    "id": "heilbronn",
    "title": "Heilbronn triangles",
    "category": "DISCRETE GEOMETRY",
    "description": "Place points in a square. Make the smallest triangle between them as large as possible.",
    "rule": "The smallest of all triangles determines quality",
    "instance": "7 points · 35 triangles",
    "task": "heilbronn",
    "params": {
      "n": 7
    },
    "answer": [
      [
        5435,
        1029
      ],
      [
        7973,
        2784
      ],
      [
        8323,
        5422
      ],
      [
        6553,
        7746
      ],
      [
        3373,
        7813
      ],
      [
        1460,
        5473
      ],
      [
        1836,
        2699
      ]
    ],
    "objective": 0.0274133,
    "group": "Geometry and distance",
    "task_text": "Place a fixed number of points inside a square. Every choice of three points forms a triangle, and the smallest triangle determines the objective. Improving most triangles is not enough if one nearly collinear triple remains.",
    "example_text": "Seven points create 35 triangles. As the points move, the minimum-area triangle is highlighted and its area is recomputed. The motion shows how the limiting triangle can change; it is not a claimed optimisation trajectory.",
    "scale_text": "Formal instances use 26–50 points in square or triangular domains. Fifty points generate 19,600 triangles to consider.",
    "legend": "Gold: the minimum-area triangle",
    "layout": "geometry"
  },
  {
    "id": "spherical_code",
    "title": "Spherical codes",
    "category": "SPHERICAL GEOMETRY",
    "description": "Fit many directions on a sphere while keeping every pair far enough apart.",
    "rule": "Pairwise angles ≥ 60°",
    "instance": "12 directions in three dimensions",
    "task": "kissing",
    "params": {
      "d": 3
    },
    "answer": [
      [
        0,
        -618,
        -1000
      ],
      [
        -618,
        -1000,
        0
      ],
      [
        -1000,
        0,
        -618
      ],
      [
        0,
        -618,
        1000
      ],
      [
        -618,
        1000,
        0
      ],
      [
        1000,
        0,
        -618
      ],
      [
        0,
        618,
        -1000
      ],
      [
        618,
        -1000,
        0
      ],
      [
        -1000,
        0,
        618
      ],
      [
        0,
        618,
        1000
      ],
      [
        618,
        1000,
        0
      ],
      [
        1000,
        0,
        618
      ]
    ],
    "objective": 12,
    "group": "Geometry and distance",
    "task_text": "A spherical code places directions on the surface of a sphere while keeping every pair separated by a required angle. Here that threshold is 60 degrees. The objective is to fit as many directions as possible without violating the separation constraint.",
    "example_text": "Twelve directions appear around the sphere. The highlighted arc joins a closest pair, separated by approximately 63.4 degrees. Rotating the view helps distinguish points on the near and far sides.",
    "scale_text": "The benchmark uses 12–15 dimensions and includes both a 60-degree threshold and variable-angle variants.",
    "legend": "Arc: a closest pair",
    "layout": "geometry"
  },
  {
    "id": "degdiam",
    "title": "Degree–diameter graphs",
    "category": "GRAPH THEORY",
    "description": "Fit as many vertices as possible while limiting the degree and the longest shortest path.",
    "rule": "Degree ≤ 3 · diameter ≤ 2",
    "instance": "The ten-vertex Petersen graph",
    "task": "degdiam",
    "params": {
      "d": 3,
      "k": 2
    },
    "answer": [
      [
        0,
        1
      ],
      [
        0,
        5
      ],
      [
        5,
        7
      ],
      [
        1,
        2
      ],
      [
        1,
        6
      ],
      [
        6,
        8
      ],
      [
        2,
        3
      ],
      [
        2,
        7
      ],
      [
        7,
        9
      ],
      [
        3,
        4
      ],
      [
        3,
        8
      ],
      [
        5,
        8
      ],
      [
        0,
        4
      ],
      [
        4,
        9
      ],
      [
        6,
        9
      ]
    ],
    "objective": 10,
    "group": "Geometry and distance",
    "task_text": "How many vertices can a graph have if each vertex has only a few neighbours and every pair must remain a few steps apart? The degree limits the number of edges at each vertex; the diameter limits the longest shortest path.",
    "example_text": "The ten-vertex Petersen graph has degree three and diameter two. From the marked vertex, three neighbours are reached in one step and all remaining vertices in a second. The same distance limit holds from every starting vertex.",
    "scale_text": "The evaluated instances use different combinations of degree and diameter limits, each ranging from 3 to 7.",
    "legend": "Gold: reached within the step limit",
    "layout": "network"
  },
  {
    "id": "covering",
    "title": "Covering designs",
    "category": "COMBINATORIAL DESIGNS",
    "description": "Cover every required subset using as few larger blocks as possible.",
    "rule": "Every pair belongs to at least one triple",
    "instance": "7 elements · 21 pairs",
    "task": "covering",
    "params": {
      "v": 7,
      "k": 3,
      "t": 2
    },
    "answer": [
      [
        0,
        1,
        3
      ],
      [
        1,
        2,
        4
      ],
      [
        2,
        3,
        5
      ],
      [
        3,
        4,
        6
      ],
      [
        0,
        4,
        5
      ],
      [
        1,
        5,
        6
      ],
      [
        0,
        2,
        6
      ]
    ],
    "objective": 7,
    "group": "Designs and algorithms",
    "task_text": "A covering design uses larger subsets, called blocks, to cover every smaller subset of a specified size. The aim is to use as few blocks as possible while leaving no required subset uncovered.",
    "example_text": "On these seven elements, each triple covers three pairs. Seven triples cover all 21 pairs, each exactly once.",
    "scale_text": "The benchmark extends this to 18–30 elements, covering triples or four-element subsets with blocks of six or seven elements.",
    "legend": "Gold: covered pairs",
    "layout": "compact"
  },
  {
    "id": "mols",
    "title": "Orthogonal Latin squares",
    "category": "COMBINATORIAL DESIGNS",
    "description": "Each symbol appears once in every row and column. Overlay the squares: every ordered pair is different.",
    "rule": "All nine ordered pairs appear exactly once",
    "instance": "Two Latin squares of order 3",
    "task": "mols",
    "params": {
      "n": 3
    },
    "answer": [
      [
        [
          0,
          1,
          2
        ],
        [
          1,
          2,
          0
        ],
        [
          2,
          0,
          1
        ]
      ],
      [
        [
          0,
          2,
          1
        ],
        [
          1,
          0,
          2
        ],
        [
          2,
          1,
          0
        ]
      ]
    ],
    "objective": 2,
    "group": "Designs and algorithms",
    "task_text": "A Latin square contains every symbol exactly once in each row and column. Two squares are orthogonal when overlaying them produces no repeated ordered pair. The task asks for as many pairwise orthogonal squares of the given order as possible.",
    "example_text": "The two order-three squares use the rules r + c and r + 2c, modulo three. Their cells align to form nine different pairs. The two components of each pair retain their visual identity as the squares come together.",
    "scale_text": "Formal instances use orders 10–20. Their larger arrays require many more row, column and pairwise-orthogonality checks.",
    "legend": "Paired symbols: one from each square",
    "layout": "squares"
  },
  {
    "id": "matmul",
    "title": "Matrix multiplication",
    "category": "ALGEBRAIC ALGORITHMS",
    "description": "Combine and reuse scalar products to multiply matrices with fewer multiplications.",
    "rule": "Seven products recombine into four output entries",
    "instance": "Strassen’s 2 × 2 construction",
    "task": "matmul",
    "params": {
      "n": 2,
      "m": 2,
      "p": 2
    },
    "answer": [
      [
        [
          1,
          0,
          0,
          1
        ],
        [
          1,
          0,
          0,
          1
        ],
        [
          1,
          0,
          0,
          1
        ]
      ],
      [
        [
          0,
          0,
          1,
          1
        ],
        [
          1,
          0,
          0,
          0
        ],
        [
          0,
          0,
          1,
          -1
        ]
      ],
      [
        [
          1,
          0,
          0,
          0
        ],
        [
          0,
          1,
          0,
          -1
        ],
        [
          0,
          1,
          0,
          1
        ]
      ],
      [
        [
          0,
          0,
          0,
          1
        ],
        [
          -1,
          0,
          1,
          0
        ],
        [
          1,
          0,
          1,
          0
        ]
      ],
      [
        [
          1,
          1,
          0,
          0
        ],
        [
          0,
          0,
          0,
          1
        ],
        [
          -1,
          1,
          0,
          0
        ]
      ],
      [
        [
          -1,
          0,
          1,
          0
        ],
        [
          1,
          1,
          0,
          0
        ],
        [
          0,
          0,
          0,
          1
        ]
      ],
      [
        [
          0,
          1,
          0,
          -1
        ],
        [
          0,
          0,
          1,
          1
        ],
        [
          1,
          0,
          0,
          0
        ]
      ]
    ],
    "objective": 7,
    "A": [
      1,
      2,
      3,
      4
    ],
    "B": [
      2,
      1,
      1,
      3
    ],
    "C": [
      4,
      7,
      10,
      15
    ],
    "products": [
      25,
      14,
      -2,
      -4,
      9,
      6,
      -8
    ],
    "group": "Designs and algorithms",
    "task_text": "Construct a scheme that multiplies matrices using few scalar multiplications. Each multiplication may combine several input entries, and its result may contribute to several output entries. The resulting identities must hold for every input matrix, not just one numerical example.",
    "example_text": "This illustration uses Strassen’s seven-product scheme for 2 × 2 matrices. Watch input combinations feed the shared products, then recombine into the four output entries. The displayed numbers provide a concrete example of the identities.",
    "scale_text": "The evaluated shapes are 4×4 by 4×5, 4×5 by 5×5, and 5×5 by 5×5, with integer coefficient constraints.",
    "legend": "Gold: an active product or contribution",
    "layout": "scheme"
  },
  {
    "id": "labs",
    "title": "Low-autocorrelation sequences",
    "category": "SEQUENCES",
    "description": "Arrange +1 and −1 so shifted copies agree as little as possible.",
    "rule": "Small correlations give a larger merit factor",
    "instance": "13 signs · 12 nonzero shifts",
    "task": "labs",
    "params": {
      "N": 13
    },
    "answer": [
      1,
      1,
      1,
      1,
      1,
      -1,
      -1,
      1,
      1,
      -1,
      1,
      -1,
      1
    ],
    "objective": 14.083333333333334,
    "correlations": [
      0,
      1,
      0,
      1,
      0,
      1,
      0,
      1,
      0,
      1,
      0,
      1
    ],
    "energy": 6,
    "group": "Sequences and codes",
    "task_text": "Choose a sequence of +1 and −1 signs. At each nonzero shift, compare the overlapping signs and add their products. These correlations are squared and summed; a smaller total gives a larger merit factor, the quantity being maximised.",
    "example_text": "A length-thirteen Barker sequence is compared with its shifted copies. The bars show all twelve nonzero-shift correlations. Their squared sum is six, giving this short sequence a merit factor of 169/12, approximately 14.08.",
    "scale_text": "The benchmark sequences have lengths 240–375, with many more shifts whose correlations must be controlled together.",
    "legend": "Bars: nonzero-shift correlations",
    "layout": "sequence"
  },
  {
    "id": "shannon",
    "title": "Shannon codes",
    "category": "ZERO-ERROR COMMUNICATION",
    "description": "Choose codewords that cannot be confused: every pair differs far enough in some position.",
    "rule": "At least one coordinate has cyclic distance ≥ 2",
    "instance": "5 codewords of length 2 over C₅",
    "task": "shannon",
    "params": {
      "q": 5,
      "d": 2
    },
    "answer": [
      "00",
      "12",
      "24",
      "31",
      "43"
    ],
    "objective": 5,
    "group": "Sequences and codes",
    "task_text": "Imagine a channel where equal or neighbouring symbols on a cycle can be confused. Two codewords are distinguishable only if at least one position uses symbols far enough apart on that cycle. The task is to construct as many mutually distinguishable words as possible.",
    "example_text": "Each circle is a five-symbol channel position. Five two-symbol words are selected, pairing i with 2i modulo five. Two words may be confusable in the first position and still be separated in the second.",
    "scale_text": "Formal instances use seven or nine symbols and lengths 24–64. Verified products of smaller codes can describe very large constructions.",
    "legend": "Gold: a distinguishing coordinate",
    "layout": "codes"
  },
  {
    "id": "trifference",
    "title": "Trifference codes",
    "category": "SEPARATING CODES",
    "description": "For any three codewords, find a position where their symbols are all different.",
    "rule": "Every triple separates as 0, 1, 2 in some column",
    "instance": "9 ternary codewords of length 4",
    "task": "trifference",
    "params": {
      "n": 4,
      "m": 1
    },
    "answer": [
      "0000",
      "0112",
      "0221",
      "1011",
      "1120",
      "1202",
      "2022",
      "2101",
      "2210"
    ],
    "objective": 9,
    "triples": [
      [
        0,
        3,
        6
      ],
      [
        0,
        1,
        2
      ],
      [
        0,
        1,
        4
      ],
      [
        0,
        1,
        3
      ]
    ],
    "group": "Sequences and codes",
    "task_text": "A trifference code uses the symbols 0, 1 and 2. For every three distinct codewords, some position must contain all three symbols. It is not enough to distinguish words pair by pair: the same position must separate the entire triple.",
    "example_text": "The display contains nine words of length four. Three rows are highlighted at a time, and a gold column shows their three different symbols. This small code already has 84 triples, all of which satisfy the condition.",
    "scale_text": "The formal code lengths are 64, 96, 144 and 192. Compact algebraic certificates allow much larger code families to be submitted and checked.",
    "legend": "Gold: three distinct symbols in one position",
    "layout": "tall-code"
  }
];
if(typeof module!=="undefined"&&module.exports)module.exports=data;else root.EndlessAtlasData=data;
})(typeof globalThis!=="undefined"?globalThis:this);
