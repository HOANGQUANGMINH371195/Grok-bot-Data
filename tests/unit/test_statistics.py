import pytest
from vda_data.statistics import StatisticsError, chi_square, welch_t


def test_bounded_statistics_pin_assumptions_alpha_and_holm() -> None:
    result = welch_t((1.0, 2.0, 3.0), (3.0, 4.0, 5.0), family="sales", correction="holm")
    assert result.test == "welch_t"
    assert result.family == "sales"
    assert result.correction == "holm"
    assert result.limitations == ("descriptive association; not a causal claim",)
    chi = chi_square(((10, 5), (4, 11)))
    assert chi.test == "chi_square"


def test_statistics_reject_nonfinite_or_unbounded_inputs() -> None:
    with pytest.raises(StatisticsError, match="finite"):
        welch_t((1.0, float("nan")), (2.0, 3.0))
    with pytest.raises(StatisticsError, match="2x2"):
        chi_square(((1,),))
