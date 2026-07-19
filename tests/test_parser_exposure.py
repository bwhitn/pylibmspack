from scripts import check_parser_exposure


def test_parser_exposure_check_passes(capsys):
    assert check_parser_exposure.main() == 0
    assert "parser exposure checks passed" in capsys.readouterr().out
