from django import forms

class QueryForm(forms.Form):
    QUERY_TYPES = (("SQL", "SQL"), ("Pandas", "Pandas"), ("R", "R"))
    query_type = forms.MultipleChoiceField(choices=QUERY_TYPES)
    query = forms.CharField()
    file_name = forms.CharField(widget=forms.HiddenInput())
