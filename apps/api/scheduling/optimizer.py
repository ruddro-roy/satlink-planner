from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from ortools.sat.python import cp_model


@dataclass
class PassCandidate:
    sat_id: str
    start: datetime
    end: datetime
    min_el_deg: float
    bitrate_bps: float
    weight: float = 1.0

    @property
    def duration_s(self) -> int:
        return int((self.end - self.start).total_seconds())

    @property
    def area(self) -> float:
        return self.duration_s * self.bitrate_bps * self.weight


@dataclass
class ScheduleResult:
    selected_indices: List[int]
    objective_bits: float


def optimize_schedule(
    candidates: Sequence[PassCandidate],
    max_concurrent: int = 1,
) -> ScheduleResult:
    model = cp_model.CpModel()
    n = len(candidates)
    x = [model.NewBoolVar(f"pass_{i}") for i in range(n)]

    # No-overlap per resource capacity max_concurrent
    # Discretize with pairwise overlap constraints when max_concurrent==1
    if max_concurrent == 1:
        for i in range(n):
            for j in range(i + 1, n):
                a, b = candidates[i], candidates[j]
                if not (a.end <= b.start or b.end <= a.start):
                    model.Add(x[i] + x[j] <= 1)
    else:
        # Time-indexed relaxation: sample boundaries
        timepoints = sorted({c.start for c in candidates} | {c.end for c in candidates})
        for t in timepoints:
            active = [i for i, c in enumerate(candidates) if c.start <= t < c.end]
            if active:
                model.Add(sum(x[i] for i in active) <= max_concurrent)

    # Objective: maximize weighted bits
    model.Maximize(sum(int(c.area) * x[i] for i, c in enumerate(candidates)))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 8.0
    solver.parameters.num_search_workers = 8
    result = solver.Solve(model)

    chosen = [i for i in range(n) if solver.BooleanValue(x[i])]
    obj = solver.ObjectiveValue()
    return ScheduleResult(selected_indices=chosen, objective_bits=obj)


