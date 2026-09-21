"""Version-1 publication grouping; stored task IDs and instance weighting remain reproducible."""

LEGACY_FAMILIES = (
    "capset", "labs", "heilbronn", "kissing", "corners", "kissing_theta", "heilbronn_shape",
    "matmul", "degdiam", "lineq", "kakeya", "covering", "schur", "apfree_q", "mols",
)
CORE_GROUPS = {
    "capset": ("capset",),
    "labs": ("labs",),
    "heilbronn": ("heilbronn", "heilbronn_shape"),
    "spherical_code": ("kissing", "kissing_theta"),
    "corners": ("corners",),
    "matmul": ("matmul",),
    "degdiam": ("degdiam",),
    "lineq": ("lineq",),
    "covering": ("covering",),
    "schur": ("schur",),
    "apfree_q": ("apfree_q",),
    "mols": ("mols",),
}
CORE12_GROUPS = dict(CORE_GROUPS)
CORE_GROUPS.update({"shannon": ("shannon",), "trifference": ("trifference",)})
UNCLASSIFIED_GROUPS = {"trifference"}

GROUP_LABELS = {
    "shannon": "Shannon codes", "trifference": "trifference codes",
    "capset": "cap set", "labs": "LABS", "heilbronn": "Heilbronn", "spherical_code": "spherical codes",
    "corners": "corners", "matmul": "matrix multiplication", "degdiam": "degree-diameter",
    "lineq": "linear-equation-free", "covering": "covering", "schur": "Schur",
    "apfree_q": "finite-field AP-free", "mols": "MOLS",
}
TASK_LABELS = {"kissing": "spherical codes: 60 degrees", "kissing_theta": "spherical codes: variable angle",
               "heilbronn": "Heilbronn: square", "heilbronn_shape": "Heilbronn: triangle"}
SEARCH_GROUPS = {"labs", "heilbronn", "matmul", "degdiam", "covering"}


def groups(selection="core"):
    if selection == "legacy15":
        return {f: (f,) for f in LEGACY_FAMILIES}
    if selection == "core12":
        return dict(CORE12_GROUPS)
    if selection == "core":
        return dict(CORE_GROUPS)
    raise ValueError(f"Unknown selection: {selection}")


def members(group, selection="core"):
    return groups(selection).get(group, (group,))


def expand_groups(selected, selection="core"):
    return {f for group in selected for f in members(group, selection)}


def group_for(task):
    return next((g for g, fs in CORE_GROUPS.items() if task in fs), task)
