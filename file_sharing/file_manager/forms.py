# file_manager/forms.py
from django import forms

class UniqueKeyForm(forms.Form):
    unique_key = forms.CharField(label='Ключ доступа', max_length=255)

class UploadFileForm(forms.Form):
    file = forms.FileField(label='Загрузите ваш Файл')