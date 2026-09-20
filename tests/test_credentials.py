from jev_vla_sim.credentials import load_key_file


def test_key_file_is_data_not_shell(monkeypatch, tmp_path):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    path = tmp_path/".env"
    path.write_text("IGNORED=$(touch SHOULD_NOT_EXIST)\nTYPESAFE_API_KEY='test-only'\n", encoding="utf-8")
    assert load_key_file(path)
    assert not (tmp_path/"SHOULD_NOT_EXIST").exists()


def test_existing_environment_takes_precedence(monkeypatch, tmp_path):
    import os
    monkeypatch.setenv("TYPESAFE_API_KEY", "existing-test")
    path = tmp_path/".env"
    path.write_text("TYPESAFE_API_KEY=file-test", encoding="utf-8")
    assert load_key_file(path)
    assert os.environ["TYPESAFE_API_KEY"] == "existing-test"
