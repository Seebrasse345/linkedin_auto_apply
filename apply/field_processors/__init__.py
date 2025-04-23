"""
Field processors for handling different types of LinkedIn job application form fields.
"""
from .base import FieldProcessor
from .text_processor import TextInputProcessor, TextareaProcessor
from .select_processor import SelectProcessor
from .radio_processor import RadioProcessor, RadioGroupProcessor
from .checkbox_processor import CheckboxProcessor
from .resume_processor import ResumeProcessor

__all__ = [
    'FieldProcessor',
    'TextInputProcessor',
    'TextareaProcessor',
    'SelectProcessor',
    'RadioProcessor',
    'RadioGroupProcessor',
    'CheckboxProcessor',
    'ResumeProcessor',
]
