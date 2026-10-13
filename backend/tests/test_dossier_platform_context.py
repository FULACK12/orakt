import pytest
from app.dossier_compact_writer import check_platform_names


class Section:
    def __init__(self, text): self.text = text
    def model_dump(self): return {'analysis': {'en': self.text}}


@pytest.mark.parametrize('text', ['Use non-overlapping out-of-sample windows.', 'Freeze training windows and validation windows.', 'Separate rolling windows.'])
def test_sample_windows_are_not_operating_systems(text):
    check_platform_names(Section(text), {'passages': [{'qualitative_view': 'Cash flow report.'}]})


@pytest.mark.parametrize('text', ['Windows operating system sales rose.', 'Microsoft Windows is gaining share.', 'out-of-sample windows and Windows platform growth.'])
def test_unsupported_operating_system_still_rejected(text):
    with pytest.raises(ValueError, match='Windows'):
        check_platform_names(Section(text), {'passages': [{'qualitative_view': 'Cash flow report.'}]})


def test_supported_operating_system_is_allowed():
    check_platform_names(Section('Windows operating system.'), {'passages': [{'qualitative_view': 'Windows operating system.'}]})
