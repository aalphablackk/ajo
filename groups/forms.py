from django import forms
from .models import AjoGroup


class AjoGroupForm(forms.ModelForm):

    class Meta:
        model = AjoGroup
        fields = [
            "name",
            "description",
            "contribution_amount",
            "frequency",
            "max_members",
            "start_date",
            "payout_method",
        ]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. Family Monthly Ajo",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Describe the purpose of this group",
            }),
            "contribution_amount": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0.01",
                "step": "0.01",
                "placeholder": "e.g. 50000",
            }),
            "frequency": forms.Select(attrs={
                "class": "form-select",
            }),
            "max_members": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "2",
            }),
            "start_date": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date",
            }),
            "payout_method": forms.Select(attrs={
                "class": "form-select",
            }),
        }