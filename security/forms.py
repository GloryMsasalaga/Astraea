# security/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from .models import UserProfile

class SecureLoginForm(AuthenticationForm):
    """Enhanced login form with security features"""
    
    username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your username',
            'autocomplete': 'username',
            'required': True,
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
            'required': True,
        })
    )
    
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        })
    )
    
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        
        if username and password:
            # Check if user exists
            try:
                user = User.objects.get(username=username)
                profile, created = UserProfile.objects.get_or_create(user=user)
                
                # Check if account is locked
                if profile.is_account_locked():
                    raise ValidationError(
                        "Account is temporarily locked due to multiple failed login attempts. "
                        f"Please try again after {profile.account_locked_until.strftime('%H:%M')}."
                    )
                    
            except User.DoesNotExist:
                # Don't reveal that the user doesn't exist
                pass
        
        return super().clean()

class TwoFactorForm(forms.Form):
    """2FA verification form"""
    
    token = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center',
            'placeholder': '000000',
            'autocomplete': 'one-time-code',
            'pattern': '[0-9]{6}',
            'required': True,
            'maxlength': '6',
            'style': 'letter-spacing: 0.5em; font-size: 1.5rem;'
        })
    )
    
    def clean_token(self):
        token = self.cleaned_data['token']
        if not token.isdigit():
            raise ValidationError("Token must contain only numbers.")
        if len(token) != 6:
            raise ValidationError("Token must be exactly 6 digits.")
        return token

class PasswordChangeSecureForm(forms.Form):
    """Secure password change form"""
    
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter current password',
            'autocomplete': 'current-password',
        })
    )
    
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password',
            'autocomplete': 'new-password',
        })
    )
    
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password',
            'autocomplete': 'new-password',
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError("New passwords do not match.")
        
        return cleaned_data


class SecureRegistrationForm(UserCreationForm):
    """Enhanced registration form with security features"""
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your first name',
            'autocomplete': 'given-name',
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your last name',
            'autocomplete': 'family-name',
        })
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your email address',
            'autocomplete': 'email',
        })
    )
    
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Choose a username',
            'autocomplete': 'username',
        }),
        help_text='Username must be unique and contain only letters, numbers, and @/./+/-/_ characters.'
    )
    
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Create a strong password',
            'autocomplete': 'new-password',
        }),
        help_text='Password must be at least 8 characters and include uppercase, lowercase, numbers, and special characters.'
    )
    
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password',
        })
    )
    
    role = forms.ChoiceField(
        choices=[
            ('accountant', 'Accountant'),
            ('auditor', 'Auditor'),
            ('manager', 'Manager'),
            ('viewer', 'Viewer'),
        ],
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-lg',
        }),
        help_text='Select your role in the organization.'
    )
    
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='I agree to the Terms of Service and Privacy Policy'
    )
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'username', 'password1', 'password2')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("This username is already taken.")
        return username
    
    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        try:
            validate_password(password1)
        except ValidationError as e:
            raise ValidationError(e.messages)
        return password1
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Create user profile with selected role
            UserProfile.objects.create(
                user=user,
                role=self.cleaned_data['role']
            )
        
        return user
