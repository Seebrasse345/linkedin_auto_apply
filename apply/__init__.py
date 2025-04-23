"""
LinkedIn Auto Apply Bot module.
Provides automated interaction with LinkedIn job application forms.
"""
from .constants import (
    APPLICATION_SUCCESS,
    APPLICATION_FAILURE,
    APPLICATION_INCOMPLETE
)
from .application_wizard import ApplicationWizard

__all__ = [
    'ApplicationWizard',
    'APPLICATION_SUCCESS',
    'APPLICATION_FAILURE',
    'APPLICATION_INCOMPLETE'
]
