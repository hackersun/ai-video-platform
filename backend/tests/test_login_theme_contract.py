from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOGIN_PAGE = ROOT / "frontend" / "src" / "app" / "login" / "page.tsx"
PASSWORD_INPUT = ROOT / "frontend" / "src" / "features" / "auth" / "password-input.tsx"


def test_login_page_uses_theme_semantic_surfaces() -> None:
    source = LOGIN_PAGE.read_text(encoding="utf-8")

    assert 'data-testid="login-page"' in source
    assert 'className="relative min-h-screen overflow-hidden bg-background text-foreground"' in source
    assert 'data-testid="login-form-panel"' in source
    assert "bg-card text-card-foreground" in source
    assert "bg-slate-950 text-white" not in source
    assert "bg-slate-900/90" not in source


def test_login_password_input_uses_theme_semantic_tokens() -> None:
    source = PASSWORD_INPUT.read_text(encoding="utf-8")

    assert "text-foreground" in source
    assert "border-input bg-background" in source
    assert "text-white" not in source
    assert "bg-white/[0.06]" not in source
