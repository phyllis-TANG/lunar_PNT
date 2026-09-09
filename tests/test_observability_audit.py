import unittest

import numpy as np

from tools.observability_audit import (
    audit_scenario,
    angular_range_geometry,
    asymmetric_geometry_scan,
    clock_marginalized_information,
    clock_process_information,
    controlled_clock_sensitivity_scenarios,
    controlled_marginal_benefit_scenarios,
    controlled_parameter_scan,
    final_direction_variance,
    initial_drift_prior_sensitivity_scan,
    matrix_rank_and_nullity,
    odometry_position_information,
    perturbed_angular_range_geometry,
    physical_clock_process_information,
    physical_prior_sensitivity_scan,
    position_direction_functional,
    range_jacobians,
    representative_clock_geometry_comparison,
    strict_prior_observability_audit,
)


class ObservabilityAuditTest(unittest.TestCase):
    def test_one_satellite_is_absorbed_by_free_clock(self) -> None:
        result = audit_scenario("one", [[[1, 0, 0]]], "independent")
        self.assertEqual(result.effective_position_rank, 0)

    def test_m_satellites_leave_at_most_m_minus_one_directions(self) -> None:
        geometries = [
            [[1, 0, 0]],
            [[1, 0, 0], [0, 1, 0]],
            [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            [[1, 0, 0], [0, 1, 0], [0, 0, 1], [-1, -1, -1]],
        ]
        self.assertEqual(
            [
                audit_scenario(
                    str(i), [geometry], "independent"
                ).effective_position_rank
                for i, geometry in enumerate(geometries)
            ],
            [0, 1, 2, 3],
        )

    def test_free_clock_each_epoch_absorbs_one_satellite_each_epoch(self) -> None:
        lines = [[[1, 0, 0]], [[0, 1, 0]], [[0, 0, 1]]]
        result = audit_scenario("free", lines, "independent")
        self.assertEqual(result.effective_position_rank, 0)

    def test_shared_clock_couples_epochs(self) -> None:
        lines = [[[1, 0, 0]], [[1, 0, 0]], [[1, 0, 0]]]
        result = audit_scenario("shared", lines, "constant")
        self.assertEqual(result.effective_position_rank, 2)

    def test_positive_clock_prior_restores_single_range_direction(self) -> None:
        h_position, h_clock = range_jacobians([[[1, 0, 0]]], "constant")
        effective = clock_marginalized_information(
            h_position, h_clock, np.array([[1.0]])
        )
        self.assertEqual(np.linalg.matrix_rank(effective), 1)
        self.assertAlmostEqual(float(effective[0, 0]), 0.5)

    def test_zero_line_of_sight_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-zero"):
            range_jacobians([[[0, 0, 0]]], "constant")

    def test_anisotropic_odometry_has_expected_accumulated_variance(self) -> None:
        information = odometry_position_information(5, [1, 0, 0], 1.0, 100.0, 100.0)
        covariance = np.linalg.inv(information)
        self.assertAlmostEqual(final_direction_variance(covariance, 5, [1, 0, 0]), 4.01)
        self.assertAlmostEqual(final_direction_variance(covariance, 5, [0, 1, 0]), 0.05)

    def test_range_alignment_changes_weak_direction_benefit(self) -> None:
        aligned, orthogonal = controlled_marginal_benefit_scenarios()
        self.assertGreater(aligned.relative_variance_reduction, 0.8)
        self.assertAlmostEqual(orthogonal.relative_variance_reduction, 0.0)

    def test_odometry_can_strictly_remove_gauge_prior(self) -> None:
        information = odometry_position_information(3, [1, 0, 0], 1.0, 10.0, 0.0)
        self.assertEqual(matrix_rank_and_nullity(information), (6, 3))

    def test_random_walk_and_bias_drift_clock_information_is_positive_definite(
        self,
    ) -> None:
        for model in ("random_walk", "bias_drift"):
            eigenvalues = np.linalg.eigvalsh(clock_process_information(5, model))
            self.assertGreater(float(eigenvalues[0]), 0.0)

    def test_bias_drift_range_rows_measure_bias_not_drift(self) -> None:
        _, h_clock = range_jacobians([[[1, 0, 1]]] * 3, "bias_drift")
        self.assertEqual(h_clock.shape, (3, 6))
        np.testing.assert_array_equal(h_clock[:, 3:], np.zeros((3, 3)))

    def test_scan_benefit_decreases_continuously_with_misalignment(self) -> None:
        records = controlled_parameter_scan()
        self.assertEqual(len(records), 3 * 3 * 3 * 7)
        groups: dict[tuple[str, float, float], list[float]] = {}
        for record in records:
            key = (
                str(record["clock_model"]),
                float(record["strong_to_weak_ratio"]),
                float(record["range_information"]),
            )
            groups.setdefault(key, []).append(
                float(record["relative_variance_reduction"])
            )
        for benefits in groups.values():
            self.assertTrue(
                all(first >= second for first, second in zip(benefits, benefits[1:])),
                benefits,
            )
            self.assertGreater(benefits[0], benefits[-1])

    def test_angular_geometry_rejects_out_of_range_angle(self) -> None:
        with self.assertRaisesRegex(ValueError, "between"):
            angular_range_geometry(91.0, 3)

    def test_single_range_benefit_depends_on_clock_model(self) -> None:
        results = controlled_clock_sensitivity_scenarios()
        reductions = [result.relative_variance_reduction for result in results]
        self.assertTrue(
            all(first > second for first, second in zip(reductions, reductions[1:])),
            reductions,
        )
        self.assertAlmostEqual(reductions[-1], 0.0)

    def test_physical_random_walk_uses_sigma_squared_times_dt(self) -> None:
        information = physical_clock_process_information(
            2, "random_walk", 4.0, 2.0, 1.0, 3.0, 0.5
        )
        expected_step_information = 1.0 / (3.0**2 * 4.0)
        self.assertAlmostEqual(information[0, 1], -expected_step_information)
        self.assertAlmostEqual(
            information[0, 0], 1.0 / 2.0**2 + expected_step_information
        )

    def test_loosening_clock_prior_does_not_increase_single_range_benefit(self) -> None:
        records = physical_prior_sensitivity_scan()
        self.assertEqual(len(records), 2 * 3 * 5)
        groups: dict[tuple[str, float], list[float]] = {}
        for record in records:
            key = (
                str(record["clock_model"]),
                float(record["initial_position_sigma_m"]),
            )
            groups.setdefault(key, []).append(
                float(record["relative_variance_reduction"])
            )
        for benefits in groups.values():
            self.assertTrue(
                all(first >= second for first, second in zip(benefits, benefits[1:])),
                benefits,
            )

    def test_perturbed_geometry_has_positive_elevation(self) -> None:
        geometry = perturbed_angular_range_geometry(30.0, 4, 45.0, 35.0, 1.0)
        self.assertEqual(len(geometry), 4)
        self.assertTrue(all(line[2] > 0.0 for epoch in geometry for line in epoch))

    def test_asymmetric_scan_is_finite_and_not_forced_to_zero_at_ninety(self) -> None:
        records = asymmetric_geometry_scan()
        self.assertEqual(len(records), 4 * 7)
        values = np.asarray(
            [float(record["relative_variance_reduction"]) for record in records]
        )
        self.assertTrue(np.all(np.isfinite(values)))
        perturbed_at_ninety = [
            float(record["relative_variance_reduction"])
            for record in records
            if float(record["initial_horizontal_los_difference_to_weak_angle_degrees"])
            == 90.0
            and record["geometry"] != "symmetric"
        ]
        self.assertTrue(any(value > 0.0 for value in perturbed_at_ninety))

    def test_relative_displacement_functional_contains_both_endpoints(self) -> None:
        functional = position_direction_functional(
            3, [1, 0, 0], "relative_displacement"
        )
        np.testing.assert_array_equal(
            functional, np.array([-1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0])
        )

    def test_relative_displacement_uses_cross_time_covariance(self) -> None:
        covariance = np.zeros((6, 6))
        covariance[0, 0] = 4.0
        covariance[3, 3] = 9.0
        covariance[0, 3] = covariance[3, 0] = 2.5
        functional = position_direction_functional(
            2, [1, 0, 0], "relative_displacement"
        )
        self.assertAlmostEqual(float(functional @ covariance @ functional), 8.0)
        self.assertNotAlmostEqual(float(functional @ covariance @ functional), 13.0)

    def test_clock_process_without_initial_prior_has_expected_nullity(self) -> None:
        random_walk = physical_clock_process_information(
            5, "random_walk", 1.0, None, None, 1.0, 0.1
        )
        bias_drift = physical_clock_process_information(
            5, "bias_drift", 1.0, None, None, 1.0, 0.1
        )
        self.assertEqual(matrix_rank_and_nullity(random_walk), (4, 1))
        self.assertEqual(matrix_rank_and_nullity(bias_drift), (8, 2))

    def test_strict_prior_audit_marks_absolute_unobservable_without_position_prior(
        self,
    ) -> None:
        records = strict_prior_observability_audit()
        no_position = [
            record
            for record in records
            if record["configuration"] == "no_position_prior"
        ]
        self.assertTrue(no_position)
        self.assertTrue(
            all(
                not record["unassisted_absolute_position_observable"]
                for record in no_position
            )
        )
        self.assertTrue(
            all(
                record["unassisted_relative_displacement_observable"]
                for record in no_position
            )
        )
        self.assertTrue(
            all(record["unassisted_absolute_std_m"] == "" for record in no_position)
        )
        no_priors = [
            record for record in records if record["configuration"] == "no_priors"
        ]
        self.assertTrue(
            all(
                record["assisted_relative_displacement_observable"]
                for record in no_priors
            )
        )

    def test_drift_prior_scan_changes_only_declared_prior(self) -> None:
        records = initial_drift_prior_sensitivity_scan()
        self.assertEqual(len(records), 5)
        fixed_fields = (
            "fixed_initial_position_sigma_m",
            "fixed_initial_clock_bias_sigma_m",
            "fixed_bias_rw_density_m_per_sqrt_s",
            "fixed_drift_rw_density_m_per_s_per_sqrt_s",
            "fixed_range_sigma_m",
            "fixed_time_step_s",
        )
        for field in fixed_fields:
            self.assertEqual(len({record[field] for record in records}), 1)

    def test_representative_comparison_declares_clock_prior_differences(self) -> None:
        records = representative_clock_geometry_comparison()
        self.assertEqual(len(records), 3 * 4)
        independent = [
            record for record in records if record["clock_model"] == "independent"
        ]
        bias_drift = [
            record for record in records if record["clock_model"] == "bias_drift"
        ]
        self.assertTrue(
            all(
                not record["initial_clock_bias_prior_present"] for record in independent
            )
        )
        self.assertTrue(
            all(record["initial_clock_drift_prior_present"] for record in bias_drift)
        )


if __name__ == "__main__":
    unittest.main()
