from django import forms

from store.models import DeveloperConfig


class DeveloperConfigForm(forms.ModelForm):
    class Meta:
        model = DeveloperConfig
        fields = ["webhook_secret", "razorpay_key_id", "razorpay_key_secret"]
        widgets = {
            "webhook_secret": forms.TextInput(attrs={"class": "w-full rounded-xl border border-slate-200 px-3 py-2"}),
            "razorpay_key_id": forms.TextInput(attrs={"class": "w-full rounded-xl border border-slate-200 px-3 py-2"}),
            "razorpay_key_secret": forms.PasswordInput(attrs={"class": "w-full rounded-xl border border-slate-200 px-3 py-2"}),
        }

