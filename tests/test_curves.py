from thinkbook_fan.curves import (
    compute_target,
    desired_level,
    level_threshold,
    median_window,
)

CURVE = ((88, 7), (81, 6), (74, 5), (66, 4), (0, 0))


def test_desired_level_uses_threshold_and_lowest_point():
    assert desired_level(90, CURVE) == 7
    assert desired_level(88, CURVE) == 7
    assert desired_level(80, CURVE) == 5
    assert desired_level(10, CURVE) == 0
    assert desired_level(-5, CURVE) == 0


def test_level_threshold_handles_skipped_levels():
    assert level_threshold(4, CURVE) == 66
    assert level_threshold(0, CURVE) == 0
    assert level_threshold(3, CURVE) is None


def test_target_steps_up_one_level():
    assert (
        compute_target(
            current=2,
            want=5,
            curve=CURVE,
            control_temp=80,
            min_level=0,
            max_level=7,
            pin_active=False,
            emergency=False,
            hysteresis_c=3,
        )
        == 3
    )


def test_target_steps_down_outside_hysteresis():
    assert (
        compute_target(
            current=4,
            want=0,
            curve=CURVE,
            control_temp=62,
            min_level=0,
            max_level=7,
            pin_active=False,
            emergency=False,
            hysteresis_c=3,
        )
        == 3
    )


def test_target_holds_inside_hysteresis():
    assert (
        compute_target(
            current=4,
            want=0,
            curve=CURVE,
            control_temp=65,
            min_level=0,
            max_level=7,
            pin_active=False,
            emergency=False,
            hysteresis_c=3,
        )
        == 4
    )


def test_pin_emergency_and_floor():
    common = dict(
        current=3,
        want=3,
        curve=CURVE,
        control_temp=50,
        min_level=0,
        max_level=7,
        hysteresis_c=3,
    )
    assert compute_target(pin_active=True, emergency=False, **common) == 3
    assert compute_target(pin_active=False, emergency=True, **common) == 7
    assert (
        compute_target(
            current=1,
            want=0,
            curve=CURVE,
            control_temp=50,
            min_level=1,
            max_level=7,
            pin_active=False,
            emergency=False,
            hysteresis_c=3,
        )
        == 1
    )


def test_median_window():
    assert median_window([100, 40, 42], 3) == 42
    assert median_window([100, 40, 42], 2) == 42
    assert median_window([], 3) == 0.0
