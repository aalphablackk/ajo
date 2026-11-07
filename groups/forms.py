from django import forms
from .models import AjoGroup, AjoCycle, GroupMembership

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

class AjoCycleForm(forms.ModelForm):

    participants = forms.ModelMultipleChoiceField(
        queryset=GroupMembership.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Select cycle participants",
        help_text="Select at least two approved group members."
    )

    class Meta:
        model = AjoCycle

        fields = [
            "contribution_amount",
            "frequency",
            "payout_method",
            "start_date",
        ]

        widgets = {
            "contribution_amount": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0.01",
                "step": "0.01",
                "placeholder": "e.g. 50000",
            }),

            "frequency": forms.Select(attrs={
                "class": "form-select",
            }),

            "payout_method": forms.Select(attrs={
                "class": "form-select",
            }),

            "start_date": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date",
            }),
        }

    def __init__(self, *args, group=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.group = group

        if group:
            self.fields["participants"].queryset = (
                GroupMembership.objects
                .filter(
                    group=group,
                    status=GroupMembership.Status.APPROVED,
                )
                .select_related("user")
                .order_by("joined_at")
            )

    def clean_participants(self):
        participants = self.cleaned_data["participants"]

        if participants.count() < 2:
            raise forms.ValidationError(
                "A cycle must have at least two participants."
            )

        if self.group and participants.count() > self.group.max_members:
            raise forms.ValidationError(
                "The selected participants exceed the group's maximum membership."
            )

        return participants