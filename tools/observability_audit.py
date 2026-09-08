#!/usr/bin/env python3
"""Audit clock-marginalized information from controlled pseudorange geometry.

This is a linear observability unit test, not a lunar performance simulator. Clock
bias is expressed in range units (metres), so a pseudorange row is [-u, 1].
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class AuditResult:
    name: str
    epochs: int
    satellites_per_epoch: list[int]
    clock_model: str
    joint_range_rank: int
    effective_position_rank: int
    effective_eigenvalues: list[float]


@dataclass(frozen=True)
class MarginalBenefitResult:
    name: str
    weak_direction: list[float]
    clock_model: str
    prior_variance: float | None
    posterior_variance: float | None
    variance_reduction: float | None
    relative_variance_reduction: float | None
    prior_absolute_std_metres: float | None
    posterior_absolute_std_metres: float | None
    absolute_relative_variance_reduction: float | None
    prior_relative_displacement_std_metres: float | None
    posterior_relative_displacement_std_metres: float | None
    relative_displacement_variance_reduction: float | None


def numerical_rank(matrix: np.ndarray, relative_tolerance: float = 1e-10) -> int:
    """Return a scale-relative numerical rank, including for a zero matrix."""
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    if singular_values.size == 0 or singular_values[0] == 0.0:
        return 0
    return int(
        np.count_nonzero(singular_values > relative_tolerance * singular_values[0])
    )


def range_jacobians(
    lines_of_sight: list[list[list[float]]], clock_model: str
) -> tuple[np.ndarray, np.ndarray]:
    """Build position and clock Jacobians for unit-variance pseudoranges."""
    epochs = len(lines_of_sight)
    if clock_model not in {"independent", "constant", "random_walk", "bias_drift"}:
        raise ValueError(f"unsupported clock model: {clock_model}")
    if clock_model == "constant":
        clock_states = 1
    elif clock_model == "bias_drift":
        clock_states = 2 * epochs
    else:
        clock_states = epochs
    rows = sum(len(epoch) for epoch in lines_of_sight)
    h_position = np.zeros((rows, 3 * epochs))
    h_clock = np.zeros((rows, clock_states))

    row = 0
    for epoch_index, epoch_lines in enumerate(lines_of_sight):
        for line in epoch_lines:
            unit_line = np.asarray(line, dtype=float)
            norm = np.linalg.norm(unit_line)
            if norm == 0.0:
                raise ValueError("line-of-sight vector must be non-zero")
            unit_line /= norm
            h_position[row, 3 * epoch_index : 3 * epoch_index + 3] = -unit_line
            clock_index = 0 if clock_model == "constant" else epoch_index
            h_clock[row, clock_index] = 1.0
            row += 1
    return h_position, h_clock


def clock_marginalized_information(
    h_position: np.ndarray,
    h_clock: np.ndarray,
    clock_prior_information: np.ndarray | None = None,
) -> np.ndarray:
    """Schur-complement clock nuisance states from unit-weight ranges."""
    lambda_pp = h_position.T @ h_position
    lambda_pc = h_position.T @ h_clock
    lambda_cc = h_clock.T @ h_clock
    if clock_prior_information is not None:
        if clock_prior_information.shape != lambda_cc.shape:
            raise ValueError("clock prior shape does not match clock state")
        lambda_cc = lambda_cc + clock_prior_information
    return lambda_pp - lambda_pc @ np.linalg.pinv(lambda_cc) @ lambda_pc.T


def clock_process_information(
    epochs: int,
    clock_model: str,
    bias_random_walk_information: float = 1.0,
    drift_random_walk_information: float = 1.0,
    initial_bias_information: float = 0.01,
    initial_drift_information: float = 1.0,
    time_step: float = 1.0,
) -> np.ndarray:
    """Build controlled clock prior/process information in range units."""
    positive = (
        bias_random_walk_information,
        drift_random_walk_information,
        time_step,
    )
    if epochs < 1 or min(positive) <= 0.0:
        raise ValueError(
            "epochs and clock process information parameters must be positive"
        )
    if min(initial_bias_information, initial_drift_information) < 0.0:
        raise ValueError("initial clock information must be non-negative")
    if clock_model == "constant":
        return np.zeros((1, 1))
    if clock_model == "independent":
        return np.zeros((epochs, epochs))
    if clock_model == "random_walk":
        information = np.zeros((epochs, epochs))
        information[0, 0] += initial_bias_information
        for epoch in range(epochs - 1):
            row = np.zeros(epochs)
            row[epoch] = -1.0
            row[epoch + 1] = 1.0
            information += bias_random_walk_information * np.outer(row, row)
        return information
    if clock_model == "bias_drift":
        information = np.zeros((2 * epochs, 2 * epochs))
        information[0, 0] += initial_bias_information
        information[epochs, epochs] += initial_drift_information
        for epoch in range(epochs - 1):
            bias_row = np.zeros(2 * epochs)
            bias_row[epoch] = -1.0
            bias_row[epoch + 1] = 1.0
            bias_row[epochs + epoch] = -time_step
            information += bias_random_walk_information * np.outer(bias_row, bias_row)
            drift_row = np.zeros(2 * epochs)
            drift_row[epochs + epoch] = -1.0
            drift_row[epochs + epoch + 1] = 1.0
            information += drift_random_walk_information * np.outer(
                drift_row, drift_row
            )
        return information
    raise ValueError(f"unsupported clock model: {clock_model}")


def physical_clock_process_information(
    epochs: int,
    clock_model: str,
    time_step_seconds: float,
    initial_bias_sigma_metres: float | None,
    initial_drift_sigma_metres_per_second: float | None,
    bias_rw_density_metres_per_sqrt_second: float,
    drift_rw_density_metres_per_second_per_sqrt_second: float,
) -> np.ndarray:
    """Build a dimensioned, deliberately simple discrete clock process model.

    The bias/drift model uses F=[[1, dt], [0, 1]] and independent residual
    variances q_b*dt and q_d*dt. It is a sensitivity model, not a fitted
    oscillator power-law model.
    """
    positive = (
        time_step_seconds,
        bias_rw_density_metres_per_sqrt_second,
        drift_rw_density_metres_per_second_per_sqrt_second,
    )
    if epochs < 1 or min(positive) <= 0.0:
        raise ValueError("epochs, time step, and clock process sigmas must be positive")
    if initial_bias_sigma_metres is not None and initial_bias_sigma_metres <= 0.0:
        raise ValueError("initial bias sigma must be positive or None")
    if (
        initial_drift_sigma_metres_per_second is not None
        and initial_drift_sigma_metres_per_second <= 0.0
    ):
        raise ValueError("initial drift sigma must be positive or None")
    bias_prior = (
        0.0 if initial_bias_sigma_metres is None else 1.0 / initial_bias_sigma_metres**2
    )
    drift_prior = (
        0.0
        if initial_drift_sigma_metres_per_second is None
        else 1.0 / initial_drift_sigma_metres_per_second**2
    )
    bias_step_information = 1.0 / (
        bias_rw_density_metres_per_sqrt_second**2 * time_step_seconds
    )
    drift_step_information = 1.0 / (
        drift_rw_density_metres_per_second_per_sqrt_second**2 * time_step_seconds
    )
    if clock_model == "constant":
        return np.array([[bias_prior]])
    if clock_model == "independent":
        return bias_prior * np.eye(epochs)
    return clock_process_information(
        epochs,
        clock_model,
        bias_random_walk_information=bias_step_information,
        drift_random_walk_information=drift_step_information,
        initial_bias_information=bias_prior,
        initial_drift_information=drift_prior,
        time_step=time_step_seconds,
    )


def odometry_position_information(
    epochs: int,
    weak_direction: list[float],
    weak_information: float,
    strong_information: float,
    initial_prior_information: float,
) -> np.ndarray:
    """Build anchored position information from anisotropic relative increments."""
    if epochs < 1:
        raise ValueError("epochs must be positive")
    if (
        min(weak_information, strong_information) <= 0.0
        or initial_prior_information < 0.0
    ):
        raise ValueError(
            "increment information must be positive and prior non-negative"
        )
    weak = np.asarray(weak_direction, dtype=float)
    norm = np.linalg.norm(weak)
    if norm == 0.0:
        raise ValueError("weak direction must be non-zero")
    weak /= norm
    weak_projector = np.outer(weak, weak)
    increment_information = weak_information * weak_projector + strong_information * (
        np.eye(3) - weak_projector
    )

    information = np.zeros((3 * epochs, 3 * epochs))
    information[:3, :3] += initial_prior_information * np.eye(3)
    for epoch in range(epochs - 1):
        first = slice(3 * epoch, 3 * epoch + 3)
        second = slice(3 * (epoch + 1), 3 * (epoch + 1) + 3)
        information[first, first] += increment_information
        information[second, second] += increment_information
        information[first, second] -= increment_information
        information[second, first] -= increment_information
    return information


def final_direction_variance(
    covariance: np.ndarray, epochs: int, direction: list[float]
) -> float:
    """Project the final-epoch marginal covariance onto a unit direction."""
    unit_direction = np.asarray(direction, dtype=float)
    norm = np.linalg.norm(unit_direction)
    if norm == 0.0:
        raise ValueError("projection direction must be non-zero")
    unit_direction /= norm
    final = covariance[3 * (epochs - 1) : 3 * epochs, 3 * (epochs - 1) : 3 * epochs]
    return float(unit_direction @ final @ unit_direction)


def position_direction_functional(
    epochs: int, direction: list[float], quantity: str
) -> np.ndarray:
    """Return a linear functional for p_T or p_T-p_0 along a direction."""
    unit_direction = np.asarray(direction, dtype=float)
    norm = np.linalg.norm(unit_direction)
    if norm == 0.0:
        raise ValueError("functional direction must be non-zero")
    unit_direction /= norm
    functional = np.zeros(3 * epochs)
    functional[-3:] = unit_direction
    if quantity == "relative_displacement":
        functional[:3] -= unit_direction
    elif quantity != "absolute_position":
        raise ValueError(f"unsupported position quantity: {quantity}")
    return functional


def estimable_linear_variance(
    information: np.ndarray, functional: np.ndarray, relative_tolerance: float = 1e-10
) -> tuple[bool, float | None]:
    """Return variance only when a linear functional is orthogonal to the nullspace."""
    eigenvalues, eigenvectors = np.linalg.eigh(information)
    scale = max(float(np.max(np.abs(eigenvalues))), 1.0)
    nullspace = eigenvectors[:, np.abs(eigenvalues) <= relative_tolerance * scale]
    projection_tolerance = max(1e-8, 100.0 * relative_tolerance) * max(
        np.linalg.norm(functional), 1.0
    )
    if (
        nullspace.size
        and np.linalg.norm(nullspace.T @ functional) > projection_tolerance
    ):
        return False, None
    variance = float(functional @ np.linalg.pinv(information) @ functional)
    return True, max(variance, 0.0)


def assemble_joint_information(
    position_information: np.ndarray,
    h_position: np.ndarray,
    h_clock: np.ndarray,
    clock_information: np.ndarray | None,
    include_ranges: bool,
) -> np.ndarray:
    """Assemble the full position/clock system without hiding singular directions."""
    clock_block = (
        np.zeros((h_clock.shape[1], h_clock.shape[1]))
        if clock_information is None
        else clock_information
    )
    joint = np.zeros(
        (
            position_information.shape[0] + h_clock.shape[1],
            position_information.shape[1] + h_clock.shape[1],
        )
    )
    position_size = position_information.shape[0]
    joint[:position_size, :position_size] = position_information
    joint[position_size:, position_size:] = clock_block
    if include_ranges:
        joint += np.block(
            [
                [h_position.T @ h_position, h_position.T @ h_clock],
                [h_clock.T @ h_position, h_clock.T @ h_clock],
            ]
        )
    return joint


def metric_from_joint_systems(
    prior_information: np.ndarray,
    posterior_information: np.ndarray,
    position_functional: np.ndarray,
) -> tuple[float | None, float | None, float | None]:
    """Return prior/posterior std and variance reduction, preserving unobservability."""
    padded = np.pad(
        position_functional,
        (0, prior_information.shape[0] - position_functional.shape[0]),
    )
    prior_estimable, prior_variance = estimable_linear_variance(
        prior_information, padded
    )
    posterior_estimable, posterior_variance = estimable_linear_variance(
        posterior_information, padded
    )
    prior_std = None if not prior_estimable else float(np.sqrt(prior_variance))
    posterior_std = (
        None if not posterior_estimable else float(np.sqrt(posterior_variance))
    )
    reduction = None
    if (
        prior_variance is not None
        and posterior_variance is not None
        and prior_variance > 0.0
    ):
        reduction = (prior_variance - posterior_variance) / prior_variance
    return prior_std, posterior_std, reduction


def marginal_benefit_scenario(
    name: str,
    lines_of_sight: list[list[list[float]]],
    clock_model: str,
    weak_direction: list[float],
    weak_information: float = 1.0,
    strong_information: float = 100.0,
    initial_prior_information: float = 100.0,
    range_information: float = 1.0,
    clock_information: np.ndarray | None = None,
    range_sigmas_metres: list[float] | None = None,
) -> MarginalBenefitResult:
    """Measure final weak-direction variance reduction from controlled ranges."""
    epochs = len(lines_of_sight)
    base_information = odometry_position_information(
        epochs,
        weak_direction,
        weak_information,
        strong_information,
        initial_prior_information,
    )
    h_position, h_clock = range_jacobians(lines_of_sight, clock_model)
    if range_sigmas_metres is None:
        if range_information <= 0.0:
            raise ValueError("range information must be positive")
        row_scales = np.full(h_position.shape[0], np.sqrt(range_information))
    else:
        if len(range_sigmas_metres) != h_position.shape[0]:
            raise ValueError("one range sigma is required for each measurement")
        sigmas = np.asarray(range_sigmas_metres, dtype=float)
        if np.any(sigmas <= 0.0):
            raise ValueError("range sigmas must be positive")
        row_scales = 1.0 / sigmas
    scaled_position = row_scales[:, None] * h_position
    scaled_clock = row_scales[:, None] * h_clock
    prior_joint = assemble_joint_information(
        base_information, scaled_position, scaled_clock, clock_information, False
    )
    posterior_joint = assemble_joint_information(
        base_information, scaled_position, scaled_clock, clock_information, True
    )
    absolute_functional = position_direction_functional(
        epochs, weak_direction, "absolute_position"
    )
    displacement_functional = position_direction_functional(
        epochs, weak_direction, "relative_displacement"
    )
    absolute = metric_from_joint_systems(
        prior_joint, posterior_joint, absolute_functional
    )
    displacement = metric_from_joint_systems(
        prior_joint, posterior_joint, displacement_functional
    )
    prior_variance = None if absolute[0] is None else absolute[0] ** 2
    posterior_variance = None if absolute[1] is None else absolute[1] ** 2
    reduction = (
        None
        if prior_variance is None or posterior_variance is None
        else prior_variance - posterior_variance
    )
    return MarginalBenefitResult(
        name=name,
        weak_direction=[float(value) for value in weak_direction],
        clock_model=clock_model,
        prior_variance=None if prior_variance is None else round(prior_variance, 12),
        posterior_variance=None
        if posterior_variance is None
        else round(posterior_variance, 12),
        variance_reduction=None if reduction is None else round(reduction, 12),
        relative_variance_reduction=(
            None if absolute[2] is None else round(absolute[2], 12)
        ),
        prior_absolute_std_metres=None
        if absolute[0] is None
        else round(absolute[0], 12),
        posterior_absolute_std_metres=(
            None if absolute[1] is None else round(absolute[1], 12)
        ),
        absolute_relative_variance_reduction=(
            None if absolute[2] is None else round(absolute[2], 12)
        ),
        prior_relative_displacement_std_metres=(
            None if displacement[0] is None else round(displacement[0], 12)
        ),
        posterior_relative_displacement_std_metres=(
            None if displacement[1] is None else round(displacement[1], 12)
        ),
        relative_displacement_variance_reduction=(
            None if displacement[2] is None else round(displacement[2], 12)
        ),
    )


def audit_scenario(
    name: str, lines_of_sight: list[list[list[float]]], clock_model: str
) -> AuditResult:
    h_position, h_clock = range_jacobians(lines_of_sight, clock_model)
    effective = clock_marginalized_information(h_position, h_clock)
    eigenvalues = np.linalg.eigvalsh(effective)
    eigenvalues[np.abs(eigenvalues) < 1e-12] = 0.0
    return AuditResult(
        name=name,
        epochs=len(lines_of_sight),
        satellites_per_epoch=[len(epoch) for epoch in lines_of_sight],
        clock_model=clock_model,
        joint_range_rank=numerical_rank(np.hstack((h_position, h_clock))),
        effective_position_rank=numerical_rank(effective),
        effective_eigenvalues=[round(float(value), 12) for value in eigenvalues],
    )


def controlled_scenarios() -> list[AuditResult]:
    """Return rank checks whose geometry is deliberately synthetic."""
    axes = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    tetrahedron = axes + [[-1, -1, -1]]
    specifications = [
        ("one_epoch_one_satellite", [[axes[0]]], "independent"),
        ("one_epoch_two_satellites", [[axes[0], axes[1]]], "independent"),
        ("one_epoch_three_satellites", [[axes[0], axes[1], axes[2]]], "independent"),
        ("one_epoch_four_satellites", [[*tetrahedron]], "independent"),
        ("three_epochs_one_satellite_free_clock", [[axes[0]]] * 3, "independent"),
        ("three_epochs_one_satellite_shared_clock", [[axes[0]]] * 3, "constant"),
        (
            "three_epochs_changing_line_shared_clock",
            [[axes[0]], [axes[1]], [axes[2]]],
            "constant",
        ),
    ]
    return [audit_scenario(*specification) for specification in specifications]


def controlled_marginal_benefit_scenarios() -> list[MarginalBenefitResult]:
    """Compare ranges aligned with or orthogonal to an odometry weak direction."""
    epochs = 5
    weak_direction = [1, 0, 0]
    # Both rays have a positive z component; their difference is aligned with x or y.
    aligned_ranges = [[[1, 0, 1], [-1, 0, 1]] for _ in range(epochs)]
    orthogonal_ranges = [[[0, 1, 1], [0, -1, 1]] for _ in range(epochs)]
    return [
        marginal_benefit_scenario(
            "range_difference_aligned_with_weak_x",
            aligned_ranges,
            "constant",
            weak_direction,
        ),
        marginal_benefit_scenario(
            "range_difference_orthogonal_to_weak_x",
            orthogonal_ranges,
            "constant",
            weak_direction,
        ),
    ]


def angular_range_geometry(
    horizontal_los_difference_to_weak_angle_degrees: float, epochs: int
) -> list[list[list[float]]]:
    """Set the horizontal LOS-difference/weak-direction angle, not inter-LOS angle."""
    if not 0.0 <= horizontal_los_difference_to_weak_angle_degrees <= 90.0:
        raise ValueError("angle must lie between 0 and 90 degrees")
    angle = np.deg2rad(horizontal_los_difference_to_weak_angle_degrees)
    direction = [float(np.cos(angle)), float(np.sin(angle))]
    return [
        [[direction[0], direction[1], 1.0], [-direction[0], -direction[1], 1.0]]
        for _ in range(epochs)
    ]


def perturbed_angular_range_geometry(
    horizontal_los_difference_to_weak_angle_degrees: float,
    epochs: int,
    first_elevation_degrees: float,
    second_elevation_degrees: float,
    azimuth_drift_degrees_per_epoch: float = 0.0,
) -> list[list[list[float]]]:
    """Perturb rays starting at a horizontal LOS-difference/weak-direction angle."""
    if not 0.0 <= horizontal_los_difference_to_weak_angle_degrees <= 90.0:
        raise ValueError("angle must lie between 0 and 90 degrees")
    if (
        not 0.0 < first_elevation_degrees < 90.0
        or not 0.0 < second_elevation_degrees < 90.0
    ):
        raise ValueError("elevations must lie strictly between 0 and 90 degrees")
    geometry = []
    for epoch in range(epochs):
        azimuth = np.deg2rad(
            horizontal_los_difference_to_weak_angle_degrees
            + epoch * azimuth_drift_degrees_per_epoch
        )
        horizontal = np.array([np.cos(azimuth), np.sin(azimuth)])
        first_elevation = np.deg2rad(first_elevation_degrees)
        second_elevation = np.deg2rad(second_elevation_degrees)
        first = [
            np.cos(first_elevation) * horizontal[0],
            np.cos(first_elevation) * horizontal[1],
            np.sin(first_elevation),
        ]
        second = [
            -np.cos(second_elevation) * horizontal[0],
            -np.cos(second_elevation) * horizontal[1],
            np.sin(second_elevation),
        ]
        geometry.append(
            [[float(value) for value in first], [float(value) for value in second]]
        )
    return geometry


def controlled_parameter_scan() -> list[dict[str, float | str]]:
    """Scan direction, anisotropy, range weight, and controlled clock dynamics."""
    epochs = 5
    records: list[dict[str, float | str]] = []
    for clock_model in ("constant", "random_walk", "bias_drift"):
        clock_information = clock_process_information(epochs, clock_model)
        for strong_to_weak_ratio in (10.0, 100.0, 1000.0):
            for range_information in (0.1, 1.0, 10.0):
                for angle_degrees in range(0, 91, 15):
                    result = marginal_benefit_scenario(
                        "parameter_scan",
                        angular_range_geometry(float(angle_degrees), epochs),
                        clock_model,
                        [1, 0, 0],
                        weak_information=1.0,
                        strong_information=strong_to_weak_ratio,
                        initial_prior_information=100.0,
                        range_information=range_information,
                        clock_information=clock_information,
                    )
                    records.append(
                        {
                            "clock_model": clock_model,
                            "strong_to_weak_ratio": strong_to_weak_ratio,
                            "range_information": range_information,
                            "horizontal_los_difference_to_weak_angle_degrees": float(
                                angle_degrees
                            ),
                            "prior_weak_variance": result.prior_variance,
                            "posterior_weak_variance": result.posterior_variance,
                            "relative_variance_reduction": result.relative_variance_reduction,
                        }
                    )
    return records


def controlled_clock_sensitivity_scenarios() -> list[MarginalBenefitResult]:
    """Compare clock models when one range per epoch cannot cancel clock directly."""
    epochs = 5
    lines_of_sight = [[[1, 0, 1]] for _ in range(epochs)]
    results = []
    for clock_model in ("constant", "random_walk", "bias_drift", "independent"):
        results.append(
            marginal_benefit_scenario(
                f"one_range_per_epoch_{clock_model}",
                lines_of_sight,
                clock_model,
                [1, 0, 0],
                clock_information=clock_process_information(epochs, clock_model),
            )
        )
    return results


def physical_prior_sensitivity_scan() -> list[dict[str, float | str]]:
    """Audit position/clock prior dependence using explicitly dimensioned inputs."""
    epochs = 10
    lines_of_sight = [[[1, 0, 1]] for _ in range(epochs)]
    records: list[dict[str, float | str]] = []
    for clock_model in ("random_walk", "bias_drift"):
        for position_sigma_metres in (0.1, 1.0, 10.0):
            for clock_sigma_metres in (0.1, 1.0, 10.0, 100.0, 1_000_000.0):
                clock_information = physical_clock_process_information(
                    epochs,
                    clock_model,
                    time_step_seconds=1.0,
                    initial_bias_sigma_metres=clock_sigma_metres,
                    initial_drift_sigma_metres_per_second=1.0,
                    bias_rw_density_metres_per_sqrt_second=1.0,
                    drift_rw_density_metres_per_second_per_sqrt_second=0.1,
                )
                result = marginal_benefit_scenario(
                    "physical_prior_scan",
                    lines_of_sight,
                    clock_model,
                    [1, 0, 0],
                    weak_information=1.0,
                    strong_information=100.0,
                    initial_prior_information=1.0 / position_sigma_metres**2,
                    clock_information=clock_information,
                    range_sigmas_metres=[10.0] * epochs,
                )
                records.append(
                    {
                        "clock_model": clock_model,
                        "initial_position_sigma_m": position_sigma_metres,
                        "initial_clock_bias_sigma_m": clock_sigma_metres,
                        "initial_clock_drift_sigma_m_per_s": 1.0,
                        "bias_rw_density_m_per_sqrt_s": 1.0,
                        "drift_rw_density_m_per_s_per_sqrt_s": 0.1,
                        "range_sigma_m": 10.0,
                        "prior_weak_std_m": round(np.sqrt(result.prior_variance), 12),
                        "posterior_weak_std_m": round(
                            np.sqrt(result.posterior_variance), 12
                        ),
                        "relative_variance_reduction": result.relative_variance_reduction,
                        "prior_absolute_std_m": result.prior_absolute_std_metres,
                        "posterior_absolute_std_m": result.posterior_absolute_std_metres,
                        "absolute_relative_variance_reduction": (
                            result.absolute_relative_variance_reduction
                        ),
                        "prior_relative_displacement_std_m": (
                            result.prior_relative_displacement_std_metres
                        ),
                        "posterior_relative_displacement_std_m": (
                            result.posterior_relative_displacement_std_metres
                        ),
                        "relative_displacement_variance_reduction": (
                            result.relative_displacement_variance_reduction
                        ),
                    }
                )
    return records


def asymmetric_geometry_scan() -> list[dict[str, float | str]]:
    """Compare symmetric and one-at-a-time perturbed two-range geometries."""
    epochs = 10
    clock_model = "bias_drift"
    clock_information = physical_clock_process_information(
        epochs, clock_model, 1.0, 10.0, 1.0, 1.0, 0.1
    )
    configurations = (
        ("symmetric", 45.0, 45.0, 10.0, 10.0, 0.0),
        ("elevation_asymmetry", 45.0, 35.0, 10.0, 10.0, 0.0),
        ("noise_asymmetry", 45.0, 45.0, 10.0, 20.0, 0.0),
        ("time_varying_azimuth", 45.0, 45.0, 10.0, 10.0, 1.0),
    )
    records: list[dict[str, float | str]] = []
    for (
        name,
        first_elevation,
        second_elevation,
        first_sigma,
        second_sigma,
        drift,
    ) in configurations:
        for angle_degrees in range(0, 91, 15):
            geometry = perturbed_angular_range_geometry(
                float(angle_degrees), epochs, first_elevation, second_elevation, drift
            )
            result = marginal_benefit_scenario(
                name,
                geometry,
                clock_model,
                [1, 0, 0],
                weak_information=1.0,
                strong_information=100.0,
                initial_prior_information=1.0,
                clock_information=clock_information,
                range_sigmas_metres=[first_sigma, second_sigma] * epochs,
            )
            records.append(
                {
                    "geometry": name,
                    "initial_horizontal_los_difference_to_weak_angle_degrees": float(
                        angle_degrees
                    ),
                    "first_elevation_degrees": first_elevation,
                    "second_elevation_degrees": second_elevation,
                    "first_range_sigma_m": first_sigma,
                    "second_range_sigma_m": second_sigma,
                    "azimuth_drift_degrees_per_epoch": drift,
                    "prior_weak_std_m": round(np.sqrt(result.prior_variance), 12),
                    "posterior_weak_std_m": round(
                        np.sqrt(result.posterior_variance), 12
                    ),
                    "relative_variance_reduction": result.relative_variance_reduction,
                    "prior_absolute_std_m": result.prior_absolute_std_metres,
                    "posterior_absolute_std_m": result.posterior_absolute_std_metres,
                    "absolute_relative_variance_reduction": (
                        result.absolute_relative_variance_reduction
                    ),
                    "prior_relative_displacement_std_m": (
                        result.prior_relative_displacement_std_metres
                    ),
                    "posterior_relative_displacement_std_m": (
                        result.posterior_relative_displacement_std_metres
                    ),
                    "relative_displacement_variance_reduction": (
                        result.relative_displacement_variance_reduction
                    ),
                }
            )
    return records


def initial_drift_prior_sensitivity_scan() -> list[dict[str, float | str]]:
    """Vary only initial clock-drift prior while all other inputs remain fixed."""
    epochs = 10
    geometry = [[[1, 0, 1]] for _ in range(epochs)]
    records: list[dict[str, float | str]] = []
    for drift_sigma in (0.01, 0.1, 1.0, 10.0, 1_000_000.0):
        clock_information = physical_clock_process_information(
            epochs, "bias_drift", 1.0, 10.0, drift_sigma, 1.0, 0.1
        )
        result = marginal_benefit_scenario(
            "initial_drift_prior_scan",
            geometry,
            "bias_drift",
            [1, 0, 0],
            weak_information=1.0,
            strong_information=100.0,
            initial_prior_information=1.0,
            clock_information=clock_information,
            range_sigmas_metres=[10.0] * epochs,
        )
        records.append(
            {
                "initial_clock_drift_sigma_m_per_s": drift_sigma,
                "fixed_initial_position_sigma_m": 1.0,
                "fixed_initial_clock_bias_sigma_m": 10.0,
                "fixed_bias_rw_density_m_per_sqrt_s": 1.0,
                "fixed_drift_rw_density_m_per_s_per_sqrt_s": 0.1,
                "fixed_range_sigma_m": 10.0,
                "fixed_time_step_s": 1.0,
                "prior_absolute_std_m": result.prior_absolute_std_metres,
                "posterior_absolute_std_m": result.posterior_absolute_std_metres,
                "absolute_relative_variance_reduction": (
                    result.absolute_relative_variance_reduction
                ),
                "prior_relative_displacement_std_m": (
                    result.prior_relative_displacement_std_metres
                ),
                "posterior_relative_displacement_std_m": (
                    result.posterior_relative_displacement_std_metres
                ),
                "relative_displacement_variance_reduction": (
                    result.relative_displacement_variance_reduction
                ),
            }
        )
    return records


def matrix_rank_and_nullity(information: np.ndarray) -> tuple[int, int]:
    rank = numerical_rank(information)
    return rank, information.shape[0] - rank


def strict_prior_observability_audit() -> list[dict[str, float | int | str | bool]]:
    """Remove priors exactly and report ranks plus estimability of two quantities."""
    epochs = 5
    geometry = perturbed_angular_range_geometry(30.0, epochs, 45.0, 35.0, 1.0)
    records: list[dict[str, float | int | str | bool]] = []
    configurations = (
        ("all_priors", True, True, True),
        ("no_clock_bias_prior", True, False, True),
        ("no_clock_drift_prior", True, True, False),
        ("no_clock_priors", True, False, False),
        ("no_position_prior", False, True, True),
        ("no_priors", False, False, False),
    )
    for clock_model in ("random_walk", "bias_drift"):
        for name, position_prior, bias_prior, drift_prior in configurations:
            if clock_model == "random_walk" and name == "no_clock_drift_prior":
                continue
            position_information = odometry_position_information(
                epochs, [1, 0, 0], 1.0, 100.0, 1.0 if position_prior else 0.0
            )
            clock_information = physical_clock_process_information(
                epochs,
                clock_model,
                1.0,
                10.0 if bias_prior else None,
                1.0 if drift_prior else None,
                1.0,
                0.1,
            )
            h_position, h_clock = range_jacobians(geometry, clock_model)
            scale = 1.0 / 10.0
            prior_joint = assemble_joint_information(
                position_information,
                scale * h_position,
                scale * h_clock,
                clock_information,
                False,
            )
            posterior_joint = assemble_joint_information(
                position_information,
                scale * h_position,
                scale * h_clock,
                clock_information,
                True,
            )
            clock_rank, clock_nullity = matrix_rank_and_nullity(clock_information)
            prior_rank, prior_nullity = matrix_rank_and_nullity(prior_joint)
            posterior_rank, posterior_nullity = matrix_rank_and_nullity(posterior_joint)
            absolute = metric_from_joint_systems(
                prior_joint,
                posterior_joint,
                position_direction_functional(epochs, [1, 0, 0], "absolute_position"),
            )
            displacement = metric_from_joint_systems(
                prior_joint,
                posterior_joint,
                position_direction_functional(
                    epochs, [1, 0, 0], "relative_displacement"
                ),
            )
            records.append(
                {
                    "clock_model": clock_model,
                    "configuration": name,
                    "position_prior_present": position_prior,
                    "clock_bias_prior_present": bias_prior,
                    "clock_drift_prior_present": (
                        drift_prior if clock_model == "bias_drift" else "not_applicable"
                    ),
                    "clock_process_rank": clock_rank,
                    "clock_process_nullity": clock_nullity,
                    "unassisted_full_rank": prior_rank,
                    "unassisted_full_nullity": prior_nullity,
                    "assisted_full_rank": posterior_rank,
                    "assisted_full_nullity": posterior_nullity,
                    "unassisted_absolute_position_observable": absolute[0] is not None,
                    "assisted_absolute_position_observable": absolute[1] is not None,
                    "unassisted_absolute_std_m": absolute[0] or "",
                    "assisted_absolute_std_m": absolute[1] or "",
                    "unassisted_relative_displacement_observable": displacement[0]
                    is not None,
                    "assisted_relative_displacement_observable": displacement[1]
                    is not None,
                    "unassisted_relative_displacement_std_m": displacement[0] or "",
                    "assisted_relative_displacement_std_m": displacement[1] or "",
                }
            )
    return records


def representative_clock_geometry_comparison() -> list[dict[str, float | str | bool]]:
    """Compare four clock models on a small, declared set of geometries."""
    epochs = 10
    geometries = {
        "symmetric_aligned": perturbed_angular_range_geometry(0.0, epochs, 45.0, 45.0),
        "elevation_asymmetric_45deg": perturbed_angular_range_geometry(
            45.0, epochs, 45.0, 35.0
        ),
        "time_varying_45deg": perturbed_angular_range_geometry(
            45.0, epochs, 45.0, 45.0, 1.0
        ),
    }
    records: list[dict[str, float | str | bool]] = []
    for geometry_name, geometry in geometries.items():
        for clock_model in ("independent", "constant", "random_walk", "bias_drift"):
            bias_prior = clock_model in {"random_walk", "bias_drift"}
            drift_prior = clock_model == "bias_drift"
            clock_information = physical_clock_process_information(
                epochs,
                clock_model,
                1.0,
                10.0 if bias_prior else None,
                1.0 if drift_prior else None,
                1.0,
                0.1,
            )
            result = marginal_benefit_scenario(
                "representative_clock_geometry",
                geometry,
                clock_model,
                [1, 0, 0],
                weak_information=1.0,
                strong_information=100.0,
                initial_prior_information=1.0,
                clock_information=clock_information,
                range_sigmas_metres=[10.0] * (2 * epochs),
            )
            records.append(
                {
                    "geometry": geometry_name,
                    "clock_model": clock_model,
                    "initial_position_sigma_m": 1.0,
                    "initial_clock_bias_prior_present": bias_prior,
                    "initial_clock_bias_sigma_m": 10.0 if bias_prior else "",
                    "initial_clock_drift_prior_present": drift_prior,
                    "initial_clock_drift_sigma_m_per_s": 1.0 if drift_prior else "",
                    "bias_rw_density_m_per_sqrt_s": (
                        1.0 if clock_model in {"random_walk", "bias_drift"} else ""
                    ),
                    "drift_rw_density_m_per_s_per_sqrt_s": (
                        0.1 if clock_model == "bias_drift" else ""
                    ),
                    "range_sigma_m": 10.0,
                    "prior_absolute_std_m": result.prior_absolute_std_metres,
                    "posterior_absolute_std_m": result.posterior_absolute_std_metres,
                    "absolute_relative_variance_reduction": (
                        result.absolute_relative_variance_reduction
                    ),
                    "prior_relative_displacement_std_m": (
                        result.prior_relative_displacement_std_metres
                    ),
                    "posterior_relative_displacement_std_m": (
                        result.posterior_relative_displacement_std_metres
                    ),
                    "relative_displacement_variance_reduction": (
                        result.relative_displacement_variance_reduction
                    ),
                }
            )
    return records


def write_audit_figures(directory: Path) -> None:
    """Render deterministic SVG curves for priors, drift prior, and geometry metrics."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    matplotlib.rcParams["svg.hashsalt"] = "lunar-pnt-observability-audit"
    directory.mkdir(parents=True, exist_ok=True)

    prior_records = [
        record
        for record in physical_prior_sensitivity_scan()
        if float(record["initial_position_sigma_m"]) == 1.0
    ]
    figure, axes = plt.subplots(1, 2, figsize=(10, 4))
    for model in ("random_walk", "bias_drift"):
        selected = [
            record for record in prior_records if record["clock_model"] == model
        ]
        x = [float(record["initial_clock_bias_sigma_m"]) for record in selected]
        axes[0].plot(
            x,
            [float(record["posterior_absolute_std_m"]) for record in selected],
            marker="o",
            label=model,
        )
        axes[1].plot(
            x,
            [
                float(record["posterior_relative_displacement_std_m"])
                for record in selected
            ],
            marker="o",
            label=model,
        )
    axes[0].axhline(
        float(prior_records[0]["prior_absolute_std_m"]),
        color="black",
        linestyle="--",
        label="unassisted",
    )
    axes[1].axhline(
        float(prior_records[0]["prior_relative_displacement_std_m"]),
        color="black",
        linestyle="--",
        label="unassisted",
    )
    for axis, title in zip(axes, ("Absolute $p_T$", "Relative $p_T-p_0$")):
        axis.set_xscale("log")
        axis.set_xlabel("Initial clock-bias prior sigma (m)")
        axis.set_ylabel("Posterior weak-direction std (m)")
        axis.set_title(title)
        axis.grid(True, alpha=0.3)
        axis.legend()
    figure.tight_layout()
    figure.savefig(
        directory / "initial_clock_bias_prior.svg",
        format="svg",
        metadata={"Date": None},
    )
    plt.close(figure)

    drift_records = initial_drift_prior_sensitivity_scan()
    figure, axis = plt.subplots(figsize=(6, 4))
    x = [float(record["initial_clock_drift_sigma_m_per_s"]) for record in drift_records]
    axis.plot(
        x,
        [float(record["posterior_absolute_std_m"]) for record in drift_records],
        marker="o",
        label="absolute $p_T$",
    )
    axis.plot(
        x,
        [
            float(record["posterior_relative_displacement_std_m"])
            for record in drift_records
        ],
        marker="s",
        label="relative $p_T-p_0$",
    )
    axis.axhline(
        float(drift_records[0]["prior_absolute_std_m"]),
        color="tab:blue",
        linestyle="--",
        label="unassisted absolute",
    )
    axis.axhline(
        float(drift_records[0]["prior_relative_displacement_std_m"]),
        color="tab:orange",
        linestyle="--",
        label="unassisted relative",
    )
    axis.set_xscale("log")
    axis.set_xlabel("Initial clock-drift prior sigma (m/s)")
    axis.set_ylabel("Posterior weak-direction std (m)")
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(
        directory / "initial_clock_drift_prior.svg",
        format="svg",
        metadata={"Date": None},
    )
    plt.close(figure)

    geometry_records = asymmetric_geometry_scan()
    figure, axes = plt.subplots(1, 2, figsize=(11, 4))
    angle_field = "initial_horizontal_los_difference_to_weak_angle_degrees"
    for geometry in (
        "symmetric",
        "elevation_asymmetry",
        "noise_asymmetry",
        "time_varying_azimuth",
    ):
        selected = [
            record for record in geometry_records if record["geometry"] == geometry
        ]
        x = [float(record[angle_field]) for record in selected]
        axes[0].plot(
            x,
            [float(record["posterior_absolute_std_m"]) for record in selected],
            marker="o",
            label=geometry,
        )
        axes[1].plot(
            x,
            [
                float(record["posterior_relative_displacement_std_m"])
                for record in selected
            ],
            marker="o",
            label=geometry,
        )
    axes[0].axhline(
        float(geometry_records[0]["prior_absolute_std_m"]),
        color="black",
        linestyle="--",
        label="unassisted",
    )
    axes[1].axhline(
        float(geometry_records[0]["prior_relative_displacement_std_m"]),
        color="black",
        linestyle="--",
        label="unassisted",
    )
    for axis, title in zip(axes, ("Absolute $p_T$", "Relative $p_T-p_0$")):
        axis.set_xlabel("Horizontal LOS-difference / weak-direction angle (deg)")
        axis.set_ylabel("Posterior weak-direction std (m)")
        axis.set_title(title)
        axis.grid(True, alpha=0.3)
    axes[0].legend(fontsize=7)
    axes[1].legend(fontsize=7)
    figure.tight_layout()
    figure.savefig(
        directory / "geometry_absolute_vs_relative.svg",
        format="svg",
        metadata={"Date": None},
    )
    plt.close(figure)

    # Matplotlib emits trailing spaces in multi-line SVG path data. Normalize the
    # text so repository whitespace checks and generated-file comparisons pass.
    for svg_path in directory.glob("*.svg"):
        lines = svg_path.read_text(encoding="utf-8").splitlines()
        svg_path.write_text(
            "\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8"
        )


def write_parameter_scan(path: Path, records: list[dict[str, float | str]]) -> None:
    """Write parameter scan records as deterministic CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(records[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="optional JSON output path")
    parser.add_argument(
        "--scan-output", type=Path, help="optional parameter-scan CSV path"
    )
    parser.add_argument(
        "--prior-scan-output", type=Path, help="optional prior-scan CSV path"
    )
    parser.add_argument(
        "--geometry-scan-output", type=Path, help="optional perturbed-geometry CSV path"
    )
    parser.add_argument(
        "--drift-prior-output", type=Path, help="optional drift-prior CSV"
    )
    parser.add_argument(
        "--rank-audit-output", type=Path, help="optional strict-rank CSV"
    )
    parser.add_argument(
        "--clock-geometry-output", type=Path, help="optional representative-model CSV"
    )
    parser.add_argument(
        "--figure-dir", type=Path, help="optional output directory for PNGs"
    )
    args = parser.parse_args()
    payload = {
        "scope": "controlled linearized geometry; not a lunar performance result",
        "clock_unit": "metres",
        "range_weight": "unit information",
        "results": [asdict(result) for result in controlled_scenarios()],
        "marginal_benefit_assumptions": {
            "epochs": 5,
            "weak_increment_information": 1.0,
            "strong_increment_information": 100.0,
            "initial_position_information": 100.0,
            "weak_direction": [1, 0, 0],
            "warning": "synthetic geometry and unit weights; not performance parameters",
        },
        "marginal_benefit_results": [
            asdict(result) for result in controlled_marginal_benefit_scenarios()
        ],
        "clock_sensitivity_assumptions": {
            "bias_random_walk_information": 1.0,
            "drift_random_walk_information": 1.0,
            "initial_bias_information": 0.01,
            "initial_drift_information": 1.0,
            "time_step": 1.0,
            "warning": "controlled dimensionless information; not a physical oscillator model",
        },
        "clock_sensitivity_results": [
            asdict(result) for result in controlled_clock_sensitivity_scenarios()
        ],
    }
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    if args.scan_output:
        write_parameter_scan(args.scan_output, controlled_parameter_scan())
    if args.prior_scan_output:
        write_parameter_scan(args.prior_scan_output, physical_prior_sensitivity_scan())
    if args.geometry_scan_output:
        write_parameter_scan(args.geometry_scan_output, asymmetric_geometry_scan())
    if args.drift_prior_output:
        write_parameter_scan(
            args.drift_prior_output, initial_drift_prior_sensitivity_scan()
        )
    if args.rank_audit_output:
        write_parameter_scan(args.rank_audit_output, strict_prior_observability_audit())
    if args.clock_geometry_output:
        write_parameter_scan(
            args.clock_geometry_output, representative_clock_geometry_comparison()
        )
    if args.figure_dir:
        write_audit_figures(args.figure_dir)
    print(rendered, end="")


if __name__ == "__main__":
    main()
