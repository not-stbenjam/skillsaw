"""CLI deprecation notices for features leaving after 0.20.0."""

from tests.cli_runner import run_cli


def _warning(command: str) -> str:
    return (
        f"Warning: 'skillsaw {command}' is deprecated and will be removed "
        "in an upcoming release."
    )


def _assert_one_stderr_warning(result, command: str) -> None:
    warning = _warning(command)
    assert result.stderr.count(warning) == 1
    assert warning not in result.stdout


def test_deprecated_command_help_warns_once_per_invocation() -> None:
    for command in ("add",):
        for _ in range(2):
            result = run_cli([command, "--help"])
            assert result.returncode == 0
            assert "Deprecated:" in result.stdout
            _assert_one_stderr_warning(result, command)


def test_add_still_scaffolds_with_one_deprecation_warning(tmp_path) -> None:
    result = run_cli(["add", "skill", "release-helper", "--path", tmp_path])

    assert result.returncode == 0
    assert (tmp_path / "release-helper" / "SKILL.md").is_file()
    _assert_one_stderr_warning(result, "add")


def test_deprecated_command_parse_errors_still_warn_once() -> None:
    for command, args in (("add", ["add", "unknown-component"]),):
        result = run_cli(args)

        assert result.returncode == 2
        assert result.stdout == ""
        _assert_one_stderr_warning(result, command)


def test_unrelated_command_has_no_feature_deprecation_warning() -> None:
    result = run_cli(["list-rules"])

    assert result.returncode == 0
    assert "is deprecated and will be removed in an upcoming release" not in result.stderr
    assert "is deprecated and will be removed in an upcoming release" not in result.stdout
