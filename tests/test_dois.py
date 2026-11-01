import pytest

from doi_paper_downloader.dois import normalize_doi, read_dois, safe_filename


@pytest.mark.parametrize("raw, expected", [
    ("10.1038/s41586-020-2649-2", "10.1038/s41586-020-2649-2"),
    ("  10.1021/jp400894v  ", "10.1021/jp400894v"),
    ("https://doi.org/10.1000/example", "10.1000/example"),
    ("http://dx.doi.org/10.1000/example", "10.1000/example"),
    ("doi: 10.1000/example", "10.1000/example"),
    ("DOI:10.1000/example.", "10.1000/example"),
    ("see (10.1000/example), thanks", "10.1000/example"),
    ("10.1016/S0021-9258(18)00001-2", "10.1016/S0021-9258(18)00001-2"),
    ("# 10.1000/commented", None),
    ("", None),
    ("not a doi", None),
])
def test_normalize_doi(raw, expected):
    assert normalize_doi(raw) == expected


def test_read_dois_skips_comments_and_case_insensitive_duplicates(tmp_path):
    path = tmp_path / "dois.txt"
    path.write_text(
        "# header\n10.1000/AbC\nhttps://doi.org/10.1000/abc\n\n10.1000/other\n"
    )
    assert read_dois(path) == ["10.1000/AbC", "10.1000/other"]


def test_read_dois_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="dois.txt"):
        read_dois(tmp_path / "dois.txt")


def test_safe_filename():
    assert safe_filename("10.1021/jp400894v") == "10.1021_jp400894v"
    assert safe_filename("10.1016/S0021-9258(18)00001-2") == "10.1016_S0021-9258_18_00001-2"
